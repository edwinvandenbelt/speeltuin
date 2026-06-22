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

rem ── Virtuele omgeving activeren en server starten ───────────────────────────
if not exist "%VENV%" (
    echo [ERROR] Virtuele omgeving niet gevonden: %VENV%
    echo [INFO]  Voer eerst update.bat uit om de omgeving in te richten.
    exit /b 1
)

call "%VENV%"
%PYTHON% "%~dp0server.py"

endlocal
