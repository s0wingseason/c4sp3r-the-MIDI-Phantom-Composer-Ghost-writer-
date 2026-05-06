@echo off
setlocal EnableDelayedExpansion
title C@sp3r - MIDI Phantom Composer — Build Standalone .exe
echo.
echo  ============================================================
echo   C@sp3r - MIDI Phantom Composer — Build Standalone .exe
echo  ============================================================
echo.

:: ---- Configuration ----
set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%venv"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "REQUIREMENTS=%PROJECT_DIR%requirements.txt"
set "EXE_NAME=Casper_MIDI_Phantom_Composer"

:: ---- Find Python ----
echo  [1/4] Checking Python installation...
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
echo  [2/4] Setting up virtual environment...
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
echo  [3/4] Installing dependencies + build tools...
call "%VENV_DIR%\Scripts\activate.bat"
pip install -q -r "%REQUIREMENTS%" pyinstaller
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo        Dependencies + PyInstaller installed.

:: ---- Build .exe ----
echo.
echo  [4/4] Building standalone executable...
echo        This may take 1-3 minutes...
cd /d "%BACKEND_DIR%"

pyinstaller --noconfirm --onefile --noconsole ^
    --name "%EXE_NAME%" ^
    --add-data "static;static" ^
    --hidden-import "waitress" ^
    --hidden-import "webview" ^
    --hidden-import "flask" ^
    --hidden-import "flask_cors" ^
    --hidden-import "clr" ^
    launcher.py

if errorlevel 1 (
    echo.
    echo  [ERROR] PyInstaller build failed. Check the output above for details.
    pause
    exit /b 1
)

:: ---- Copy to project root ----
echo.
if exist "dist\%EXE_NAME%.exe" (
    copy /Y "dist\%EXE_NAME%.exe" "%PROJECT_DIR%%EXE_NAME%.exe" >nul
    echo  ============================================================
    echo   BUILD SUCCESSFUL!
    echo   Output: %PROJECT_DIR%%EXE_NAME%.exe
    echo.
    echo   To run: just double-click the .exe file.
    echo   The config.json must be in the same folder as the .exe.
    echo  ============================================================
) else (
    echo  [ERROR] Build output not found.
)

:: ---- Cleanup ----
echo.
echo  Cleaning build artifacts...
rd /s /q "%BACKEND_DIR%\build" 2>nul
rd /s /q "%BACKEND_DIR%\dist" 2>nul
del /q "%BACKEND_DIR%\%EXE_NAME%.spec" 2>nul

call "%VENV_DIR%\Scripts\deactivate.bat" 2>nul
echo  Done.
pause
endlocal
