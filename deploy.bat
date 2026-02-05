@echo off
echo [AWS Deployment Helper]
echo Zipping files for upload...

tar -cvf ktr_bot_deploy.tar ^
  app ^
  main_auto_trade.py ^
  requirements.txt ^
  Dockerfile ^
  .env

echo.
echo [Done] 'ktr_bot_deploy.tar' created.
echo Upload this file to your AWS Server.
pause
