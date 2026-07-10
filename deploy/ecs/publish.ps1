#requires -Version 5.1
<#
.SYNOPSIS
  Publish Learning Hub to the Aliyun ECS (121.199.53.233) Docker Swarm stack `learning-hub`.

.DESCRIPTION
  - Locally docker build backend / frontend images (tags lh-backend / lh-frontend, tag = IMAGE_TAG).
  - docker save to tar, scp to ECS /root/learning-hub/.
  - ssh triggers remote-setup.sh / db-init.sh / docker load / docker stack deploy.
  - Polls docker stack ps until backend / frontend are Running.
  - ssh triggers nginx-vhost-apply.sh (first run issues cert + appends vhost + reloads).
  - Prints HTTPS verification checklist.

.PARAMETER SkipBuild
  Skip local build + image save; reuse existing local images (for quick re-deploy).

.PARAMETER SkipNginx
  Skip nginx-gateway cert + vhost changes (use when stack is fine and only app needs redeploy).

.EXAMPLE
  PS> .\publish.ps1
  PS> .\publish.ps1 -SkipBuild
  PS> .\publish.ps1 -SkipNginx

.NOTES
  Prereqs: PowerShell 5.1+ / Docker / scp / ssh on PATH.
            .env file (copy from .env.example, fill in real values).

  PowerShell 5.1 compatibility notes:
    - All user-visible strings are ASCII-only because Windows PowerShell 5.1 parses script
      files using the console ANSI code page; UTF-8 bytes get mis-decoded and break
      inline @ / $(...) parsing. If you want Chinese messages, write the script with
      PowerShell 7+ or add a UTF-8 BOM and run via `chcp 65001`.
    - Remote bash commands use ';' separator instead of '&&' (PS 5.1 rejects &&).
#>

[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipNginx,
    [int]$WaitHealthyTimeout = 300
)

Set-Location -LiteralPath $PSScriptRoot

# ---- Output helpers (ASCII only) ------------------------------------------
function OutStep($msg)  { Write-Host "[*] " -NoNewline -ForegroundColor Cyan;    Write-Host $msg }
function OutOk($msg)    { Write-Host "[+] " -NoNewline -ForegroundColor Green;  Write-Host $msg }
function OutWarn($msg)  { Write-Host "[!] " -NoNewline -ForegroundColor Yellow; Write-Host $msg }
function OutErr($msg)   { Write-Host "[-] " -NoNewline -ForegroundColor Red;    Write-Host $msg }

# ---- 1) Load .env ----------------------------------------------------------
OutStep "Loading .env"
$envFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envFile)) {
    OutErr ".env not found (expected at $envFile). Run `cp .env.example .env` and fill in real values first."
    exit 1
}

$envVars = @{}
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#')) {
        $kv = $line -split '=', 2
        if ($kv.Length -eq 2) { $envVars[$kv[0]] = $kv[1] }
    }
}

foreach ($k in @('ECS_SSH_USER','ECS_HOST','ECS_SSH_KEY_PATH','IMAGE_TAG','POSTGRES_NETWORK_NAME','POSTGRES_SERVICE_NAME','NGINX_NETWORK_NAME','DATABASE_USER','DATABASE_PASSWORD','DATABASE_NAME','ADMIN_TOKEN','JWT_SECRET','LH_DOMAIN','ECS_REMOTE_DIR')) {
    if (-not $envVars.ContainsKey($k) -or [string]::IsNullOrWhiteSpace($envVars[$k])) {
        OutErr ".env is missing required key: $k"
        exit 1
    }
}

foreach ($k in $envVars.Keys) { Set-Item -Path "Env:\$k" -Value $envVars[$k] }

$EC = @{
    User        = $envVars['ECS_SSH_USER']
    Host        = $envVars['ECS_HOST']
    Key         = $envVars['ECS_SSH_KEY_PATH']
    RemoteDir   = $envVars['ECS_REMOTE_DIR']
    ImageTag    = $envVars['IMAGE_TAG']
    LhDomain    = $envVars['LH_DOMAIN']
}
OutOk "ECS=$($EC.User)@$($EC.Host), tag=$($EC.ImageTag), domain=$($EC.LhDomain)"

# ---- 2) Test SSH ------------------------------------------------------------
OutStep "Testing SSH connection to $($EC.User)@$($EC.Host)"
& ssh -i $EC.Key -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "$($EC.User)@$($EC.Host)" 'echo OK' | Out-Null
if ($LASTEXITCODE -ne 0) {
    OutErr "SSH failed. Check that $($EC.Key) is in ECS ~/.ssh/authorized_keys."
    exit 1
}
OutOk "SSH reachable"

# ---- 3) Build images --------------------------------------------------------
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$BackendDir = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$BackendImage = "lh-backend:$($EC.ImageTag)"
$FrontendImage = "lh-frontend:$($EC.ImageTag)"

if (-not $SkipBuild) {
    # ECS is aarch64 (ARM64). On Windows / x86 dev hosts we must build with
    # buildx + explicit --platform, otherwise exec format error blocks startup.
    # Make sure a single-node 'lhxbuild' buildx builder exists; create if absent.
    $builderExists = (& docker buildx ls 2>$null) -join "`n" -match '(?m)^lhxbuild\b'
    if (-not $builderExists) {
        # Windows / Docker Desktop: docker driver 只能创建一个 default builder。
        # 直接复用 default builder（Docker Desktop 默认启用了 QEMU,可交叉编译 arm64）。
        OutStep "No 'lhxbuild' builder found; using default builder (Docker Desktop + QEMU)..."
        & docker buildx use default | Out-Null
        if ($LASTEXITCODE -ne 0) { OutErr "docker buildx use default failed"; exit 1 }
    } else {
        & docker buildx use lhxbuild | Out-Null
    }

    OutStep "Building backend image for linux/arm64 (LibreOffice + deps are heavy; 5-10 min first time)..."
    & docker buildx build --platform linux/arm64 -t $BackendImage --load $BackendDir | Out-Null
    if ($LASTEXITCODE -ne 0) { OutErr "backend image build failed"; exit 1 }
    OutOk "backend image built (arm64): $BackendImage"

    OutStep "Patching frontend/nginx.conf: backend -> learning-hub_backend (swarm service DNS)"
    $feNginx = Join-Path $FrontendDir 'nginx.conf'
    $orig = Get-Content -LiteralPath $feNginx -Raw
    $patched = $orig -replace 'proxy_pass http://backend:8000', 'proxy_pass http://learning-hub_backend:8000'
    if ($patched -ne $orig) {
        Set-Content -LiteralPath $feNginx -Value $patched -NoNewline
    }

    OutStep "Building frontend image for linux/arm64..."
    & docker buildx build --platform linux/arm64 -t $FrontendImage --load $FrontendDir | Out-Null
    if ($LASTEXITCODE -ne 0) { OutErr "frontend image build failed"; exit 1 }
    OutOk "frontend image built (arm64): $FrontendImage"
} else {
    OutWarn "SkipBuild is on; assuming $BackendImage and $FrontendImage already exist"
    foreach ($img in @($BackendImage, $FrontendImage)) {
        $exists = & docker images -q $img
        if ([string]::IsNullOrEmpty($exists)) {
            OutErr "Image $img not found locally; remove -SkipBuild and re-run."
            exit 1
        }
        $arch = & docker inspect $img --format '{{.Architecture}}'
        if ($arch -ne 'arm64') {
            OutWarn "Image $img architecture is '$arch', but ECS is arm64. Rebuild without -SkipBuild."
        }
    }
}

# ---- 4) Save images ---------------------------------------------------------
if (-not $SkipBuild) {
    OutStep "Saving images to tar..."
    $tar = Join-Path $PSScriptRoot "lh-images.tar"
    if (Test-Path $tar) { Remove-Item $tar -Force }
    & docker save -o $tar $BackendImage $FrontendImage | Out-Null
    if ($LASTEXITCODE -ne 0) { OutErr "docker save failed"; exit 1 }
    $size = [Math]::Round((Get-Item $tar).Length / 1MB, 1)
    OutOk "tar written ($size MB): $tar"
} else {
    OutWarn "SkipBuild is on; skipping save. Ensure tar already exists at $($EC.RemoteDir)."
}

# ---- 5) Remote: mkdir the working dir (must precede scp) -------------------
function Invoke-Ssh {
    param([string]$Cmd)
    # 用 $output 变量吃 SSH stdout,避免返回值被 "OK" 字符串污染。
    $output = & ssh -i $EC.Key -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$($EC.User)@$($EC.Host)" $Cmd 2>&1
    return $LASTEXITCODE
}

OutStep "Remote: mkdir -p $($EC.RemoteDir)"
$rc = Invoke-Ssh "mkdir -p $($EC.RemoteDir) ; echo OK"
if ($rc -ne 0) { OutErr "remote mkdir failed (exit=$rc)"; exit 1 }
OutOk "remote working dir ready"

# ---- 6) scp files ----------------------------------------------------------
OutStep "scp .env / compose.yml / remote-setup.sh / db-init.sh / nginx-vhost-apply.sh / nginx-vhost-http.snippet / nginx-vhost-https.snippet / persist-cert-mount.py to $($EC.Host):$($EC.RemoteDir)"
foreach ($f in @('.env','compose.yml','remote-setup.sh','db-init.sh','nginx-vhost-apply.sh','nginx-vhost-http.snippet','nginx-vhost-https.snippet','persist-cert-mount.py')) {
    & scp -i $EC.Key -o BatchMode=yes -o StrictHostKeyChecking=accept-new (Join-Path $PSScriptRoot $f) "$($EC.User)@$($EC.Host):$($EC.RemoteDir)/"
    if ($LASTEXITCODE -ne 0) { OutErr "scp $f failed"; exit 1 }
}

if (-not $SkipBuild) {
    OutStep "scp lh-images.tar to $($EC.Host):$($EC.RemoteDir)"
    & scp -i $EC.Key -o BatchMode=yes -o StrictHostKeyChecking=accept-new (Join-Path $PSScriptRoot "lh-images.tar") "$($EC.User)@$($EC.Host):$($EC.RemoteDir)/"
    if ($LASTEXITCODE -ne 0) { OutErr "scp lh-images.tar failed"; exit 1 }
}

# ---- 7) Remote: setup / db-init / docker load / docker stack deploy --------

OutStep "Remote: bash $($EC.RemoteDir)/remote-setup.sh"
$rc = Invoke-Ssh "bash $($EC.RemoteDir)/remote-setup.sh"
if ($rc -ne 0) { OutErr "remote-setup.sh failed (exit=$rc)"; exit 1 }
OutOk "remote-setup done (dir + lh_storage created)"
$envInline = "POSTGRES_SERVICE_NAME='$($envVars['POSTGRES_SERVICE_NAME'])' DATABASE_USER='$($envVars['DATABASE_USER'])' DATABASE_PASSWORD='$($envVars['DATABASE_PASSWORD'])' DATABASE_NAME='$($envVars['DATABASE_NAME'])' LH_DOMAIN='$($envVars['LH_DOMAIN'])' ECS_REMOTE_DIR='$($envVars['ECS_REMOTE_DIR'])'"
$rc = Invoke-Ssh "$envInline bash $($EC.RemoteDir)/db-init.sh"
if ($rc -ne 0) { OutErr "db-init.sh failed (exit=$rc)"; exit 1 }
OutOk "db-init done"

if (-not $SkipBuild) {
    OutStep "Remote: docker load -i $($EC.RemoteDir)/lh-images.tar"
    # Use ';' instead of '&&' (PS 5.1 does not support &&).
    $rc = Invoke-Ssh "docker load -i $($EC.RemoteDir)/lh-images.tar ; rm $($EC.RemoteDir)/lh-images.tar"
    if ($rc -ne 0) { OutErr "docker load failed (exit=$rc)"; exit 1 }
    OutOk "docker load done"
}

OutStep "Remote: docker stack deploy -c compose.yml learning-hub"
$deployEnv = "POSTGRES_NETWORK_NAME='$($envVars['POSTGRES_NETWORK_NAME'])' POSTGRES_SERVICE_NAME='$($envVars['POSTGRES_SERVICE_NAME'])' NGINX_NETWORK_NAME='$($envVars['NGINX_NETWORK_NAME'])' IMAGE_TAG='$($envVars['IMAGE_TAG'])'"
# Use ';' instead of '&&' (PS 5.1 does not support &&).
$rc = Invoke-Ssh "cd $($EC.RemoteDir) ; $deployEnv docker stack deploy -c compose.yml learning-hub"
if ($rc -ne 0) { OutErr "docker stack deploy failed (exit=$rc)"; exit 1 }
OutOk "learning-hub stack deployed"

# ---- 7) Poll stack status ---------------------------------------------------
OutStep "Waiting for backend / frontend Running (timeout=${WaitHealthyTimeout}s)"
$deadline = (Get-Date).AddSeconds($WaitHealthyTimeout)
$allOk = $false
while ((Get-Date) -lt $deadline) {
    $psOutput = Invoke-Ssh "docker stack ps learning-hub --format '{{.Name}} {{.DesiredState}} {{.CurrentState}}'"
    $allOk = $true
    $haveBackend = $false
    $haveFrontend = $false
    $hasOutput = $false
    if ($LASTEXITCODE -eq 0 -and $psOutput) {
        $lines = $psOutput -split "`n" | Where-Object { $_.Trim() }
        $hasOutput = ($lines.Count -gt 0)
        foreach ($line in $lines) {
            $parts = $line.Trim() -split ' '
            $name = $parts[0]
            $current = $parts[-1]
            Write-Host "  - $name ... $current" -ForegroundColor DarkGray
            if ($name -like "*backend*")  { $haveBackend  = ($current -eq "Running") }
            if ($name -like "*frontend*") { $haveFrontend = ($current -eq "Running") }
        }
        if ($haveBackend -and $haveFrontend) { $allOk = $true; break }
        $allOk = $false
    } else {
        $allOk = $false
    }
    if ($allOk -and $hasOutput) { break }
    Start-Sleep -Seconds 5
}
if (-not $allOk) { OutWarn "Some services are not Running within ${WaitHealthyTimeout}s; check on ECS with 'docker stack ps learning-hub'" }

# ---- 8) nginx-gateway: cert + vhost ----------------------------------------
if (-not $SkipNginx) {
    # Phase 1: 80 redirect + certbot webroot -> issue LE cert
    OutStep "nginx-vhost-apply phase1 (add 80 block + certbot issue)"
    $acmeEmail = if ([string]::IsNullOrWhiteSpace($envVars['ACME_EMAIL'])) { 'admin@smartmoves.com.cn' } else { $envVars['ACME_EMAIL'] }
    $envP1 = "LH_DOMAIN='$($envVars['LH_DOMAIN'])' NGINX_STACK_DIR='/root/nginx-smartmoves' STACK_NAME='nginx-gateway' ACME_EMAIL='$acmeEmail' CERTBOT_WEBROOT='/root/nginx-static/html' REMOTE_DIR='$($EC.RemoteDir)'"
    $rc = Invoke-Ssh "$envP1 bash $($EC.RemoteDir)/nginx-vhost-apply.sh phase1"
    if ($rc -ne 0) { OutErr "phase1 failed (exit=$rc)"; exit 1 }
    OutOk "phase1 done (cert issued)"

    # 8a) Add cert volume mounts to nginx-gateway stack service and force recreate.
    OutStep "Patching nginx-gateway docker-compose.yml with cert mounts + redeploy"
    $rc = Invoke-Ssh "docker service update --mount-add type=bind,source=/etc/letsencrypt/live/$($envVars['LH_DOMAIN'])/fullchain.pem,target=/etc/nginx/certs/$($envVars['LH_DOMAIN']).crt,readonly=true nginx-gateway_nginx"
    if ($rc -ne 0) { OutErr "mount-add fullchain failed"; exit 1 }
    $rc = Invoke-Ssh "docker service update --mount-add type=bind,source=/etc/letsencrypt/live/$($envVars['LH_DOMAIN'])/privkey.pem,target=/etc/nginx/certs/$($envVars['LH_DOMAIN']).key,readonly=true nginx-gateway_nginx"
    if ($rc -ne 0) { OutErr "mount-add privkey failed"; exit 1 }
    OutOk "cert mounts injected into nginx-gateway_nginx"

    # Phase 2: insert 443 server block + reload (cert is now in container).
    OutStep "nginx-vhost-apply phase2 (add 443 block + reload)"
    $envP2 = "LH_DOMAIN='$($envVars['LH_DOMAIN'])' NGINX_STACK_DIR='/root/nginx-smartmoves' STACK_NAME='nginx-gateway' REMOTE_DIR='$($EC.RemoteDir)'"
    $rc = Invoke-Ssh "$envP2 bash $($EC.RemoteDir)/nginx-vhost-apply.sh phase2"
    if ($rc -ne 0) { OutErr "phase2 failed (exit=$rc)"; exit 1 }
    OutOk "phase2 done (443 server block live)"

    # Also persist cert mounts to the nginx-gateway docker-compose.yml on the host
    # (mount-add alone is enough for runtime, but stack deploy needs them baked in
    # for the next re-deploy to keep them).
    $rc = Invoke-Ssh "python3 /root/learning-hub/persist-cert-mount.py $($envVars['LH_DOMAIN'])"
    OutOk "nginx-gateway compose.yml mounts persisted (persist-cert-mount.py rc=$rc)"
} else {
    OutWarn "SkipNginx is on; cert issue / vhost append skipped"
}

# ---- 9) Print verification checklist ---------------------------------------
Write-Host ""
Write-Host "================ Deploy Complete ================" -ForegroundColor Green
Write-Host "  Public entry  :  https://$($EC.LhDomain)/" -ForegroundColor White
Write-Host "  HTTP -> HTTPS :  curl -I http://$($EC.LhDomain)/  (expect 301 -> https)" -ForegroundColor White
Write-Host "  Backend health:  curl https://$($EC.LhDomain)/api/public/health" -ForegroundColor White
Write-Host "  Admin login   :  https://$($EC.LhDomain)/admin   (token=$($envVars['ADMIN_TOKEN']))" -ForegroundColor White
Write-Host ""
Write-Host "  Follow-up on ECS:" -ForegroundColor White
Write-Host "    ssh -i $($EC.Key) $($EC.User)@$($EC.Host)" -ForegroundColor DarkGray
Write-Host "    docker stack ps learning-hub" -ForegroundColor DarkGray
Write-Host "    docker service logs learning-hub_backend" -ForegroundColor DarkGray
Write-Host "    docker service logs learning-hub_frontend" -ForegroundColor DarkGray
$backendCid = Invoke-Ssh 'docker ps -q -f name=learning-hub_backend.1 | head -1'
Write-Host "    docker exec $backendCid alembic current" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Rollback: docker -H ssh://$($EC.User)@$($EC.Host) stack rm learning-hub" -ForegroundColor DarkGray
Write-Host "================================================" -ForegroundColor Green
