@echo off
setlocal EnableDelayedExpansion
title C@sp3r - MIDI Phantom Composer — Build VST3 Plugin
echo.
echo  ============================================================
echo   C@sp3r - MIDI Phantom Composer — Build VST3 Plugin
echo  ============================================================
echo.

set "PROJECT_DIR=%~dp0"
set "VST_DIR=%PROJECT_DIR%vst"

:: ---- Check for Rust ----
echo  [1/3] Checking Rust toolchain...
where rustc >nul 2>&1
if errorlevel 1 (
    echo        Rust not found. Installing via rustup...
    echo.
    echo        This will download and install the Rust toolchain (~250MB^).
    echo        This is a one-time setup.
    echo.

    :: Download rustup-init.exe
    set "RUSTUP_URL=https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe"
    set "RUSTUP_EXE=%TEMP%\rustup-init.exe"

    powershell -Command "Invoke-WebRequest -Uri '%RUSTUP_URL%' -OutFile '%RUSTUP_EXE%'" 2>nul
    if not exist "!RUSTUP_EXE!" (
        curl -sSfL "%RUSTUP_URL%" -o "!RUSTUP_EXE!" 2>nul
    )

    if not exist "!RUSTUP_EXE!" (
        echo  [ERROR] Failed to download rustup-init.exe
        echo  Please install Rust manually from https://rustup.rs
        pause
        exit /b 1
    )

    :: Install with defaults (no prompts)
    "!RUSTUP_EXE!" -y --default-toolchain stable --profile minimal
    if errorlevel 1 (
        echo  [ERROR] Rust installation failed.
        pause
        exit /b 1
    )

    :: Refresh PATH
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
    echo        Rust installed successfully!
) else (
    for /f "tokens=*" %%i in ('rustc --version 2^>^&1') do set "RUSTVER=%%i"
    echo        Found: !RUSTVER!
)
echo.

:: ---- Build the plugin ----
echo  [2/3] Building VST3 plugin (release mode)...
echo        This may take 2-5 minutes on first build...
echo.

cd /d "%VST_DIR%"

:: Use cargo xtask to build and bundle
cargo run --release -p xtask -- bundle casper_vst --release
if errorlevel 1 (
    echo.
    echo  [ERROR] Build failed. Check the output above for details.
    echo.
    echo  Common fixes:
    echo    - Make sure you have a C/C++ compiler (Visual Studio Build Tools)
    echo    - Run: rustup update
    echo    - Try: cargo clean, then run this script again
    pause
    exit /b 1
)

echo.
echo  [3/3] Locating built plugin...

:: The bundled VST3 will be in target/bundled/
set "VST3_BUNDLE=%VST_DIR%\target\bundled\C@sp3r MIDI Phantom.vst3"
set "VST3_ALT=%VST_DIR%\target\bundled\casper_vst.vst3"

:: Copy to common VST3 directory
set "VST3_SYSTEM=%CommonProgramFiles%\VST3"
if not exist "%VST3_SYSTEM%" mkdir "%VST3_SYSTEM%"

if exist "%VST3_BUNDLE%" (
    xcopy /E /I /Y "%VST3_BUNDLE%" "%VST3_SYSTEM%\C@sp3r MIDI Phantom.vst3" >nul 2>&1
    echo        VST3 installed to: %VST3_SYSTEM%\C@sp3r MIDI Phantom.vst3
) else if exist "%VST3_ALT%" (
    xcopy /E /I /Y "%VST3_ALT%" "%VST3_SYSTEM%\Casper MIDI Phantom.vst3" >nul 2>&1
    echo        VST3 installed to: %VST3_SYSTEM%\Casper MIDI Phantom.vst3
) else (
    echo        [WARN] Could not locate bundled .vst3 — check target\bundled\
    echo        You may need to manually copy the .vst3 folder to your DAW's VST3 directory.
    dir /s /b "%VST_DIR%\target\bundled\" 2>nul
)

echo.
echo  ============================================================
echo   BUILD COMPLETE!
echo.
echo   The VST3 plugin has been built and installed.
echo   Rescan plugins in your DAW to see "C@sp3r MIDI Phantom".
echo.
echo   The plugin reads AI_Arpeggio_pattern_data.txt from:
echo     %%APPDATA%%\REAPER\Data\
echo.
echo   Controls: Velocity Scale, Octave, Gate, Transpose, Swing
echo   GUI: Custom dark-themed editor (click plugin window in DAW)
echo  ============================================================
echo.
pause
endlocal
