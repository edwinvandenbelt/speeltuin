@echo off
setlocal

set SRC=C:\sources\GMP\gmt-calculation-lib\dist\gmt_calculation_lib-0.1.1-py3-none-any.whl
set DST=%~dp0gmt_calculation_lib-0.1.1-py3-none-any.whl
set VENV=%~dp0.venv\Scripts\activate.bat

set SRC_HTML=index.html
set DST_HTML=index.html
set SRC_PY=server.py
set DST_PY=server.py

if not exist "%SRC%" (
    echo [WARN] Bronbestand niet gevonden: %SRC%
    goto start_server
)

if not exist "%DST%" (
    echo [INFO] Lokale whl ontbreekt, kopieer en installeer...
    goto do_update
)

rem Vergelijk timestamps via PowerShell (exitcode 1 = bron is nieuwer)
powershell -NoProfile -Command ^
  "if ((Get-Item '%SRC%').LastWriteTime -gt (Get-Item '%DST%').LastWriteTime) { exit 1 } else { exit 0 }"
if errorlevel 1 goto do_update
echo [INFO] Lokale whl is al up-to-date.

:html_check
echo [INFO] Controleren of lokale html is...
powershell -NoProfile -Command ^
  "if ((Get-Item '%SRC_HTML%').LastWriteTime -gt (Get-Item '%DST_HTML%').LastWriteTime) { exit 1 } else { exit 0 }"
if errorlevel 1 goto do_update_html
echo [INFO] Lokale HTML is al up-to-date.

:py_check
echo [INFO] Controleren of lokale Python-bestand is...
powershell -NoProfile -Command ^
  "if ((Get-Item '%SRC_PY%').LastWriteTime -gt (Get-Item '%DST_PY%').LastWriteTime) { exit 1 } else { exit 0 }"
if errorlevel 1 goto do_update_py
echo [INFO] Lokale Python-bestand is al up-to-date.

goto start_server

:do_update
echo [INFO] Nieuwere module gevonden, installeren...
copy /Y "%SRC%" "%DST%" >nul
call "%VENV%"
pip install --force-reinstall "%DST%"
if errorlevel 1 (
    echo [ERROR] Installatie mislukt.
    exit /b 1
)
echo [INFO] Whl succesvol herinstalleerd.

goto html_check

:do_update_html
echo [INFO] Nieuwere HTML gevonden, kopiëren...
copy /Y "%SRC_HTML%" "%DST_HTML%" >nul
if errorlevel 1 (
    echo [ERROR] Kopiëren mislukt.
    exit /b 1
)
echo [INFO] HTML succesvol bijgewerkt.

goto py_check

:do_update_py
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

endlocal
