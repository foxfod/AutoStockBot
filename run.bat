@echo off
cd /d c:\Users\foxfo\OneDrive\Study\Python\Scalping_Stock_Selector
call venv\Scripts\activate
if %errorlevel% neq 0 (
    echo Virtual environment not found. Attempting to run with system python...
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
) else (
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
)
timeout /t 5
goto loop
