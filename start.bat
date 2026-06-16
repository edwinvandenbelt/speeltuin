@echo off
setlocal

set SRC=C:\sources\GMP\gmt-calculation-lib\dist\gmt_calculation_lib-0.1.1-py3-none-any.whl
set DST=%~dp0gmt_calculation_lib-0.1.1-py3-none-any.whl
set VENV=%~dp0.venv\Scripts\activate.bat

if not exist "%SRC%" (
    echo [WARN] Bronbestand niet gevonden: %SRC%
    goto start_server
)

if not exist "%DST%" (
    echo [INFO] Lokale whl ontbreekt, kopieer en installeer...
    goto do_update
)

rem Vergelijk timestamps via xcopy /D (kopieert alleen als bron nieuwer is)
xcopy /D /Y /Q "%SRC%" "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Lokale whl is al up-to-date.
    goto start_server
)

:do_update
echo [INFO] Nieuwere whl gevonden, installeren...
copy /Y "%SRC%" "%DST%" >nul
call "%VENV%"
pip install --force-reinstall "%DST%"
if errorlevel 1 (
    echo [ERROR] Installatie mislukt.
    exit /b 1
)
echo [INFO] Whl succesvol herinstalleerd.

:start_server
echo [INFO] Server starten...
call "%VENV%"
python "%~dp0server.py"

endlocal
