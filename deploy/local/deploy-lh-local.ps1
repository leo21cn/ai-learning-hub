#requires -Version 5.1
<#
.SYNOPSIS
  Learning Hub 本机 Docker Desktop 部署脚本。

.DESCRIPTION
  - 自动通过 named pipe 连接 Docker Desktop daemon（无需 2375 端口）
  - 重建 backend / frontend 镜像（含本轮新增的 P-VIEWER 素材预览能力）
  - 用 deploy 命名空间启动三服务（postgres + backend + frontend）
  - 验证后端 openapi 中是否已注册 /api/public/materials/{id}/stream 接口
  - 打印最终访问地址

.EXAMPLE
  PS> .\deploy-lh-local.ps1
#>

[CmdletBinding()]
param(
    [string]$ProjectName = "deploy",
    [string]$ComposeFile = "docker-compose.yml",
    [int]$WaitHealthyTimeout = 180
)

Set-Location -LiteralPath $PSScriptRoot

# ---- 颜色输出工具 ----------------------------------------------------------
function OutStep($msg)  { Write-Host "[*] " -NoNewline -ForegroundColor Cyan;    Write-Host $msg }
function OutOk($msg)    { Write-Host "[+] " -NoNewline -ForegroundColor Green;  Write-Host $msg }
function OutWarn($msg)  { Write-Host "[!] " -NoNewline -ForegroundColor Yellow; Write-Host $msg }
function OutErr($msg)   { Write-Host "[-] " -NoNewline -ForegroundColor Red;    Write-Host $msg }

# ---- Docker CLI 包装 --------------------------------------------------------
# Docker Desktop v29 默认只走 named pipe，所以显式指定 -H
# 多连接方式 fallback：named pipe → TCP 2375 → 默认（看环境变量）
$script:DockerHostCandidates = @(
    "npipe:////./pipe/docker_engine"
    "tcp://127.0.0.1:2375"
)
$script:DockerHost = $null

function Find-DockerHost {
    foreach ($cand in $script:DockerHostCandidates) {
        $out = & docker -H $cand version --format "{{.Server.Version}}" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            $script:DockerHost = $cand
            return $cand
        }
    }
    return $null
}

function Invoke-Docker {
    if (-not $script:DockerHost) { Find-DockerHost | Out-Null }
    if (-not $script:DockerHost) { throw "无任一 Docker daemon 端点可用" }
    & docker -H $script:DockerHost @args
    return $LASTEXITCODE
}

# ---- 1) 探测 Docker daemon ------------------------------------------------
OutStep "探测 Docker Desktop daemon"
$script:DockerHost = Find-DockerHost
if (-not $script:DockerHost) {
    OutErr "无法连接 Docker Desktop。请检查："
    OutErr "  1) Docker Desktop 是否已启动（右下角鲸鱼图标变绿）"
    OutErr "  2) PowerShell 是否以管理员身份运行（named pipe 需要 admin ACL）"
    OutErr "  3) 或者在 Docker Desktop Settings → Docker Engine 添加 hosts: tcp://0.0.0.0:2375"
    OutErr ""
    OutErr "管理员身份验证："
    OutErr "  ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent())"
    OutErr "    .IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"
    exit 1
}
$serverVer = (& docker -H $script:DockerHost version --format "{{.Server.Version}}").Trim()
OutOk "Docker Engine $serverVer 已就绪 (via $script:DockerHost)"

# ---- 2) 停掉旧容器（释放内存以 build） -----------------------------------
OutStep "停止旧容器（保留数据卷）"
$rc = Invoke-Docker compose -p $ProjectName -f $ComposeFile stop backend frontend 2>$null
if ($rc -ne 0) { OutWarn "stop 时已无运行中的容器（可忽略）" }
OutOk "backend / frontend 已停止；postgres 继续保留以省去重跑 alembic 时间"

# ---- 3) 重建 backend ------------------------------------------------------
OutStep "重建 backend（首次约 5min，后续命中缓存约 1min）"
$buildLog = Join-Path $env:TEMP "lh-build-backend.log"
& docker -H $script:DockerHost compose -p $ProjectName -f $ComposeFile build backend 2>&1 |
    Tee-Object -FilePath $buildLog | Out-Null
$rc = $LASTEXITCODE
if ($rc -ne 0) {
    OutErr "backend 构建失败。完整日志: $buildLog"
    Select-String -Path $buildLog -Pattern "(Failed|Err|Unable|cannot|exit code|error:)" |
        ForEach-Object { Write-Host "    " -NoNewline; Write-Host $_ }
    exit 1
}
OutOk "backend 镜像已重建"

# ---- 4) 重建 frontend -----------------------------------------------------
OutStep "重建 frontend（首次约 3min，后续命中缓存约 30s）"
$buildLog = Join-Path $env:TEMP "lh-build-frontend.log"
& docker -H $script:DockerHost compose -p $ProjectName -f $ComposeFile build frontend 2>&1 |
    Tee-Object -FilePath $buildLog | Out-Null
$rc = $LASTEXITCODE
if ($rc -ne 0) {
    OutErr "frontend 构建失败。完整日志: $buildLog"
    Select-String -Path $buildLog -Pattern "(Failed|Err|Unable|cannot|exit code|error:)" |
        ForEach-Object { Write-Host "    " -NoNewline; Write-Host $_ }
    exit 1
}
OutOk "frontend 镜像已重建"

# ---- 5) 启动三服务 ---------------------------------------------------------
OutStep "启动 postgres + backend + frontend"
$rc = Invoke-Docker compose -p $ProjectName -f $ComposeFile up -d backend frontend
if ($rc -ne 0) { OutErr "up -d 失败 (exit=$rc)"; exit 1 }
OutOk "三服务已在 $ProjectName project 启动"

# ---- 6) 等到 healthy ------------------------------------------------------
OutStep "等待容器 healthy (timeout=$WaitHealthyTimeout s)"
$deadline = (Get-Date).AddSeconds($WaitHealthyTimeout)
$allHealthy = $false
while ((Get-Date) -lt $deadline) {
    $psOutput = & docker -H $script:DockerHost compose -p $ProjectName -f $ComposeFile ps --format json 2>$null | Out-String
    $allHealthy = $true
    $healthyCount = 0
    $containerCount = 0
    if (-not [string]::IsNullOrWhiteSpace($psOutput)) {
        $lines = $psOutput -split "`n" | Where-Object { $_.Trim() }
        foreach ($line in $lines) {
            $c = $line | ConvertFrom-Json -ErrorAction SilentlyContinue
            if ($null -eq $c) { continue }
            $containerCount += 1
            $state = $c.State
            $health = $c.Health
            $lineStr = "  - {0,-12} {1,-10} {2}" -f $c.Service, $state, $health
            if ($state -ne "running") {
                $allHealthy = $false
                OutWarn $lineStr
            } elseif ($health -and $health -ne "healthy") {
                $allHealthy = $false
                OutWarn $lineStr
            } else {
                $healthyCount += 1
                OutOk $lineStr
            }
        }
    }
    if ($allHealthy -and $containerCount -ge 3) { break }
    Start-Sleep -Seconds 5
}
if (-not $allHealthy) { OutWarn "部分容器尚未 healthy,请稍后用 'docker compose -p $ProjectName ps' 查看" }

# ---- 7) 验证 openapi 包含本轮新接口 --------------------------------------
OutStep "验证后端 openapi 已注册本轮新接口"
try {
    $openapi = (Invoke-WebRequest "http://127.0.0.1:8000/api/openapi.json" -UseBasicParsing -TimeoutSec 5).Content
    $hasStream = $openapi -match '"/api/public/materials/\{material_id\}/stream"'
    $hasGetOne = $openapi -match '"/api/public/materials/\{material_id\}":\s*\{'
    $hasCwGet  = $openapi -match '"/api/public/coursewares/\{courseware_id\}":\s*\{'
    if ($hasStream) { OutOk "GET /api/public/materials/{id}/stream   已注册" } else { OutWarn "stream 接口未注册" }
    if ($hasGetOne) { OutOk "GET /api/public/materials/{id}         已注册" } else { OutWarn "公开素材详情未注册" }
    if ($hasCwGet)  { OutOk "GET /api/public/coursewares/{id}       已注册" } else { OutWarn "公开课件详情未注册" }
} catch { OutWarn "openapi 拉取失败: $_" }

# ---- 8) 打印访问地址 ------------------------------------------------------
Write-Host ""
Write-Host "================ 部署完成 ================" -ForegroundColor Green
Write-Host "  前台首页    :  http://localhost:5173/" -ForegroundColor White
Write-Host "  后台登录    :  http://localhost:5173/admin   (token=demo)" -ForegroundColor White
Write-Host "  后端 API    :  http://localhost:8000/api/docs" -ForegroundColor White
Write-Host "  后端 health :  http://localhost:8000/api/public/health" -ForegroundColor White
Write-Host "  PostgreSQL  :  localhost:5432   (lh / lh / learning_hub)" -ForegroundColor White
Write-Host ""
Write-Host "  已就绪素材 (共 7 个):" -ForegroundColor White
Write-Host "    PDF  : id=1 (231KB) | id=9 (9.5MB)" -ForegroundColor Gray
Write-Host "    MP4  : id=5 (46MB)  | id=10 (180MB)" -ForegroundColor Gray
Write-Host "    PPTX : id=6 (81KB)  | id=7 (973KB) | id=8 (64MB)" -ForegroundColor Gray
Write-Host "  课件 id=12 (RESTRICTED)  Token id=3" -ForegroundColor Gray
Write-Host ""
Write-Host "  查看日志:  docker -H npipe:////./pipe/docker_engine compose -p $ProjectName logs -f backend" -ForegroundColor DarkGray
Write-Host "  关停服务:  docker -H npipe:////./pipe/docker_engine compose -p $ProjectName down" -ForegroundColor DarkGray
Write-Host "==========================================" -ForegroundColor Green
