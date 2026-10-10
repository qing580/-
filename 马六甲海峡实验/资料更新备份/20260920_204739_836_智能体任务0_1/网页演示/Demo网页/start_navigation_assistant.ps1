param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$demoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pageSegments = @("海上异常监测智能体.html")
$encodedPage = ($pageSegments | ForEach-Object { [Uri]::EscapeDataString($_) }) -join "/"

$pythonCandidates = @(
    "C:\Users\卿之ya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $pythonCandidates += $pythonCommand.Source
}
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) {
    throw "未找到可用的 Python。请先按项目环境说明恢复 Python 运行时。"
}

function Test-LocalPortFree {
    param([int]$CandidatePort)
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $CandidatePort)
    try {
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

$selectedPort = $null
foreach ($candidate in $Port..($Port + 20)) {
    if (Test-LocalPortFree -CandidatePort $candidate) {
        $selectedPort = $candidate
        break
    }
}
if (-not $selectedPort) {
    throw "端口 $Port 至 $($Port + 20) 均被占用。"
}

$server = Start-Process -FilePath $python `
    -ArgumentList @("-m", "http.server", $selectedPort, "--bind", "127.0.0.1") `
    -WorkingDirectory $demoRoot `
    -WindowStyle Hidden `
    -PassThru

$rootUrl = "http://127.0.0.1:$selectedPort/"
$pageUrl = "$rootUrl$encodedPage"
$ready = $false
try {
    for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
        if ($server.HasExited) {
            throw "本地地图服务启动失败，退出码：$($server.ExitCode)。"
        }
        try {
            Invoke-WebRequest -Uri $rootUrl -UseBasicParsing -TimeoutSec 1 | Out-Null
            $ready = $true
            break
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $ready) {
        throw "本地地图服务未在预期时间内响应。"
    }

    Write-Host "海上异常监测智能体已启动：$pageUrl" -ForegroundColor Green
    Write-Host "请保留此窗口。按 Ctrl+C 可停止本地服务。" -ForegroundColor Yellow
    Start-Process $pageUrl
    Wait-Process -Id $server.Id
}
finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
}
