# deploy.ps1
# Maakt een deployment-ZIP van GMT Analyzer (analyzer/ + de gedeelde common/-map).
# De collega heeft alleen de ZIP + een .env-bestand nodig.
# Alles landt plat in één map (zoals voorheen) — common/py, common/js en
# common/data worden uitgepakt als gewone submappen/bestanden naast server.py.
#
# Gebruik:
#   .\deploy.ps1
#   .\deploy.ps1 -OutputDir "C:\Users\jou\Desktop"

param(
    [string]$OutputDir = $PSScriptRoot
)

$scriptDir = $PSScriptRoot
$repoRoot  = Split-Path $scriptDir -Parent
$timestamp = Get-Date -Format "yyyyMMddHHmm"
$zipPath   = Join-Path $OutputDir "GMT-analyzer-deploy-$timestamp.zip"

# ── Vaste bestanden (uit analyzer/) ──────────────────────────────────────────
$fixedFiles = @(
    "index.html",
    "server.py",
    "requirements.txt",
    "start.bat",
    "startDocker.bat",
    "Dockerfile",
    "wegenscan_pipeline.py",

    # Door index.html ingeladen.
    "measure-set-panel.js"
)

# ── Vaste bestanden op repo-niveau (gedeeld met digital-twin) ───────────────
$rootFixedFiles = @(
    ".dockerignore",
    "default-gmt-env"
)

# ── Gedeelde common/-data (plat uitgepakt naast server.py) ──────────────────
$commonDataFiles = @(
    "common/data/daylight.json",
    "common/data/holiday_indices.csv",
    "common/data/purpose_index.json"
)
# Door index.html ingeladen; zonder deze bestanden is de pagina (of Kaart 2) stuk.
$commonJsFiles = @("common/js/left-menu-panel.js", "common/js/montreal-basemap.js")

# ── Dynamisch: wheels en release-notes (versienummer kan wijzigen) ───────────
$dynamicFiles = @()
$dynamicFiles += Get-ChildItem -Path $repoRoot -Filter "*.whl"               -File | Select-Object -ExpandProperty Name
$dynamicFiles += Get-ChildItem -Path $repoRoot -Filter "release-notes-*.html" -File | Select-Object -ExpandProperty Name

# ── Mappen (analyzer/-mappen + gedeelde common/py-fetchers) ─────────────────
$directories = @(
    "svg"                    # pictogrammen die server.py en index.html opvragen
)
$rootDirectories = @(
    "common/py/buildings_fetcher",
    "common/data/traffic_sign_icons",
    "scripts"                # server.py importeert scripts.geofabrik_pbf (PBF-resolver)
)

# ── Alles samenvoegen en controleren ─────────────────────────────────────────
$missing = @()
$missing += $fixedFiles       | Where-Object { -not (Test-Path (Join-Path $scriptDir $_)) }
$missing += $directories      | Where-Object { -not (Test-Path (Join-Path $scriptDir $_)) }
$missing += $rootFixedFiles   | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }
$missing += $rootDirectories  | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }
$missing += $commonDataFiles  | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }
$missing += $commonJsFiles    | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }

# Losse bestanden gaan rechtstreeks de ZIP in.
$paths  = @($fixedFiles)     | ForEach-Object { Join-Path $scriptDir $_ } | Where-Object { Test-Path $_ }
$paths += @($rootFixedFiles) | ForEach-Object { Join-Path $repoRoot  $_ } | Where-Object { Test-Path $_ }
$paths += @($dynamicFiles)   | ForEach-Object { Join-Path $repoRoot  $_ } | Where-Object { Test-Path $_ }

# ── Mappen + gedeelde common/-bestanden via een staging-map ──────────────────
# Compress-Archive kan binnen een map niets uitsluiten, dus worden de mappen
# eerst gekopieerd en daar opgeschoond. Anders reizen __pycache__ en losse .pyc
# mee: rommel die de indruk wekt dat er gecompileerde bestanden bij horen, en
# die bij een afwijkende Python-versie alleen maar verwarring geeft.
# De common/-bestanden worden plat in de staging-map gekopieerd (basename
# zonder de common/py|js|data-prefix), zodat ze net als voorheen gewoon naast
# server.py/index.html komen te staan.
$stageDir = Join-Path ([System.IO.Path]::GetTempPath()) "gmt-deploy-$timestamp"
New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

foreach ($dir in $directories) {
    $src = Join-Path $scriptDir $dir
    if (-not (Test-Path $src)) { continue }
    Copy-Item $src $stageDir -Recurse -Force
    $paths += (Join-Path $stageDir $dir)
}

foreach ($dir in $rootDirectories) {
    $src = Join-Path $repoRoot $dir
    if (-not (Test-Path $src)) { continue }
    $destName = Split-Path $dir -Leaf
    Copy-Item $src (Join-Path $stageDir $destName) -Recurse -Force
    $paths += (Join-Path $stageDir $destName)
}

foreach ($f in (@($commonDataFiles) + @($commonJsFiles))) {
    $src = Join-Path $repoRoot $f
    if (-not (Test-Path $src)) { continue }
    $destName = Split-Path $f -Leaf
    Copy-Item $src (Join-Path $stageDir $destName) -Force
    $paths += (Join-Path $stageDir $destName)
}

# Eén opruimactie voor alles wat in de staging-map staat. `-Exclude` van
# Copy-Item filtert geen mappen, dus achteraf weggooien is de enige
# betrouwbare manier.
$purged = @(Get-ChildItem $stageDir -Recurse -Directory -Filter "__pycache__")
$purged | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $stageDir -Recurse -File -Include "*.pyc", "*.pyo" |
    Remove-Item -Force -ErrorAction SilentlyContinue

if ($paths.Count -eq 0) {
    Write-Host "[ERROR] Geen bestanden gevonden om in te pakken." -ForegroundColor Red
    exit 1
}

# ── ZIP aanmaken ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Bestanden inpakken:" -ForegroundColor Cyan
$paths | ForEach-Object { Write-Host "  + $(Split-Path $_ -Leaf)" }

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "[LET OP] Niet gevonden, dus NIET in de ZIP:" -ForegroundColor Yellow
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
}

if ($purged.Count -gt 0) {
    Write-Host ""
    Write-Host "  ($($purged.Count) x __pycache__ opgeruimd)" -ForegroundColor DarkGray
}

Compress-Archive -Path $paths -DestinationPath $zipPath -Force

if ($stageDir -and (Test-Path $stageDir)) {
    Remove-Item $stageDir -Recurse -Force
}

$sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "[OK] Deployment-ZIP aangemaakt: $zipPath ($sizeMb MB)" -ForegroundColor Green
Write-Host ""
Write-Host "Instructies voor de collega:" -ForegroundColor Yellow
Write-Host "  1. ZIP uitpakken naar een map naar keuze"
Write-Host "  2. .env-bestand (met Databricks-credentials) in die map plaatsen"
Write-Host "  3a. Zonder Docker : start.bat uitvoeren"
Write-Host "  3b. Met Docker    : startDocker.bat uitvoeren (Docker Desktop vereist)"
Write-Host ""
