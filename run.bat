@echo off
cd /d c:\Users\foxfo\OneDrive\Study\Python\Scalping_Stock_Selector
call venv\Scripts\activate
if %errorlevel% neq 0 (
    echo Virtual environment not found. Attempting to run with system python...
    python main_auto_trade.py
) else (
    python main_auto_trade.py
)
timeout /t 5
goto loop
