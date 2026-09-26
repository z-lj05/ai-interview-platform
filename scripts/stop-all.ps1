<#
  停止全部服务.ps1 —— 把「启动全部服务」点起来的服务全停掉

  由「停止全部服务.bat」调用（双击即可）。

  停什么、不停什么：
    停：后端 8000 / Celery worker / 用户端 5173 / 管理端 3001 / Redis 容器
    不停：PostgreSQL（Windows 服务，停了别的程序也可能要用，且它开机自启）
          Docker Desktop（它是个大应用，关不关你自己决定）

  三个技术点（都是踩出来的）：

  ① **按端口找 + 按命令行找，两者配合**
     后端/两个前端有监听端口，一找一个准；但 Celery worker 不占端口，
     uvicorn 的 reloader 父进程也不占端口——只能靠 CommandLine 认人。

  ② **必须杀进程树（taskkill /T），不能只杀单个进程**
     uvicorn --reload 在 Windows 上是"父进程看门 + 用 multiprocessing 拉一个子进程
     跑真正的服务"。那个子进程的命令行是
       python -c "from multiprocessing.spawn import spawn_main; ..." --multiprocessing-fork
     ——**里面没有 "uvicorn" 这个词**，按命令行特征根本认不出它。
     如果只杀父进程（不带 /T），子进程就变成孤儿继续占着端口，
     下次启动直接撞 [Errno 10048] 端口占用。带 /T 一起带走，从根上不产生孤儿。

  ③ **最后一定要验端口，不能"报了已停止"就算完**
     Stop-Process / docker stop 都是**动作**，端口空出来才是**结果**，
     两者之间 Windows 有几百毫秒到几秒的延迟（释放监听套接字要时间）。
     所以收尾轮询等端口真空出来，而不是睡 2 秒就断言。
#>

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Total = 5
$stopped = @()

function Write-Step([int]$n, [string]$text) {
    Write-Host ("[{0}/{1}] " -f $n, $Total) -NoNewline -ForegroundColor Cyan
    Write-Host $text -NoNewline
}
function Write-Ok([string]$m)   { Write-Host " $m" -ForegroundColor Green }
function Write-Dim2([string]$m) { Write-Host " $m" -ForegroundColor DarkGray }

function Test-Port([int]$port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Get-PortPids([int]$port) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

# 按命令行特征找进程（celery / uvicorn 的关键补充：它们不占端口）
function Get-CmdlinePids([string]$pattern) {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match $pattern } |
        Select-Object -ExpandProperty ProcessId
}

# 杀**进程树**（/T = 连子进程一起），不是杀单个进程——见文件头 ②
function Stop-Tree($pids) {
    $killed = 0
    foreach ($procId in $pids) {
        if (-not $procId) { continue }
        $null = & taskkill /PID $procId /T /F 2>&1
        if ($LASTEXITCODE -eq 0) { $killed++ }
    }
    return $killed
}

Write-Host ''
Write-Host '══════ AI 模拟面试系统 · 一键停止 ══════' -ForegroundColor White

# ── [1/5] 后端 8000 ─────────────────────────────────────────────────
# 先杀命令行带 uvicorn 的（含 reloader 父进程），再杀占着 8000 的（兜底）
Write-Step 1 '后端 8000'
$n = Stop-Tree (Get-CmdlinePids 'uvicorn')
$n += Stop-Tree (Get-PortPids 8000)
if ($n -gt 0) { $stopped += '后端'; Write-Ok "已停止（$n 个进程树）" } else { Write-Dim2 '本来就没在跑' }

# ── [2/5] Celery worker（不占端口，只认命令行）──────────────────────
Write-Step 2 'Celery worker'
$n = Stop-Tree (Get-CmdlinePids 'celery')
if ($n -gt 0) { $stopped += 'Celery worker'; Write-Ok "已停止（$n 个进程树）" } else { Write-Dim2 '本来就没在跑' }

# ── [3/5] 用户端 5173 ───────────────────────────────────────────────
Write-Step 3 '用户端 5173'
$n = Stop-Tree (Get-PortPids 5173)
if ($n -gt 0) { $stopped += '用户端'; Write-Ok '已停止' } else { Write-Dim2 '本来就没在跑' }

# ── [4/5] 管理端 3001 ───────────────────────────────────────────────
Write-Step 4 '管理端 3001'
$n = Stop-Tree (Get-PortPids 3001)
if ($n -gt 0) { $stopped += '管理端'; Write-Ok '已停止' } else { Write-Dim2 '本来就没在跑' }

# ── [5/5] Redis 容器 ────────────────────────────────────────────────
Write-Step 5 'Redis 容器'
$null = & docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Dim2 'Docker 没在跑，Redis 自然也没跑'
} else {
    $running = & docker ps --filter 'name=^redis$' --format '{{.Names}}' 2>$null
    if ($running) {
        & docker stop redis | Out-Null
        $stopped += 'Redis'
        Write-Ok '已停止（容器还在，下次 docker start 秒起）'
    } else {
        Write-Dim2 '本来就没在跑'
    }
}

# ── 收尾：轮询等端口**真的**空出来（见文件头 ③）────────────────────

Write-Host ''
Write-Host '正在确认端口已释放…' -ForegroundColor DarkGray

$watch = [ordered]@{ 8000 = '后端'; 5173 = '用户端'; 3001 = '管理端'; 6379 = 'Redis' }
$stillOpen = @()
for ($i = 0; $i -lt 20; $i++) {           # 最多等 10 秒
    $stillOpen = @()
    foreach ($p in $watch.Keys) {
        if (Test-Port $p) { $stillOpen += "$($watch[$p]) $p" }
    }
    if ($stillOpen.Count -eq 0) { break }
    Start-Sleep -Milliseconds 500
}

Write-Host ''
if ($stopped.Count -gt 0) {
    Write-Host "已停：$($stopped -join '、')" -ForegroundColor Green
} else {
    Write-Host '没有任何服务在跑。' -ForegroundColor DarkGray
}

if ($stillOpen.Count -gt 0) {
    Write-Host "⚠ 这些端口还占着：$($stillOpen -join '、')" -ForegroundColor Yellow
    Write-Dim2 '再跑一次本脚本；还不行就看谁占的：netstat -ano | findstr :8000'
} else {
    Write-Host '端口全部已释放 ✓' -ForegroundColor Green
}

# 顺手报一下漏网的孤儿 python（multiprocessing 子进程，父进程死了它还在）
$orphans = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
           Where-Object { $_.CommandLine -match 'multiprocessing.spawn' }
if ($orphans) {
    Write-Host ''
    Write-Host "⚠ 还有 $($orphans.Count) 个孤儿 python 进程（父进程已死、自己不占端口）：" -ForegroundColor Yellow
    Write-Dim2 '   多半是 uvicorn --reload 的 multiprocessing 子进程残留，杀法：'
    Write-Dim2 ('   taskkill /PID ' + (($orphans | Select-Object -ExpandProperty ProcessId) -join ' /PID ') + ' /T /F')
}

Write-Host ''
Write-Host '说明：' -ForegroundColor DarkGray
Write-Dim2 'PostgreSQL 没停（Windows 服务，开机自启，停了别的程序也可能要用）'
Write-Dim2 'Docker Desktop 没关（要关自己从右下角托盘退出）'
Write-Dim2 '各服务那个 cmd 窗口还开着（进程没了，窗口可以手动关，或直接不管）'
Write-Host ''
