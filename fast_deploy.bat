@echo off
chcp 65001 > nul
echo ========================================================
echo       🚀 Fast Deploy Helper (Git Push + Auto Deploy)
echo ========================================================
echo.

:: 1. Ask for Commit Message
set /p msg="Commit Message (Enter for default): "
if "%msg%"=="" set msg="Auto update via script"

echo.
echo [1/3] Adding changes...
git add .
if %errorlevel% neq 0 (
    echo [ERROR] Git Add failed.
    pause
    exit /b
)

echo [2/3] Committing...
git commit -m "%msg%"
if %errorlevel% neq 0 (
    echo [INFO] Nothing to commit or error.
)

echo [3/3] Pushing to GitHub...
git push
if %errorlevel% neq 0 (
    echo [ERROR] Git Push failed. Check your network or credentials.
    pause
    exit /b
)

echo [4/4] Connecting to Remote Server...
ssh -i "C:\Users\foxfo\.ssh\AutoStockBot.pem" ubuntu@3.25.119.99 "cd AutoStockBot && git pull && source venv/bin/activate && pip install -r requirements.txt && sudo systemctl restart scalping_bot"

echo.
echo ✅ Local Push & Remote Restart Successful!
echo.
echo ========================================================
echo  [Info] Remote Server Update
echo ========================================================
echo The bot service (scalping_bot) has been restarted.
echo Check logs with: sudo journalctl -u scalping_bot -f
echo.

pause
