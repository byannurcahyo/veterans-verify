@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

echo ========================================
echo   Veterans-Verify Chrome DevTools
echo   MCP Dedicated Debug Instance (Persistent Config)
echo ========================================
echo.

set "PORT=9222"
set "USER_DATA_DIR=%USERPROFILE%\.cache\veterans-chrome-mcp\user-data"
set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"

if not exist "%CHROME_EXE%" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if not exist "%CHROME_EXE%" (
    echo [Error] Chrome browser not found
    pause
    exit /b 1
)

if not exist "%USER_DATA_DIR%" (
    echo [Info] Creating data directory: "%USER_DATA_DIR%"
    mkdir "%USER_DATA_DIR%" >nul 2>&1
)

echo [Config] Chrome: "%CHROME_EXE%"
echo [Config] Data Directory: "%USER_DATA_DIR%"
echo [Config] Debug Port: http://127.0.0.1:%PORT%
echo.
echo ----------------------------------------
echo   Purpose: Dev Debug, Record Page Selectors
echo   Note: Use Camoufox for actual batch execution
echo ----------------------------------------
echo.

REM Check Port
netstat -ano | findstr ":%PORT%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [Info] Chrome is already running, port %PORT%
    echo        Connect using Claude Code directly
    pause
    exit /b 0
)

echo Starting Chrome...
start "" "%CHROME_EXE%" ^
    --remote-debugging-address=127.0.0.1 ^
    --remote-debugging-port=%PORT% ^
    --user-data-dir="%USER_DATA_DIR%" ^
    --no-first-run ^
    "about:blank"

timeout /t 2 /nobreak >nul
echo.
echo Chrome started! Now you can use Claude Code
pause
endlocal
