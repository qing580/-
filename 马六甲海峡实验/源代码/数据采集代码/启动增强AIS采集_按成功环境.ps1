param(
    [ValidateSet("Preflight", "Formal")]
    [string]$Mode = "Preflight",
    [double]$Hours = 0,
    [string]$Bbox = "1.0,103.0,3.5,104.5",
    [string]$RegionId = "malacca_southeast_singapore_strait",
    [int]$PrintEvery = 1,
    [int]$FlushEvery = 1,
    [int]$IdleTimeout = 30,
    [switch]$SkipCumulativeAudit
)

$ErrorActionPreference = "Stop"

function Join-Chars([int[]]$Codes) {
    return -join ($Codes | ForEach-Object { [char]$_ })
}

if ($Hours -le 0) {
    $Hours = if ($Mode -eq "Preflight") { 1.0 / 6.0 } else { 6.0 }
}
if ($Hours -le 0) { throw "Hours must be positive." }
if ($FlushEvery -le 0) { throw "FlushEvery must be positive." }

$userProfile = $env:USERPROFILE
$legacyProject = Join-Path $userProfile "Documents\Codex\2026-08-09\ban\work\maritime-anomaly-agent"
$python = Join-Path $userProfile ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$deps = Join-Path $legacyProject ".local_pydeps_ws12"

$collectorScript = Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.py" |
    Where-Object { $_.Name -like "*AIS*" -and $_.Name -notlike "*audit*" -and $_.Length -gt 10000 } |
    Sort-Object Length -Descending |
    Select-Object -First 1 -ExpandProperty FullName
$batchAuditScript = Join-Path $PSScriptRoot "audit_malacca_collection_batch.py"
$cumulativeAuditScript = Get-ChildItem -LiteralPath (Split-Path $PSScriptRoot -Parent) -Filter "malacca_batch_audit.py" -File |
    Select-Object -First 1 -ExpandProperty FullName

$experimentFolder = Join-Chars @(0x9A6C, 0x516D, 0x7532, 0x6D77, 0x5CE1, 0x5B9E, 0x9A8C)
$rawFolder = Join-Chars @(0x539F, 0x59CB, 0x6570, 0x636E)
$resultsFolder = Join-Chars @(0x8FD0, 0x884C, 0x7ED3, 0x679C)
$desktopProject = Join-Path ([Environment]::GetFolderPath("Desktop")) $experimentFolder
$rawDir = Join-Path $desktopProject $rawFolder
$batchRoot = Join-Path $rawDir "batches"

Write-Host "=== Reusable Malacca AIS collector launcher ==="
Write-Host "Mode: $Mode"
Write-Host "Python: $python"
Write-Host "Dependency dir: $deps"
Write-Host "Collector: $collectorScript"
Write-Host "Batch audit: $batchAuditScript"

if (-not (Test-Path -LiteralPath $python)) { throw "Python not found: $python" }
if (-not (Test-Path -LiteralPath $deps)) { throw "Dependency dir not found: $deps" }
if (-not $collectorScript -or -not (Test-Path -LiteralPath $collectorScript)) { throw "Collector not found in: $PSScriptRoot" }
if (-not (Test-Path -LiteralPath $batchAuditScript)) { throw "Batch audit not found: $batchAuditScript" }

$env:PYTHONPATH = $deps
& $python -c "import websockets; print('websockets version:', websockets.__version__); print('module:', websockets.__file__); print('connect_available:', callable(getattr(websockets, 'connect', None)))"
if ($LASTEXITCODE -ne 0) { throw "websockets dependency check failed." }

if (-not $env:AISSTREAM_API_KEY) {
    $secret = Read-Host "Enter AISStream API Key (hidden)" -AsSecureString
    $credential = New-Object System.Management.Automation.PSCredential("AISStream", $secret)
    $env:AISSTREAM_API_KEY = $credential.GetNetworkCredential().Password
    Remove-Variable secret, credential
}

New-Item -ItemType Directory -Path $batchRoot -Force | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss_fff"
$hoursTag = ("{0:g}" -f $Hours).Replace(".", "p")
$modeTag = $Mode.ToLowerInvariant()
$batchId = "{0}_{1}h_{2}" -f $modeTag, $hoursTag, $stamp
$batchDir = Join-Path $batchRoot $batchId
if (Test-Path -LiteralPath $batchDir) { throw "Batch directory already exists: $batchDir" }
New-Item -ItemType Directory -Path $batchDir | Out-Null

$normalized = Join-Path $batchDir "normalized_events.csv"
$rawJsonl = Join-Path $batchDir "raw_events.jsonl"
$connections = Join-Path $batchDir "connection_events.csv"
$runtime = Join-Path $batchDir "batch_runtime.json"

Write-Host "Batch ID: $batchId"
Write-Host "Batch directory: $batchDir"
Write-Host "Normalized CSV: $normalized"
Write-Host "Raw JSONL: $rawJsonl"
Write-Host "Hours: $Hours"
Write-Host "Bbox: $Bbox"
Write-Host "Region ID: $RegionId"
Write-Host "Rows are flushed to CSV and JSONL during collection. Press Ctrl+C to stop."

& $python -u $collectorScript `
    --hours $Hours `
    --bbox $Bbox `
    --region-id $RegionId `
    --batch-id $batchId `
    --print-every $PrintEvery `
    --flush-every $FlushEvery `
    --idle-timeout $IdleTimeout `
    --output $normalized `
    --raw-output $rawJsonl `
    --connection-output $connections `
    --runtime-output $runtime
$collectorExit = $LASTEXITCODE

if (-not (Test-Path -LiteralPath $normalized)) {
    throw "Collector did not create normalized CSV. Exit code: $collectorExit"
}

$auditMode = $Mode.ToLowerInvariant()
Write-Host "=== Running batch quality audit ==="
& $python -u $batchAuditScript `
    --input $normalized `
    --raw-jsonl $rawJsonl `
    --connection-events $connections `
    --runtime $runtime `
    --mode $auditMode
$auditExit = $LASTEXITCODE
$qualityReport = Join-Path $batchDir "batch_quality_report.md"

Write-Host "Collector exit code: $collectorExit"
Write-Host "Audit report: $qualityReport"
if ($auditExit -ne 0) {
    Write-Host "QUALITY VERDICT: FAIL"
    Write-Host "Do not start or continue a long collection until failed checks are resolved."
    exit 2
}

Write-Host "QUALITY VERDICT: PASS"
if ($Mode -eq "Preflight") {
    Write-Host "Preflight passed. The next permitted command is:"
    Write-Host ('powershell -ExecutionPolicy Bypass -File "{0}" -Mode Formal -Hours 6 -PrintEvery 100 -FlushEvery 1' -f $PSCommandPath)
    exit 0
}

if (-not $SkipCumulativeAudit -and $cumulativeAuditScript -and (Test-Path -LiteralPath $cumulativeAuditScript)) {
    $inputs = @(
        Get-ChildItem -LiteralPath $rawDir -File -Filter "malacca_enhanced_ais_*.csv"
        Get-ChildItem -LiteralPath $batchRoot -Directory -Filter "formal_*" |
            ForEach-Object { Get-Item -LiteralPath (Join-Path $_.FullName "normalized_events.csv") -ErrorAction SilentlyContinue }
    ) | Where-Object { $_ -and $_.Exists } | Sort-Object FullName -Unique
    if ($inputs.Count -gt 0) {
        $resultRoot = Join-Path $desktopProject $resultsFolder
        $cumulativeOut = Join-Path $resultRoot ("Malacca_AIS_cumulative_audit_{0}" -f $stamp)
        $auditArgs = @($cumulativeAuditScript, "--output", $cumulativeOut, "--target-eligible", "500")
        foreach ($item in $inputs) {
            $auditArgs += @("--input", $item.FullName)
        }
        Write-Host "=== Running cumulative classification audit ==="
        & $python -u @auditArgs
        Write-Host "Cumulative audit output: $cumulativeOut"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Cumulative audit failed. Raw batch remains valid; inspect the cumulative audit error separately."
        }
    }
}

Write-Host "Formal batch completed and passed quality audit."
