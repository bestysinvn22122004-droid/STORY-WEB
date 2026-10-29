@echo off
title Universal Story Scraper - Clean Novel Engine
cd /d "%~dp0"

echo ========================================================
echo   Universal Story Scraper (Cloud & Local Edition)
echo   Chuyen dung cao truyen full chuong khong quang cao
echo ========================================================
echo.

rem Giai phong port 8501 neu co tien trinh cu dang chay
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8501 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Khong tim thay Python! Hay cai dat Python 3.10 tro len.
    pause
    exit /b
)

echo [*] Kiem tra thu vien...
python -m pip install -q -r requirements.txt

echo.
echo [*] Dang khoi dong Web Scraper tai http://localhost:8501 ...
python -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false

pause
