@echo off
setlocal EnableDelayedExpansion
title FalconEYE AI Arpeggio Generator — Uninstall
echo.
echo  ============================================================
echo   FalconEYE AI Arpeggio Generator — Uninstall
echo  ============================================================
echo.

set "PROJECT_DIR=%~dp0"

:: Remove venv
echo  [1/4] Removing virtual environment...
if exist "%PROJECT_DIR%venv" (
    rd /s /q "%PROJECT_DIR%venv"
    echo        Removed.
) else (
    echo        Not found (already clean).
)

:: Remove JSFX from REAPER
echo.
echo  [2/4] Removing JSFX from REAPER...
set "JSFX_DEST=%APPDATA%\REAPER\Effects\FalconEYE"
if exist "%JSFX_DEST%" (
    rd /s /q "%JSFX_DEST%"
    echo        Removed: %JSFX_DEST%
) else (
    echo        Not found.
)

:: Remove ReaScript from REAPER
echo.
echo  [3/4] Removing ReaScript from REAPER...
set "SCRIPT_DEST=%APPDATA%\REAPER\Scripts\FalconEYE"
if exist "%SCRIPT_DEST%" (
    rd /s /q "%SCRIPT_DEST%"
    echo        Removed: %SCRIPT_DEST%
) else (
    echo        Not found.
)

:: Remove pattern data file
echo.
echo  [4/4] Removing pattern data file...
set "PATTERN_FILE=%APPDATA%\REAPER\Data\AI_Arpeggio_pattern_data.txt"
if exist "%PATTERN_FILE%" (
    del /q "%PATTERN_FILE%"
    echo        Removed.
) else (
    echo        Not found.
)

echo.
echo  ============================================================
echo   Uninstall complete.
echo   Your pattern library in pattern_library/ was NOT deleted.
echo   Delete it manually if you want to remove all data.
echo  ============================================================
echo.
pause
endlocal
