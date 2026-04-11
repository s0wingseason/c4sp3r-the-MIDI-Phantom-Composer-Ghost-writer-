@echo off
setlocal EnableDelayedExpansion
title FalconEYE AI Arpeggio Generator — Build ^& Run
echo.
echo  ============================================================
echo   FalconEYE AI Arpeggio Generator — Build ^& Run
echo  ============================================================
echo.

:: ---- Configuration ----
set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%venv"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "JSFX_FILE=%PROJECT_DIR%FalconEYE_AI_Arpeggio.jsfx"
set "LUA_FILE=%PROJECT_DIR%FalconEYE_AI_Arpeggio_Generator.lua"
set "DKJSON_FILE=%PROJECT_DIR%dkjson.lua"
set "REQUIREMENTS=%PROJECT_DIR%requirements.txt"

:: ---- Find Python ----
echo  [1/6] Checking Python installation...
where python >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found in PATH.
    echo  Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set "PYVER=%%i"
echo        Found: %PYVER%

:: ---- Create/Update Virtual Environment ----
echo.
echo  [2/6] Setting up virtual environment...
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo        Creating new venv...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo        Existing venv found.
)

:: ---- Install Dependencies ----
echo.
echo  [3/6] Installing dependencies...
call "%VENV_DIR%\Scripts\activate.bat"
pip install -q -r "%REQUIREMENTS%"
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo        Dependencies installed.

:: ---- Install JSFX to REAPER ----
echo.
echo  [4/6] Installing JSFX plugin to REAPER...
set "REAPER_EFFECTS="

:: Check APPDATA\REAPER\Effects
if exist "%APPDATA%\REAPER\Effects" (
    set "REAPER_EFFECTS=%APPDATA%\REAPER\Effects"
)

:: Create FalconEYE subfolder and copy JSFX
if defined REAPER_EFFECTS (
    set "DEST_DIR=!REAPER_EFFECTS!\FalconEYE"
    if not exist "!DEST_DIR!" mkdir "!DEST_DIR!"
    copy /Y "%JSFX_FILE%" "!DEST_DIR!\FalconEYE_AI_Arpeggio.jsfx" >nul
    echo        Installed JSFX to: !DEST_DIR!

    :: Ensure Data directory exists for pattern files
    if not exist "%APPDATA%\REAPER\Data" mkdir "%APPDATA%\REAPER\Data"
    echo        REAPER Data directory ready.
) else (
    echo        [WARN] REAPER Effects folder not found at %%APPDATA%%\REAPER\Effects
    echo        Please manually copy FalconEYE_AI_Arpeggio.jsfx to your REAPER Effects folder.
)

:: ---- Install ReaScript to REAPER ----
echo.
echo  [5/6] Installing ReaScript to REAPER...
set "REAPER_SCRIPTS=%APPDATA%\REAPER\Scripts"
if exist "%REAPER_SCRIPTS%" (
    set "SCRIPT_DEST=!REAPER_SCRIPTS!\FalconEYE"
    if not exist "!SCRIPT_DEST!" mkdir "!SCRIPT_DEST!"
    copy /Y "%LUA_FILE%" "!SCRIPT_DEST!\FalconEYE_AI_Arpeggio_Generator.lua" >nul
    copy /Y "%DKJSON_FILE%" "!SCRIPT_DEST!\dkjson.lua" >nul
    echo        Installed ReaScript to: !SCRIPT_DEST!
    echo        To use in REAPER: Actions ^> Load ReaScript ^> select the .lua file
) else (
    echo        [WARN] REAPER Scripts folder not found at %%APPDATA%%\REAPER\Scripts
    echo        You can still use the standalone app or web UI.
)

:: ---- Launch Server (Background / Silent) ----
echo.
echo  [6/6] Starting application in background...
echo.
echo  ============================================================

:: Redirect server output to log file, run hidden via pythonw or VBS
cd /d "%BACKEND_DIR%"
set "LOG_FILE=%BACKEND_DIR%\server.log"
set "PYTHONW=%VENV_DIR%\Scripts\pythonw.exe"

:: Try pythonw first (truly headless), fall back to hidden python via VBS
if exist "%PYTHONW%" (
    echo   Launching server silently via pythonw...
    echo   Logs: %LOG_FILE%
    start "" /b "%PYTHONW%" launcher.py > "%LOG_FILE%" 2>&1
) else (
    echo   Launching server silently via VBS wrapper...
    echo   Logs: %LOG_FILE%
    start "" /b cscript //nologo "%PROJECT_DIR%launch_silent.vbs"
)

:: Wait for server to start, then open browser
echo.
echo   Waiting for server to start...
timeout /t 3 /nobreak >nul 2>&1

:: Check if server is running
python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=2)" >nul 2>&1
if %errorlevel% == 0 (
    echo   Server is running!
    start "" http://localhost:8765
) else (
    timeout /t 3 /nobreak >nul 2>&1
    start "" http://localhost:8765
)

echo.
echo  ============================================================
echo   FalconEYE AI Arpeggio Generator is running in background.
echo   Web UI: http://localhost:8765
echo   Logs:   %LOG_FILE%
echo.
echo   To stop the server, use Task Manager or the system tray.
echo  ============================================================
echo.

:: Deactivate venv and exit (CMD window closes)
call "%VENV_DIR%\Scripts\deactivate.bat" 2>nul
endlocal
exit
