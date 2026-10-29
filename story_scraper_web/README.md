# Universal Story Scraper (Cloud Edition) 📖✨

Công cụ cào truyện đa nền tảng tự động cào 100% tất cả các chương truyện trên bất kỳ website nào, lọc sạch quảng cáo và rác, sẵn sàng đưa lên **Render**.

---

## 🚀 Tính năng vượt trội:

1. **Cào đa tầng (Multi-Strategy):**
   - **Tầng 1 (Mục lục TOC):** Nhận diện mục lục mọi website novel.
   - **Tầng 2 (Next Button Crawler):** Tự động bắt nút `Next`, `Next Chapter`, `Chương sau`, `»` để lướt qua từng chương cho đến hết.
   - **Tầng 3 (Adaptive URL):** Tự động nhận dạng cấu trúc `/chapter-N`, `/part-N`, `?page=N`.
2. **Lọc sạch 100% rác:** Loại bỏ hoàn toàn quảng cáo, nút share mạng xã hội, các dòng tiêu đề chương ("Chapter 1", "Chương 1").
3. **Thao tác nhanh:**
   - 1-Click Tải file `.txt` về máy.
   - 1-Click Sao chép toàn văn truyện để đăng lên website đọc truyện kiếm tiền.
   - Xem chi tiết từng chương riêng biệt.

---

## 🌐 Hướng dẫn Đưa Lên Render:

1. Tạo một Repository mới trên GitHub (ví dụ: `story-scraper-web`) và đẩy toàn bộ thư mục này lên.
2. Đăng nhập [Render.com](https://dashboard.render.com).
3. Bấm **New +** $\rightarrow$ Chọn **Web Service**.
4. Chọn Repository vừa tạo.
5. Cấu hình các thông số:
   - **Language:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --browser.gatherUsageStats false`
   - **Plan:** `Free` (Chỉ tốn ~70MB RAM / 512MB RAM tối đa, chạy cực êm).
6. Bấm **Deploy Web Service** và chờ 1 phút là có link web online dùng bất cứ đâu!

---

## 💻 Chạy Trực Tiếp Trên Máy Tính:
Nhấp đúp chuột vào file **`run.bat`** để mở giao diện tại `http://localhost:8501`.
