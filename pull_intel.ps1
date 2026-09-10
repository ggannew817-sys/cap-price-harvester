# CAP intel pull (local PC, no git). Downloads intel_daily.json from the PUBLIC repo.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$owner  = "ggannew817-sys"
$repo   = "cap-price-harvester"
$branch = "main"
$url = "https://raw.githubusercontent.com/$owner/$repo/$branch/intel_daily.json?t=" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$dst = Join-Path $PSScriptRoot "intel_daily.json"

try {
    Invoke-WebRequest -Uri $url -OutFile $dst -UseBasicParsing
} catch {
    Write-Host ("[FAIL] download error: " + $_.Exception.Message)
    Write-Host "       If HTTP 404 -> intel_daily.json not committed yet, or repo path wrong."
    exit 1
}
try {
    $j = Get-Content $dst -Raw -Encoding UTF8 | ConvertFrom-Json
    $n = @($j.items).Count
    if ($n -eq 0) { Write-Host "[WARN] file has 0 items"; exit 0 }
    Write-Host ("[OK] saved -> " + $dst)
    Write-Host ("     updated: " + $j.updated + " | items: " + $n)
} catch {
    Write-Host ("[FAIL] not valid JSON: " + $_.Exception.Message)
    exit 1
}
