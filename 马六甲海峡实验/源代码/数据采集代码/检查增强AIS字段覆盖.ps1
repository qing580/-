param(
    [Parameter(Mandatory = $true)]
    [string]$InputCsv
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $InputCsv)) {
    throw "Input file not found: $InputCsv"
}

$rows = @(Import-Csv -LiteralPath $InputCsv)
if ($rows.Count -eq 0) {
    Write-Output "No data rows in input file."
    exit 0
}

function HasValue($value) {
    return $null -ne $value -and "$value".Trim() -ne ""
}

$fields = @(
    "mmsi",
    "lat",
    "lon",
    "sog",
    "cog",
    "true_heading",
    "rate_of_turn",
    "navigational_status",
    "vessel_name",
    "call_sign",
    "imo",
    "vessel_type",
    "destination",
    "draught",
    "ship_length",
    "ship_width",
    "raw_json"
)

Write-Output "=== Enhanced AIS field coverage check ==="
Write-Output "File: $InputCsv"
Write-Output "Rows: $($rows.Count)"
Write-Output ""

Write-Output "=== Message type counts ==="
$rows |
    Group-Object message_type |
    Sort-Object Count -Descending |
    ForEach-Object {
        "{0,-34} {1,8}" -f $_.Name, $_.Count
    }

Write-Output ""
Write-Output "=== Non-empty field coverage ==="
foreach ($field in $fields) {
    $count = @($rows | Where-Object { HasValue $_.$field }).Count
    $rate = $count / $rows.Count
    "{0,-22} {1,8} / {2,-8} {3,7:P2}" -f $field, $count, $rows.Count, $rate
}

Write-Output ""
Write-Output "=== Unique MMSI and static coverage ==="
$uniqueMmsi = @($rows | Where-Object { HasValue $_.mmsi } | Select-Object -ExpandProperty mmsi -Unique)
$mmsiWithType = @($rows | Where-Object { (HasValue $_.mmsi) -and (HasValue $_.vessel_type) } | Select-Object -ExpandProperty mmsi -Unique)
$mmsiWithName = @($rows | Where-Object { (HasValue $_.mmsi) -and (HasValue $_.vessel_name) } | Select-Object -ExpandProperty mmsi -Unique)
$mmsiWithSize = @($rows | Where-Object { (HasValue $_.mmsi) -and ((HasValue $_.ship_length) -or (HasValue $_.ship_width)) } | Select-Object -ExpandProperty mmsi -Unique)

"Unique MMSI: {0}" -f $uniqueMmsi.Count
"MMSI with vessel_type: {0}" -f $mmsiWithType.Count
"MMSI with vessel_name: {0}" -f $mmsiWithName.Count
"MMSI with ship_length or ship_width: {0}" -f $mmsiWithSize.Count

Write-Output ""
Write-Output "=== Initial decision hint ==="
if ($mmsiWithType.Count -eq 0 -and $mmsiWithSize.Count -eq 0) {
    Write-Output "WARNING: No vessel_type or size fields were captured. Do not start long model-data collection yet."
} elseif ($mmsiWithType.Count / [Math]::Max(1, $uniqueMmsi.Count) -lt 0.3) {
    Write-Output "LOW COVERAGE: vessel_type coverage is low. A 6-hour comparison may help, but external verification is still needed."
} else {
    Write-Output "USABLE COVERAGE: vessel_type coverage is initially usable. Next step: run a 6-hour comparison and verify labels."
}
