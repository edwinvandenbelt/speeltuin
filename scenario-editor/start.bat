@echo off
setlocal

rem GMT Scenario-editor — lokale start (Windows).
rem Afgeleid van digital-twin\start.bat: geen wegenscan/what_if-wheel-sync nodig.

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

rem ── Eerste installatie: venv aanmaken en requirements installeren ────────────
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [INFO] Eerste installatie: virtuele omgeving aanmaken...
    %PYTHON% -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo [ERROR] Aanmaken virtuele omgeving mislukt.
        exit /b 1
    )
    echo [INFO] Virtuele omgeving aangemaakt.
    echo [INFO] Requirements installeren...
    "%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [ERROR] pip install -r requirements.txt mislukt.
        exit /b 1
    )
    echo [INFO] Requirements succesvol geinstalleerd.
)

echo [INFO] Server starten op poort 5002 (GMT Analyzer gebruikt 5000, GMT Digital Twin 5001)...
call "%VENV%"
%PYTHON% "%~dp0server.py" --port 5002
goto :eof

endlocal
