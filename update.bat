@echo off
setlocal

set "VENV=%~dp0.venv\Scripts\activate.bat"

rem ── Detecteer Python-executable ─────────────────────────────────────────────
where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=py"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=python"
    ) else (
        echo [ERROR] Geen Python gevonden ^(py noch python^). Installeer Python en probeer opnieuw.
        exit /b 1
    )
)
echo [INFO] Python executable: %PYTHON%

rem ── Standaardwaarden ────────────────────────────────────────────────────────
set "WHEEL_DIR="
set "CODE_DIR="
set "BACKUP_DONE=0"

rem ── Lees .gmt-env als die bestaat ───────────────────────────────────────────
if exist "%~dp0.gmt-env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0.gmt-env") do (
        if /i "%%A"=="WHEEL_DIR" set "WHEEL_DIR=%%B"
        if /i "%%A"=="CODE_DIR"  set "CODE_DIR=%%B"
    )
) else (
    echo [WARN] .gmt-env niet gevonden, geen bronmappen ingesteld.
)

rem ── Wheel: gmt_calculation_lib ───────────────────────────────────────────────
if not defined WHEEL_DIR (
    echo [INFO] WHEEL_DIR niet ingesteld in .gmt-env, wheel-update overgeslagen.
    goto whatif_wheel_check
)
if not exist "%WHEEL_DIR%\" (
    echo [INFO] WHEEL_DIR niet bereikbaar ^(%WHEEL_DIR%^), wheel-update overgeslagen.
    goto whatif_wheel_check
)

set "WHEEL_FILE="
for /f "delims=" %%f in ('dir /b "%WHEEL_DIR%\gmt_calculation_lib-*.whl" 2^>nul') do set "WHEEL_FILE=%%f"
if not defined WHEEL_FILE (
    echo [WARN] Geen gmt_calculation_lib wheel gevonden in %WHEEL_DIR%
    goto whatif_wheel_check
)

set "SRC=%WHEEL_DIR%\%WHEEL_FILE%"
set "DST=%~dp0%WHEEL_FILE%"

if not exist "%DST%" (
    echo [INFO] Lokale gmt whl ontbreekt, kopieer en installeer...
    goto do_update_gmt
)

powershell -NoProfile -Command ^
    "if ((Get-Item '%SRC%').LastWriteTime -gt (Get-Item '%DST%').LastWriteTime) { exit 1 } else { exit 0 }"
if errorlevel 1 goto do_update_gmt
echo [INFO] gmt_calculation_lib whl is al up-to-date.
goto whatif_wheel_check

:do_update_gmt
call :make_backup
echo [INFO] Nieuwere gmt_calculation_lib module gevonden, installeren...
copy /Y "%SRC%" "%DST%" >nul
call "%VENV%"
%PYTHON% -m pip install --force-reinstall "%DST%"
if errorlevel 1 (
    echo [ERROR] Installatie gmt_calculation_lib mislukt.
    exit /b 1
)
echo [INFO] gmt_calculation_lib whl succesvol herinstalleerd.

rem ── Wheel: what_if_quick_scan ────────────────────────────────────────────────
:whatif_wheel_check
if not defined WHEEL_DIR goto code_check
if not exist "%WHEEL_DIR%\" goto code_check

set "WHATIF_WHEEL_FILE="
for /f "delims=" %%f in ('dir /b "%WHEEL_DIR%\what_if_quick_scan-*.whl" 2^>nul') do set "WHATIF_WHEEL_FILE=%%f"
if not defined WHATIF_WHEEL_FILE (
    echo [WARN] Geen what_if_quick_scan wheel gevonden in %WHEEL_DIR%
    goto code_check
)

set "WHATIF_SRC=%WHEEL_DIR%\%WHATIF_WHEEL_FILE%"
set "WHATIF_DST=%~dp0%WHATIF_WHEEL_FILE%"

if not exist "%WHATIF_DST%" (
    echo [INFO] Lokale what_if whl ontbreekt, kopieer en installeer...
    goto do_update_whatif
)

powershell -NoProfile -Command ^
    "if ((Get-Item '%WHATIF_SRC%').LastWriteTime -gt (Get-Item '%WHATIF_DST%').LastWriteTime) { exit 1 } else { exit 0 }"
if errorlevel 1 goto do_update_whatif
echo [INFO] what_if_quick_scan whl is al up-to-date.
goto code_check

:do_update_whatif
call :make_backup
echo [INFO] Nieuwere what_if_quick_scan module gevonden, installeren...
copy /Y "%WHATIF_SRC%" "%WHATIF_DST%" >nul
call "%VENV%"
%PYTHON% -m pip install --force-reinstall "%WHATIF_DST%"
if errorlevel 1 (
    echo [ERROR] Installatie what_if_quick_scan mislukt.
    exit /b 1
)
echo [INFO] what_if_quick_scan whl succesvol herinstalleerd.

rem ── Code (HTML + PY) ────────────────────────────────────────────────────────
:code_check
set "DO_CODE_COPY=0"
if not defined CODE_DIR goto start_server
if not exist "%CODE_DIR%\" (
    echo [INFO] CODE_DIR niet bereikbaar ^(%CODE_DIR%^), code-update overgeslagen.
    goto start_server
)

rem Vergelijk CODE_DIR met de scriptmap via PowerShell (padnormalisatie)
powershell -NoProfile -Command ^
    "if ([IO.Path]::GetFullPath('%CODE_DIR%') -ne [IO.Path]::GetFullPath('%~dp0'.TrimEnd('\'))){ exit 1 } else { exit 0 }"
if errorlevel 1 set "DO_CODE_COPY=1"
if "%DO_CODE_COPY%"=="0" goto start_server

set "SRC_HTML=%CODE_DIR%\index.html"
set "DST_HTML=%~dp0index.html"
set "SRC_PY=%CODE_DIR%\server.py"
set "DST_PY=%~dp0server.py"
set "SRC_REQ=%CODE_DIR%\requirements.txt"
set "DST_REQ=%~dp0requirements.txt"

:html_check
echo [INFO] HTML controleren...
powershell -NoProfile -Command ^
    "if ((Get-Item '%SRC_HTML%').LastWriteTime -gt (Get-Item '%DST_HTML%').LastWriteTime) { exit 1 } else { exit 0 }"
if errorlevel 1 goto do_update_html
echo [INFO] Lokale HTML is al up-to-date.

:py_check
echo [INFO] Python-bestand controleren...
powershell -NoProfile -Command ^
    "if ((Get-Item '%SRC_PY%').LastWriteTime -gt (Get-Item '%DST_PY%').LastWriteTime) { exit 1 } else { exit 0 }"
if errorlevel 1 goto do_update_py
echo [INFO] Lokale Python-bestand is al up-to-date.
goto requirements_check

:do_update_html
call :make_backup
echo [INFO] Nieuwere HTML gevonden, kopiëren...
copy /Y "%SRC_HTML%" "%DST_HTML%" >nul
if errorlevel 1 (
    echo [ERROR] Kopiëren HTML mislukt.
    exit /b 1
)
echo [INFO] HTML succesvol bijgewerkt.
goto py_check

:do_update_py
call :make_backup
echo [INFO] Nieuwer Python-bestand gevonden, kopiëren...
copy /Y "%SRC_PY%" "%DST_PY%" >nul
if errorlevel 1 (
    echo [ERROR] Kopiëren server.py mislukt.
    exit /b 1
)
echo [INFO] Python-bestand succesvol bijgewerkt.

:requirements_check
if not exist "%SRC_REQ%" (
    echo [INFO] requirements.txt niet gevonden in CODE_DIR, overgeslagen.
    goto data_files_check
)
echo [INFO] requirements.txt controleren...
powershell -NoProfile -Command ^
    "$s='%SRC_REQ%'; $d='%DST_REQ%';" ^
    "if (!(Test-Path $d) -or (Get-Item $s).LastWriteTime -gt (Get-Item $d).LastWriteTime) { exit 1 } else { exit 0 }"
if errorlevel 1 goto do_update_requirements
echo [INFO] Lokale requirements.txt is al up-to-date.
goto data_files_check

:do_update_requirements
call :make_backup
echo [INFO] Nieuwere requirements.txt gevonden, kopiëren...
copy /Y "%SRC_REQ%" "%DST_REQ%" >nul
if errorlevel 1 (
    echo [ERROR] Kopiëren requirements.txt mislukt.
    exit /b 1
)
echo [INFO] requirements.txt succesvol bijgewerkt.
echo [INFO] Requirements installeren...
call "%VENV%"
%PYTHON% -m pip install -r "%DST_REQ%"
if errorlevel 1 (
    echo [ERROR] pip install -r requirements.txt mislukt.
    exit /b 1
)
echo [INFO] Requirements succesvol geinstalleerd.

:data_files_check
echo [INFO] Data-bestanden controleren ^(*.json, *.csv^)...
powershell -NoProfile -Command ^
    "$src = '%CODE_DIR%'; $dst = '%~dp0'.TrimEnd('\'); $copied = 0;" ^
    "foreach ($ext in @('*.json', '*.csv')) {" ^
    "    foreach ($f in Get-ChildItem -Path $src -Filter $ext -EA SilentlyContinue) {" ^
    "        $d = Join-Path $dst $f.Name;" ^
    "        if (!(Test-Path $d) -or $f.LastWriteTime -gt (Get-Item $d).LastWriteTime) {" ^
    "            Copy-Item $f.FullName $d -Force;" ^
    "            Write-Host '[INFO] Gekopieerd:' $f.Name; $copied++ } } }" ^
    "if ($copied -eq 0) { Write-Host '[INFO] Alle data-bestanden zijn al up-to-date.' }"

:start_server
echo [INFO] Server starten...
call "%VENV%"
%PYTHON% "%~dp0server.py"
goto :eof

rem ── Subroutine: backup van huidige lokale bestanden ──────────────────────────
:make_backup
if "%BACKUP_DONE%"=="1" goto :eof
set "BACKUP_DONE=1"
echo [INFO] Huidige versie backuppen...
powershell -NoProfile -Command ^
    "$d = Get-Date -Format 'yyyyMMdd-HHmmss';" ^
    "$z = '%~dp0GMT-' + $d + '.zip';" ^
    "$f = @();" ^
    "$whl = Get-ChildItem -Path '%~dp0' -Filter 'gmt_calculation_lib-*.whl' -EA SilentlyContinue;" ^
    "if ($whl) { foreach ($w in $whl) { $f += $w.FullName } };" ^
    "$whl2 = Get-ChildItem -Path '%~dp0' -Filter 'what_if_quick_scan-*.whl' -EA SilentlyContinue;" ^
    "if ($whl2) { foreach ($w in $whl2) { $f += $w.FullName } };" ^
    "if (Test-Path '%~dp0index.html') { $f += '%~dp0index.html' };" ^
    "if (Test-Path '%~dp0server.py')  { $f += '%~dp0server.py' };" ^
    "if ($f.Count -gt 0) { Compress-Archive -Path $f -DestinationPath $z -Force; Write-Host '[INFO] Backup opgeslagen:' $z } else { Write-Host '[WARN] Niets om te backuppen' }"
goto :eof

endlocal
