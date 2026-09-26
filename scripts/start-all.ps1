<#
  启动全部服务.ps1 —— AI 模拟面试系统 · 本地开发一键启动

  由「启动全部服务.bat」调用（双击即可）。按依赖顺序点火六件事：
    [1] PostgreSQL  5432  Windows 服务，开机一般自启 → 只做检查
    [2] Docker Desktop   没开就开，等它就绪（30~60 秒，Redis 住在里面）
    [3] Redis       6379  容器不在跑就 docker start
    [4] 后端        8000  uvicorn（带 --reload：改代码自动重启）
    [5] Celery worker     批量导入的向量化 / 邮件，靠它消费队列
    [6] 两个前端    5173 用户端 + 3001 管理端

  设计要点：**每个长驻服务各占一个窗口**——它们是长驻进程，
  串在同一个窗口里第一个就会把后面的全挡住。所以本脚本只负责"点火"，
  点完火回到本窗口做验证、打印汇总。

  已经在跑的端口会自动跳过（不会重复起，也不会报 10048 端口占用）。
#>

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Root      = Split-Path -Parent $PSScriptRoot          # scripts\ 的上一级 = 项目根
$Backend   = Join-Path $Root 'backend'
$Frontend  = Join-Path $Root 'frontend'
$Admin     = Join-Path $Root 'admin'
$Python    = Join-Path $Root '.venv\Scripts\python.exe'
$DockerExe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
$PgService = 'postgresql-x64-17'
$Total     = 6


# ── 小工具 ────────────────────────────────────────────────────────────

function Write-Step([int]$n, [string]$text) {
    Write-Host ("[{0}/{1}] " -f $n, $Total) -NoNewline -ForegroundColor Cyan
    Write-Host $text -NoNewline
}

function Write-Ok([string]$msg)   { Write-Host " $msg" -ForegroundColor Green }
function Write-Warn2([string]$msg){ Write-Host " $msg" -ForegroundColor Yellow }
function Write-Bad([string]$msg)  { Write-Host " $msg" -ForegroundColor Red }
function Write-Note([string]$msg) { Write-Host "      $msg" -ForegroundColor DarkGray }

function Test-Port([int]$port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Port([int]$port, [int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Test-Docker {
    $null = & docker info 2>&1
    return ($LASTEXITCODE -eq 0)
}

# 在一个**新窗口**里跑一个长驻服务（title 方便在任务栏认人）
function Start-ServiceWindow([string]$title, [string]$workDir, [string]$command) {
    $line = "title $title && cd /d `"$workDir`" && $command"
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $line | Out-Null
}


# ── 开场 ──────────────────────────────────────────────────────────────

Write-Host ''
Write-Host '══════ AI 模拟面试系统 · 一键启动 ══════' -ForegroundColor White
Write-Host "项目根目录：$Root" -ForegroundColor DarkGray
Write-Host ''

$problems = @()


# ── [1/6] PostgreSQL ─────────────────────────────────────────────────

Write-Step 1 'PostgreSQL 5432'
if (Test-Port 5432) {
    Write-Ok '已在运行 ✓'
} else {
    Write-Warn2 '没在运行，尝试启动 Windows 服务…'
    try {
        Start-Service -Name $PgService -ErrorAction Stop
        if (Wait-Port 5432 20) { Write-Ok '已启动 ✓' }
        else { Write-Bad '启动了但端口没通'; $problems += 'PostgreSQL 起来了但端口 5432 没监听' }
    } catch {
        Write-Bad "启动失败：$($_.Exception.Message)"
        Write-Note "多半是权限不够。手动开：Win+R → services.msc → 找 $PgService → 右键启动"
        $problems += 'PostgreSQL 没起来（数据库连不上，后端会 500）'
    }
}


# ── [2/6] Docker Desktop ─────────────────────────────────────────────

Write-Step 2 'Docker Desktop'
if (Test-Docker) {
    Write-Ok '已就绪 ✓'
} else {
    Write-Warn2 '没就绪，正在启动（首次约 30~60 秒）…'
    if (Test-Path $DockerExe) {
        Start-Process -FilePath $DockerExe | Out-Null
        $ready = $false
        for ($i = 0; $i -lt 60; $i++) {          # 最多等 120 秒
            Start-Sleep -Seconds 2
            if (Test-Docker) { $ready = $true; break }
            Write-Host '.' -NoNewline -ForegroundColor DarkGray
        }
        if ($ready) { Write-Ok '已就绪 ✓' }
        else {
            Write-Bad '等了 120 秒还没就绪'
            Write-Note '手动确认：右下角鲸鱼图标变绿 → 再跑一次本脚本'
            $problems += 'Docker Desktop 没就绪（Redis 起不来 → 向量化/邮件会挂队列）'
        }
    } else {
        Write-Bad "找不到 Docker Desktop：$DockerExe"
        $problems += 'Docker Desktop 没装或路径变了'
    }
}


# ── [3/6] Redis ──────────────────────────────────────────────────────

Write-Step 3 'Redis 6379'
if (Test-Port 6379) {
    Write-Ok '已在运行 ✓'
} elseif (Test-Docker) {
    # 容器存在就 start，不存在（被删过）才重建
    $exists = & docker ps -a --filter 'name=^redis$' --format '{{.Names}}' 2>$null
    if ($exists) {
        Write-Host ' 容器未运行，docker start…' -NoNewline -ForegroundColor DarkGray
        & docker start redis | Out-Null
    } else {
        Write-Host ' 容器不存在，新建…' -NoNewline -ForegroundColor DarkGray
        & docker run -d --name redis -p 6379:6379 docker.m.daocloud.io/library/redis:7-alpine | Out-Null
    }
    if (Wait-Port 6379 20) {
        $pong = & docker exec redis redis-cli ping 2>$null
        if ($pong -match 'PONG') { Write-Ok '已启动 ✓ PONG' } else { Write-Ok '已启动 ✓' }
    } else {
        Write-Bad '容器起了但端口 6379 不通'
        $problems += 'Redis 没起来（批量导入的向量化、邮件会挂队列）'
    }
} else {
    Write-Bad '跳过了：Docker 没就绪'
    $problems += 'Redis 没起来（批量导入的向量化、邮件会挂队列）'
}


# ── [4/6] 后端 8000 ──────────────────────────────────────────────────

Write-Step 4 '后端 8000'
if (Test-Port 8000) {
    Write-Ok '已在运行，跳过 ✓'
} else {
    # --reload：改完代码自动重启（省掉"代码是新的、进程里是旧的"那个坑）
    Start-ServiceWindow '后端 8000' $Backend "`"$Python`" -m uvicorn main:app --port 8000 --reload"
    Write-Ok '已开窗口启动'
}


# ── [5/6] Celery worker ──────────────────────────────────────────────

Write-Step 5 'Celery worker'
$workerRunning = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
                 Where-Object { $_.CommandLine -match 'celery' }
if ($workerRunning) {
    Write-Ok '已在运行，跳过 ✓'
} else {
    # Windows 必须 --pool=solo（没有 fork 系统调用，默认 prefork 会报错）
    Start-ServiceWindow 'Celery worker' $Backend "`"$Python`" -m celery -A app.core.celery_app worker --pool=solo -l info"
    Write-Ok '已开窗口启动'
}


# ── [6/6] 两个前端 ───────────────────────────────────────────────────

Write-Step 6 '两个前端'
$feStarted = @()
if (Test-Port 5173) { Write-Host ' 用户端已在运行；' -NoNewline -ForegroundColor DarkGray }
else { Start-ServiceWindow '用户端 5173' $Frontend 'npm run dev'; $feStarted += '5173' }
if (Test-Port 3001) { Write-Host ' 管理端已在运行' -NoNewline -ForegroundColor DarkGray }
else { Start-ServiceWindow '管理端 3001' $Admin 'npm run dev'; $feStarted += '3001' }
Write-Ok '已处理 ✓'


# ── 收尾：等后端就绪 + 健康检查 ──────────────────────────────────────

Write-Host ''
Write-Host '正在等各服务就绪…' -ForegroundColor DarkGray
$null = Wait-Port 8000 60
$null = Wait-Port 5173 90
$null = Wait-Port 3001 90

Write-Host ''
Write-Host '════════════ 访问地址 ════════════' -ForegroundColor White

# 后端：健康检查（redis down 时返回 503，所以要 try/catch）
$apiState = '未就绪'
if (Test-Port 8000) {
    try {
        $r = Invoke-RestMethod 'http://localhost:8000/api/v1/config/health' -TimeoutSec 5
        $apiState = '正常'
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            $apiState = '端口通但健康检查失败（多半是 Redis 没起，业务仍可用）'
        } else {
            $apiState = '端口通，健康检查没响应'
        }
    }
}

function Show-Addr([string]$name, [int]$port, [string]$url, [string]$extra) {
    if (Test-Port $port) {
        Write-Host '  ✓ ' -NoNewline -ForegroundColor Green
        Write-Host ("{0,-12}" -f $name) -NoNewline
        Write-Host $url -NoNewline -ForegroundColor Cyan
        if ($extra) { Write-Host "   $extra" -ForegroundColor DarkGray } else { Write-Host '' }
    } else {
        Write-Host '  ✗ ' -NoNewline -ForegroundColor Red
        Write-Host ("{0,-12}" -f $name) -NoNewline
        Write-Host "$url   （没起来，看它那个窗口的报错）" -ForegroundColor DarkGray
    }
}

Show-Addr '后端'    8000 'http://localhost:8000'            $apiState
Show-Addr '用户端'  5173 'http://localhost:5173'            'stream_1787556246@test.com / test123456'
Show-Addr '管理端'  3001 'http://localhost:3001'            'a@new.com / 123456'
Show-Addr 'Redis'   6379 'localhost:6379'                   'Celery 的队列'
Show-Addr 'PostgreSQL' 5432 'localhost:5432'                '本地库（524 题）'

if ($problems.Count -gt 0) {
    Write-Host ''
    Write-Host '⚠ 有服务没起来：' -ForegroundColor Yellow
    foreach ($p in $problems) { Write-Host "   · $p" -ForegroundColor Yellow }
}

Write-Host ''
Write-Host '提示：' -ForegroundColor DarkGray
Write-Note '各服务跑在各自的窗口里，关掉那个窗口 = 停掉那个服务'
Write-Note '要一键全停：双击「停止全部服务.bat」'
Write-Note '改了后端代码不用手动重启（--reload 会自己重载）；但改了 Celery 任务代码要重启 worker 窗口'
Write-Host ''
