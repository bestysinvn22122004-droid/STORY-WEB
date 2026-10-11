@echo off
chcp 65001 > nul
title Website Đọc Truyện Kiếm Tiền Ads
color 0A

echo ==============================================================================
echo        HE THONG WEBSITE DOC TRUYEN KIEM TIEN QUANG CAO (ADS MONETIZATION)
echo ==============================================================================
echo.
echo [1/3] Kiem tra va cai dat thu vien Python can thiet...
python -m pip install -r requirements.txt

echo.
echo [2/3] Khoi tao co so du lieu SQLite...
python -c "from app.database import init_db; init_db(); print('Da san sang co so du lieu!')"

echo.
echo [3/3] Dang khoi dong Web Server tai http://localhost:8000 ...
echo - Trang chu website:   http://localhost:8000
echo - Bang quan tri Admin: http://localhost:8000/admin (Mat khau mac dinh: admin123)
echo - Tuyen tap Quang cao: http://localhost:8000/admin/ads
echo.
echo Bam Ctrl + C de dung may chu bat cu luc nao.
echo ==============================================================================

start http://localhost:8000

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
