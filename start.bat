@echo off
setlocal

set "VENV=%~dp0.venv\Scripts\activate.bat"

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

rem ── Wheel ────────────────────────────────────────────────────────────────────
if not defined WHEEL_DIR (
    echo [INFO] WHEEL_DIR niet ingesteld in .gmt-env, wheel-update overgeslagen.
    goto code_check
)
if not exist "%WHEEL_DIR%\" (
    echo [INFO] WHEEL_DIR niet bereikbaar ^(%WHEEL_DIR%^), wheel-update overgeslagen.
    goto code_check
)

set "WHEEL_FILE="
for /f "delims=" %%f in ('dir /b "%WHEEL_DIR%\gmt_calculation_lib-*.whl" 2^>nul') do set "WHEEL_FILE=%%f"
if not defined WHEEL_FILE (
    echo [WARN] Geen wheel gevonden in %WHEEL_DIR%
    goto code_check
)

set "SRC=%WHEEL_DIR%\%WHEEL_FILE%"
set "DST=%~dp0%WHEEL_FILE%"

if not exist "%DST%" (
    echo [INFO] Lokale whl ontbreekt, kopieer en installeer...
    goto do_update
)

powershell -NoProfile -Command ^
    "if ((Get-Item '%SRC%').LastWriteTime -gt (Get-Item '%DST%').LastWriteTime) { exit 1 } else { exit 0 }"
if errorlevel 1 goto do_update
echo [INFO] Lokale whl is al up-to-date.
goto code_check

:do_update
call :make_backup
echo [INFO] Nieuwere module gevonden, installeren...
copy /Y "%SRC%" "%DST%" >nul
call "%VENV%"
pip install --force-reinstall "%DST%"
if errorlevel 1 (
    echo [ERROR] Installatie mislukt.
    exit /b 1
)
echo [INFO] Whl succesvol herinstalleerd.

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
goto start_server

:do_update_html
call :make_backup
echo [INFO] Nieuwere HTML gevonden, kopiëren...
copy /Y "%SRC_HTML%" "%DST_HTML%" >nul
if errorlevel 1 (
    echo [ERROR] Kopiëren mislukt.
    exit /b 1
)
echo [INFO] HTML succesvol bijgewerkt.
goto py_check

:do_update_py
call :make_backup
echo [INFO] Nieuwer Python-bestand gevonden, kopiëren...
copy /Y "%SRC_PY%" "%DST_PY%" >nul
if errorlevel 1 (
    echo [ERROR] Kopiëren mislukt.
    exit /b 1
)
echo [INFO] Python-bestand succesvol bijgewerkt.

:start_server
echo [INFO] Server starten...
call "%VENV%"
python "%~dp0server.py"
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
    "if (Test-Path '%~dp0index.html') { $f += '%~dp0index.html' };" ^
    "if (Test-Path '%~dp0server.py')  { $f += '%~dp0server.py' };" ^
    "if ($f.Count -gt 0) { Compress-Archive -Path $f -DestinationPath $z -Force; Write-Host '[INFO] Backup opgeslagen:' $z } else { Write-Host '[WARN] Niets om te backuppen' }"
goto :eof

endlocal
