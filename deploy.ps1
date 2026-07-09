# deploy.ps1
# Maakt een deployment-ZIP van het GMT Speeltuin project.
# De collega heeft alleen de ZIP + een .env-bestand nodig.
#
# Gebruik:
#   .\deploy.ps1
#   .\deploy.ps1 -OutputDir "C:\Users\jou\Desktop"

param(
    [string]$OutputDir = $PSScriptRoot
)

$scriptDir = $PSScriptRoot
$timestamp = Get-Date -Format "yyyyMMddHHmm"
$zipPath   = Join-Path $OutputDir "GMT-speeltuin-deploy-$timestamp.zip"

# ── Vaste bestanden ─────────────────────────────────────────────────────────
$fixedFiles = @(
    "index.html",
    "server.py",
    "requirements.txt",
    "start.bat",
    "update.bat",
    "default-gmt-env",
    "daylight.json",
    "holiday_indices.csv",
    "purpose_index.json",
    "ndw_traffic_signs.json",
    "download_traffic_sign_icons.py"
)

# ── Dynamisch: wheels en release-notes (versienummer kan wijzigen) ───────────
$dynamicFiles = @()
$dynamicFiles += Get-ChildItem -Path $scriptDir -Filter "*.whl"              -File | Select-Object -ExpandProperty Name
$dynamicFiles += Get-ChildItem -Path $scriptDir -Filter "release-notes-*.html" -File | Select-Object -ExpandProperty Name

# ── Mappen ───────────────────────────────────────────────────────────────────
$directories = @(
    "traffic_sign_icons",
    "buildings_fetcher",
    "traffic_signs_fetcher"
)

# ── Alles samenvoegen en controleren ─────────────────────────────────────────
$allItems = @($fixedFiles) + @($dynamicFiles) + @($directories)
$paths    = $allItems | ForEach-Object { Join-Path $scriptDir $_ } | Where-Object { Test-Path $_ }

if ($paths.Count -eq 0) {
    Write-Host "[ERROR] Geen bestanden gevonden om in te pakken." -ForegroundColor Red
    exit 1
}

# ── ZIP aanmaken ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Bestanden inpakken:" -ForegroundColor Cyan
$paths | ForEach-Object { Write-Host "  + $(Split-Path $_ -Leaf)" }

Compress-Archive -Path $paths -DestinationPath $zipPath -Force

$sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "[OK] Deployment-ZIP aangemaakt: $zipPath ($sizeMb MB)" -ForegroundColor Green
Write-Host ""
Write-Host "Instructies voor de collega:" -ForegroundColor Yellow
Write-Host "  1. ZIP uitpakken naar een map naar keuze"
Write-Host "  2. .env-bestand (met Databricks-credentials) in die map plaatsen"
Write-Host "  3. update.bat uitvoeren -> installeert alles en start de server"
Write-Host ""
