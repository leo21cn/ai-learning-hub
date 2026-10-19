#requires -Version 5.1
<#
.SYNOPSIS
  Publish indexpage/index.html to https://learning-hub.smartmoves.com.cn/intro/.

.DESCRIPTION
  1. Verify indexpage/index.html + og-cover.png + qr.png match their frontend/public copies.
  2. Upload the page, share image, QR code and remote build script to the ECS host.
  3. On the ECS host: rebuild lh-frontend from the currently running image with
     only /usr/share/nginx/html/intro/ replaced, then roll the
     learning-hub_frontend service.
  4. Fetch the public URL, OG image and QR code, compare SHA-256 with local files.

  Uses the existing SSH key (BatchMode). No password or local Docker needed.

.PARAMETER EcsHost
  ECS public address. Default 121.199.53.233.

.PARAMETER SkipVerify
  Skip the final public-URL hash check.

.EXAMPLE
  pwsh -File scripts/sync-intro.ps1
#>
[CmdletBinding()]
param(
    [string]$EcsHost = '121.199.53.233',
    [string]$EcsUser = 'root',
    [string]$RemoteDir = '/root/learning-hub/intro-deploy',
    [string]$PublicUrl = 'https://learning-hub.smartmoves.com.cn/intro/',
    [switch]$SkipVerify
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'indexpage/index.html'
$mirror = Join-Path $root 'frontend/public/intro/index.html'
$ogSource = Join-Path $root 'indexpage/og-cover.png'
$ogMirror = Join-Path $root 'frontend/public/intro/og-cover.png'
$qrSource = Join-Path $root 'indexpage/qr.png'
$qrMirror = Join-Path $root 'frontend/public/intro/qr.png'
$remoteScript = Join-Path $root 'deploy/ecs/sync-intro-remote.sh'

foreach ($p in @($source, $mirror, $ogSource, $ogMirror, $qrSource, $qrMirror, $remoteScript)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "missing file: $p" }
}

$srcHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$mirrorHash = (Get-FileHash -LiteralPath $mirror -Algorithm SHA256).Hash.ToLowerInvariant()
if ($srcHash -ne $mirrorHash) {
    throw "intro copies differ (indexpage vs frontend/public) - sync them before publishing"
}
$ogHash = (Get-FileHash -LiteralPath $ogSource -Algorithm SHA256).Hash.ToLowerInvariant()
$ogMirrorHash = (Get-FileHash -LiteralPath $ogMirror -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ogHash -ne $ogMirrorHash) {
    throw "OG image copies differ (indexpage vs frontend/public) - sync them before publishing"
}
$qrHash = (Get-FileHash -LiteralPath $qrSource -Algorithm SHA256).Hash.ToLowerInvariant()
$qrMirrorHash = (Get-FileHash -LiteralPath $qrMirror -Algorithm SHA256).Hash.ToLowerInvariant()
if ($qrHash -ne $qrMirrorHash) {
    throw "QR copies differ (indexpage vs frontend/public) - sync them before publishing"
}
Write-Host "[*] local sha256 : $srcHash"
Write-Host "[*] og sha256    : $ogHash"
Write-Host "[*] qr sha256    : $qrHash"

$sshArgs = @('-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=no')
$target = "$EcsUser@$EcsHost"

& ssh @sshArgs $target "mkdir -p $RemoteDir"
if ($LASTEXITCODE -ne 0) { throw "remote mkdir failed" }

& scp @sshArgs $source "${target}:${RemoteDir}/index.html"
if ($LASTEXITCODE -ne 0) { throw "scp index.html failed" }

& scp @sshArgs $ogSource "${target}:${RemoteDir}/og-cover.png"
if ($LASTEXITCODE -ne 0) { throw "scp og-cover.png failed" }

& scp @sshArgs $qrSource "${target}:${RemoteDir}/qr.png"
if ($LASTEXITCODE -ne 0) { throw "scp qr.png failed" }

& scp @sshArgs $remoteScript "${target}:${RemoteDir}/sync.sh"
if ($LASTEXITCODE -ne 0) { throw "scp sync.sh failed" }

Write-Host "[*] building image and rolling learning-hub_frontend ..."
& ssh @sshArgs $target "bash $RemoteDir/sync.sh"
if ($LASTEXITCODE -ne 0) { throw "remote sync failed" }

if ($SkipVerify) {
    Write-Host "[+] published (verification skipped)"
    return
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) 'lh-intro-live.html'
& curl.exe -sS -o $tmp $PublicUrl
if ($LASTEXITCODE -ne 0) { throw "failed to fetch $PublicUrl" }
$liveHash = (Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash.ToLowerInvariant()
$liveSize = (Get-Item -LiteralPath $tmp).Length

if ($liveHash -ne $srcHash) {
    throw "live hash mismatch: local=$srcHash live=$liveHash"
}

$tmpOg = Join-Path ([System.IO.Path]::GetTempPath()) 'lh-intro-live-og.png'
& curl.exe -sS -o $tmpOg "${PublicUrl}og-cover.png"
if ($LASTEXITCODE -ne 0) { throw "failed to fetch ${PublicUrl}og-cover.png" }
$liveOgHash = (Get-FileHash -LiteralPath $tmpOg -Algorithm SHA256).Hash.ToLowerInvariant()
if ($liveOgHash -ne $ogHash) {
    throw "live OG hash mismatch: local=$ogHash live=$liveOgHash"
}

$tmpQr = Join-Path ([System.IO.Path]::GetTempPath()) 'lh-intro-live-qr.png'
& curl.exe -sS -o $tmpQr "${PublicUrl}qr.png"
if ($LASTEXITCODE -ne 0) { throw "failed to fetch ${PublicUrl}qr.png" }
$liveQrHash = (Get-FileHash -LiteralPath $tmpQr -Algorithm SHA256).Hash.ToLowerInvariant()
if ($liveQrHash -ne $qrHash) {
    throw "live QR hash mismatch: local=$qrHash live=$liveQrHash"
}

Write-Host "[+] live sha256  : $liveHash (size=$liveSize)"
Write-Host "[+] live og      : $liveOgHash"
Write-Host "[+] live qr      : $liveQrHash"
Write-Host "[+] published    : $PublicUrl"
