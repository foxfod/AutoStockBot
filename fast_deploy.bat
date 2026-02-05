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

ssh -i "C:\path\to\mykey.pem" ubuntu@<서버IP> "cd <프로젝트폴더> && git pull && source venv/bin/activate && pip install -r requirements.txt && python main_auto_trade.py"

echo.
echo ✅ Local Push Successful!
echo.
echo ========================================================
echo  [Optional] Remote Server Update
echo ========================================================
echo If you have SSH set up, you can uncomment line 35 in this file
echo to automatically trigger 'git pull' on the server.
echo.
echo Example command to add:
echo ssh -i "key.pem" ubuntu@<YOUR_IP> "cd <REPO_DIR> && git pull && sudo systemctl restart scalping_bot"
echo.

pause
