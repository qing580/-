param(
    [double]$Hours = 0.5,
    [string]$Bbox = "1.0,103.0,3.5,104.5",
    [int]$PrintEvery = 1,
    [int]$FlushEvery = 1,
    [int]$IdleTimeout = 30,
    [switch]$NoCoverageCheck
)

$ErrorActionPreference = "Stop"

function Join-Chars([int[]]$Codes) {
    return -join ($Codes | ForEach-Object { [char]$_ })
}

$userProfile = $env:USERPROFILE
$project = Join-Path $userProfile "Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent"
$python = Join-Path $userProfile ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$deps = Join-Path $project ".local_pydeps_ws12"

$collectorScript = Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.py" |
    Where-Object { $_.Name -like "*AIS*" -and $_.Length -gt 10000 } |
    Sort-Object Length -Descending |
    Select-Object -First 1 -ExpandProperty FullName
$coverageScript = Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.ps1" |
    Where-Object { $_.FullName -ne $PSCommandPath -and $_.Name -like "*AIS*" } |
    Select-Object -First 1 -ExpandProperty FullName

$experimentFolder = Join-Chars @(0x9A6C, 0x516D, 0x7532, 0x6D77, 0x5CE1, 0x5B9E, 0x9A8C)
$rawFolder = Join-Chars @(0x539F, 0x59CB, 0x6570, 0x636E)
$rawDir = Join-Path ([Environment]::GetFolderPath("Desktop")) (Join-Path $experimentFolder $rawFolder)

Write-Host "=== Enhanced AIS collector launcher ==="
Write-Host "Python: $python"
Write-Host "Dependency dir: $deps"
Write-Host "Collector script: $collectorScript"

if (-not (Test-Path -LiteralPath $python)) { throw "Python not found: $python" }
if (-not (Test-Path -LiteralPath $deps)) { throw "Dependency dir not found: $deps" }
if (-not $collectorScript -or -not (Test-Path -LiteralPath $collectorScript)) {
    throw "Enhanced collector script not found in: $PSScriptRoot"
}

$env:PYTHONPATH = $deps
& $python -c "import websockets; print('websockets version:', websockets.__version__); print('module:', websockets.__file__); print('connect_available:', callable(getattr(websockets, 'connect', None)))"

if (-not $env:AISSTREAM_API_KEY) {
    $secret = Read-Host "Enter AISStream API Key (hidden)" -AsSecureString
    $credential = New-Object System.Management.Automation.PSCredential("AISStream", $secret)
    $env:AISSTREAM_API_KEY = $credential.GetNetworkCredential().Password
    Remove-Variable secret, credential
}

New-Item -ItemType Directory -Path $rawDir -Force | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss_fff"
$hoursTag = ("{0:g}" -f $Hours).Replace(".", "p")
$output = Join-Path $rawDir ("malacca_enhanced_ais_{0}h_{1}.csv" -f $hoursTag, $stamp)
if (Test-Path -LiteralPath $output) { throw "Output file already exists: $output" }

Write-Host "Output file: $output"
Write-Host "Hours: $Hours"
Write-Host "Bbox: $Bbox"
Write-Host "Print every rows: $PrintEvery"
Write-Host "Flush every rows: $FlushEvery"
Write-Host "Start collecting. row=N means one row has been received and written. Press Ctrl+C to stop."

& $python -u $collectorScript `
    --hours $Hours `
    --bbox $Bbox `
    --print-every $PrintEvery `
    --flush-every $FlushEvery `
    --idle-timeout $IdleTimeout `
    --output $output

Write-Host "Collector finished: $output"

if (-not $NoCoverageCheck) {
    if ($coverageScript -and (Test-Path -LiteralPath $coverageScript)) {
        powershell -ExecutionPolicy Bypass -File $coverageScript -InputCsv $output
    } else {
        Write-Host "Coverage checker not found in: $PSScriptRoot"
    }
}
