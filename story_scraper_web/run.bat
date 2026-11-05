@echo off
title Universal Story Scraper - Clean Novel Engine
cd /d "%~dp0"

echo ========================================================
echo   Universal Story Scraper [Cloud va Local Edition]
echo   Chuyen dung cao truyen full chuong khong quang cao
echo ========================================================
echo.

rem Giai phong port 8501 neu co tien trinh cu dang chay
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8501 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

rem Uu tien dung moi truong Python da cai san thu vien de khoi dong trong 1 giay
set PYTHON_CMD=python
if exist "E:\fb_video_clone_tool\.venv\Scripts\python.exe" (
    set PYTHON_CMD="E:\fb_video_clone_tool\.venv\Scripts\python.exe"
)

%PYTHON_CMD% -c "import streamlit, bs4, requests" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [*] Dang cai dat thu vien can thiet...
    %PYTHON_CMD% -m pip install -r "%~dp0requirements.txt"
) else (
    echo [*] Thu vien da san sang!
)

echo.
echo [*] Dang khoi dong Web Scraper tai http://localhost:8501 ...
start http://localhost:8501
%PYTHON_CMD% -m streamlit run "%~dp0app.py" --server.port 8501 --browser.gatherUsageStats false

pause
