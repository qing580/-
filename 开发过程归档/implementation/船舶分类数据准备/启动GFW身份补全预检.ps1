param(
    [switch]$Execute,
    [int]$Limit = 20
)

$ErrorActionPreference = "Stop"

if ($Limit -lt 1) { throw "Limit must be at least 1." }

$python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$client = Join-Path $PSScriptRoot "gfw_vessel_enrichment.py"

$manifestCandidates = @(
    Get-ChildItem -LiteralPath $projectRoot -Filter "vessel_query_manifest.csv" -File -Recurse -ErrorAction SilentlyContinue
)
if ($manifestCandidates.Count -ne 1) {
    throw "Expected exactly one vessel_query_manifest.csv under project root, found $($manifestCandidates.Count)."
}
$manifest = $manifestCandidates[0].FullName
$resultRoot = Split-Path $manifestCandidates[0].DirectoryName -Parent
$pilotCandidates = @(
    Get-ChildItem -LiteralPath $resultRoot -Filter "gfw_pilot_sample.csv" -File -Recurse -ErrorAction SilentlyContinue
)
$outputDir = if ($pilotCandidates.Count -ge 1) {
    $pilotCandidates[0].DirectoryName
} else {
    Join-Path $resultRoot "GFW_identity_pilot_2026-09-15"
}

if (-not (Test-Path -LiteralPath $python)) { throw "Python not found: $python" }
if (-not (Test-Path -LiteralPath $client)) { throw "GFW client not found: $client" }

Write-Host "=== GFW vessel identity pilot ==="
Write-Host "Manifest: $manifest"
Write-Host "Output: $outputDir"
Write-Host "Pilot vessels: $Limit"

$arguments = @(
    $client,
    "--manifest", $manifest,
    "--output-dir", $outputDir,
    "--limit", $Limit
)

if ($Execute) {
    if (-not $env:GFW_API_TOKEN) {
        $secret = Read-Host "Enter your personal GFW API token (hidden)" -AsSecureString
        $credential = New-Object System.Management.Automation.PSCredential("GFW", $secret)
        $env:GFW_API_TOKEN = $credential.GetNetworkCredential().Password
        Remove-Variable secret, credential
    }
    $arguments += "--execute"
    Write-Host "Online pilot enabled. Raw responses will be cached locally."
} else {
    Write-Host "Preparation only. No external API requests will be made."
}

& $python -u @arguments
$exitCode = $LASTEXITCODE
Remove-Item Env:GFW_API_TOKEN -ErrorAction SilentlyContinue
if ($exitCode -ne 0) { exit $exitCode }

Write-Host "Done. Review gfw_pilot_summary.json before any full-manifest run."
