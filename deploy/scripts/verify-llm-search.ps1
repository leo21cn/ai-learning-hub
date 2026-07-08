<#
.SYNOPSIS
  Learning Hub v1.1 LLM-to-SQL 端到端验证脚本（PowerShell 原生）。

.DESCRIPTION
  覆盖三步闭环：
    1. 后端单元测试：pytest tests/test_llm_sql.py + tests/test_search_llm.py
    2. 手工 curl 搜索：docker compose up → /api/public/coursewares/search
    3. Playwright e2e：front-search-llm.spec.ts F-007/008/009

  关键安全约束：
    - DASHSCOPE_API_KEY 仅从 backend/.env 读取，不入仓（已 gitignore）
    - 脚本运行时不打印 key 任何字符
    - LLM_SQL_TIMEOUT_SECONDS=8 兜底超时；超时 / 失败 → 走 ILIKE 降级

.NOTES
  使用方式（Windows PowerShell，cwd = repo 根）:
    powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\scripts\verify-llm-search.ps1 -Step all
    powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\scripts\verify-llm-search.ps1 -Step test
    powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\scripts\verify-llm-search.ps1 -Step smoke
    powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\scripts\verify-llm-search.ps1 -Step e2e
#>

[CmdletBinding()]
param(
    [ValidateSet('all', 'test', 'smoke', 'e2e', 'env')]
    [string]$Step = 'all',

    [string]$BackendDir = '.\backend',
    [string]$FrontendDir = '.\frontend',
    [string]$DeployDir = '.\deploy'
)

$ErrorActionPreference = 'Stop'
# 仓库根 = 脚本所在目录的 ../..（脚本位于 deploy/scripts/）
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -Path $RepoRoot
Write-Host "[init] cwd = $RepoRoot" -ForegroundColor DarkGray

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  [ERR] $msg" -ForegroundColor Red }

# ====== 步骤 0: 环境就绪检查 ======
function Test-Env {
    Write-Step "环境就绪检查"
    $envFile = Join-Path $BackendDir '.env'
    if (-not (Test-Path $envFile)) {
        Write-Err "未找到 $envFile。请先 `cp backend/.env.example backend/.env` 后填入 DASHSCOPE_API_KEY。"
        exit 1
    }
    $content = Get-Content $envFile -Raw
    if ($content -notmatch 'DASHSCOPE_API_KEY=sk-') {
        Write-Warn "$envFile 中 DASHSCOPE_API_KEY 未设置（仅注释或空），走降级路径"
    } else {
        Write-Ok "$envFile 中 DASHSCOPE_API_KEY 已配置（值已隐藏）"
    }
    foreach ($tool in 'docker', 'python') {
        $cmd = Get-Command $tool -ErrorAction SilentlyContinue
        if ($cmd) { Write-Ok "$tool 已安装: $($cmd.Source)" }
        else { Write-Warn "$tool 未在 PATH 中找到" }
    }
}

# ====== 步骤 1: pytest 后端单元测试 ======
function Invoke-Pytest {
    Write-Step "pytest 后端单元测试（test_llm_sql + test_search_llm）"
    Push-Location $BackendDir
    try {
        # 测试用 SQLite 内存（conftest.py 自动覆盖 DATABASE_URL），无需 PostgreSQL
        python -m pytest tests/test_llm_sql.py tests/test_search_llm.py -v --tb=short
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "pytest 通过"
        } else {
            Write-Err "pytest 失败 (exit=$LASTEXITCODE)"
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }
}

# ====== 步骤 2: docker compose 启动 + 手工 curl ======
function Invoke-Smoke {
    Write-Step "docker compose up -d --build（postgres + backend + frontend）"
    Push-Location $DeployDir
    try {
        docker compose up -d --build
        if ($LASTEXITCODE -ne 0) { Write-Err "docker compose 启动失败"; exit $LASTEXITCODE }
        Write-Ok "容器已启动，等待 backend & frontend healthy..."
        for ($i = 0; $i -lt 60; $i++) {
            $backendStatus = (docker inspect -f '{{.State.Health.Status}}' lh-backend 2>$null) -join ''
            $frontendStatus = (docker inspect -f '{{.State.Health.Status}}' lh-frontend 2>$null) -join ''
            if ($backendStatus -eq 'healthy' -and $frontendStatus -eq 'healthy') {
                Write-Ok "lh-backend healthy · lh-frontend healthy"
                break
            }
            Start-Sleep -Seconds 2
        }
        if ($backendStatus -ne 'healthy') { Write-Warn "lh-backend 未在 120s 内 healthy（status=$backendStatus）" }
        if ($frontendStatus -ne 'healthy') { Write-Warn "lh-frontend 未在 120s 内 healthy（status=$frontendStatus）" }

        # ===== 手工 curl（避免 PowerShell 5.1 不支持 -TimeoutSec）=====
        function Invoke-RestWithTimeout {
            param([string]$Uri, [int]$TimeoutSec = 15)
            try {
                # PowerShell 7+ 原生支持；5.1 退到 .NET HttpClient
                if ($PSVersionTable.PSVersion.Major -ge 7) {
                    return Invoke-RestMethod -Uri $Uri -TimeoutSec $TimeoutSec
                } else {
                    $http = [System.Net.Http.HttpClient]::new()
                    $http.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)
                    $resp = $http.GetStringAsync($Uri).GetAwaiter().GetResult()
                    return ($resp | ConvertFrom-Json)
                }
            } catch {
                Write-Err "请求失败: $($_.Exception.Message)"
                return $null
            }
        }

        Write-Step "验证 1: LLM 路径（长句）"
        $q1 = '帮我找一下与增量绩效相关的课件'
        $url1 = "http://localhost:8000/api/public/coursewares/search?q=$([uri]::EscapeDataString($q1))"
        $r1 = Invoke-RestWithTimeout -Uri $url1 -TimeoutSec 15
        if (-not $r1) { Write-Err "接口调用失败"; exit 1 }
        Write-Host "  data.source = $($r1.data.source)" -ForegroundColor Yellow
        if ($r1.data.source -eq 'llm') {
            Write-Ok "LLM 路径命中 qwen-plus NL2SQL（返回 $($r1.data.total) 条）"
        } elseif ($r1.data.source -eq 'keyword') {
            Write-Warn "降级到 ILIKE（可能 key 无效、LLM 调用失败或超时）；返回 $($r1.data.total) 条"
        } else {
            Write-Err "未知 source: $($r1.data.source)"; exit 1
        }

        Write-Step "验证 2: 降级路径（短关键词）"
        $q2 = '管理'
        $url2 = "http://localhost:8000/api/public/coursewares/search?q=$([uri]::EscapeDataString($q2))"
        $r2 = Invoke-RestWithTimeout -Uri $url2 -TimeoutSec 15
        if (-not $r2) { Write-Err "接口调用失败"; exit 1 }
        Write-Host "  data.source = $($r2.data.source)" -ForegroundColor Yellow
        Write-Host "  hits: $($r2.data.total) 条"
        Write-Ok "ILIKE 短关键词路径正常"

        Write-Step "验证 3: health check"
        $health = Invoke-RestWithTimeout -Uri 'http://localhost:8000/api/public/health' -TimeoutSec 5
        if ($health) {
            Write-Host "  $($health.data.status)" -ForegroundColor Yellow
        } else {
            Write-Warn "health 接口未返回（可能在启动中）"
        }
    } finally {
        Pop-Location
    }
}

# ====== 步骤 3: Playwright e2e ======
function Invoke-Playwright {
    Write-Step "Playwright e2e（front-search-llm.spec.ts F-007/008/009）"
    # 前置：frontend 容器必须跑起来（已包含在 docker compose up）
    Push-Location $FrontendDir
    try {
        if (-not (Test-Path 'node_modules')) {
            Write-Warn "node_modules 不存在，执行 npm install..."
            npm install
        }
        # PLAYWRIGHT_DOWNLOAD_HOST 国内镜像加速（与 deploy/README §7.6 一致）
        $env:PLAYWRIGHT_DOWNLOAD_HOST = 'https://npmmirror.com/mirrors/playwright'
        # 仅装 chromium（避免装全部浏览器造成额外耗时）
        npx playwright install --with-deps chromium 2>$null
        npx playwright test e2e/front-search-llm.spec.ts --reporter=list
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Playwright e2e 通过"
        } else {
            Write-Err "Playwright e2e 失败 (exit=$LASTEXITCODE)"
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }
}

# ====== 主流程 ======
Test-Env

switch ($Step) {
    'env'  { return }
    'test' { Invoke-Pytest }
    'smoke' { Invoke-Smoke }
    'e2e'   { Invoke-Playwright }
    'all' {
        Invoke-Pytest
        Invoke-Smoke
        Invoke-Playwright
    }
}

Write-Step "全部验证完成"
Write-Host "  下一步可执行: docker compose -f deploy/docker-compose.yml logs backend" -ForegroundColor DarkGray
Write-Host "  收尾: docker compose -f deploy/docker-compose.yml down" -ForegroundColor DarkGray