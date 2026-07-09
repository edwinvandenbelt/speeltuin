@echo off
setlocal

set "IMAGE_NAME=gmt-speeltuin"
set "CONTAINER_NAME=gmt-speeltuin"
set "HOST_PORT=5000"
set "WORK_DIR=%~dp0work"
set "SCRIPT_DIR=%~dp0"

rem %~dp0 eindigt altijd op \  —  strip die voor gebruik als Docker-pad
rem (anders wordt "pad\" door de shell gelezen als escaped aanhalingsteken)
set "BUILD_CONTEXT=%~dp0"
set "BUILD_CONTEXT=%BUILD_CONTEXT:~0,-1%"

echo [INFO] GMT Speeltuin — Docker start

rem ── Docker beschikbaarheid checken ──────────────────────────────────────────
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker niet gevonden. Installeer Docker Desktop en probeer opnieuw.
    echo [INFO]  https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker daemon niet actief. Start Docker Desktop en probeer opnieuw.
    pause
    exit /b 1
)

rem ── .env checken ─────────────────────────────────────────────────────────────
if not exist "%SCRIPT_DIR%.env" (
    echo [ERROR] .env-bestand niet gevonden in: %SCRIPT_DIR%
    echo [INFO]  Maak een .env-bestand met de Databricks-credentials en probeer opnieuw.
    pause
    exit /b 1
)

rem ── work-directory aanmaken als die nog niet bestaat ─────────────────────────
if not exist "%WORK_DIR%\" (
    echo [INFO] work-map aanmaken: %WORK_DIR%
    mkdir "%WORK_DIR%"
)

rem ── Docker image bouwen ──────────────────────────────────────────────────────
echo [INFO] Docker image bouwen ^(%IMAGE_NAME%^)...
echo [INFO] Dit kan de eerste keer enkele minuten duren.
docker build -t "%IMAGE_NAME%" "%BUILD_CONTEXT%"
if errorlevel 1 (
    echo [ERROR] Docker build mislukt.
    pause
    exit /b 1
)
echo [INFO] Image succesvol gebouwd.

rem ── Bestaande container stoppen en verwijderen ───────────────────────────────
echo [INFO] Eventuele bestaande container opruimen...
docker stop "%CONTAINER_NAME%" >nul 2>&1
docker rm   "%CONTAINER_NAME%" >nul 2>&1

rem ── Container starten ────────────────────────────────────────────────────────
echo [INFO] Container starten op poort %HOST_PORT%...
docker run -d ^
    --name "%CONTAINER_NAME%" ^
    -p %HOST_PORT%:5000 ^
    -v "%WORK_DIR%:/app/work" ^
    --env-file "%SCRIPT_DIR%.env" ^
    --restart unless-stopped ^
    "%IMAGE_NAME%"

if errorlevel 1 (
    echo [ERROR] Container starten mislukt.
    pause
    exit /b 1
)

echo.
echo [OK] GMT Speeltuin draait op: http://localhost:%HOST_PORT%
echo.
echo Handige Docker-commando's:
echo   Logs bekijken  :  docker logs -f %CONTAINER_NAME%
echo   Container stop :  docker stop %CONTAINER_NAME%
echo   Container start:  docker start %CONTAINER_NAME%
echo   Image herbouwen:  Voer startDocker.bat opnieuw uit
echo.
pause

endlocal
