# 📖 HƯỚNG DẪN VẬN HÀNH WEBSITE TRUYỆN & TRỎ TÊN MIỀN KIẾM TIỀN QUẢNG CÁO

Toàn bộ mã nguồn website đã được lưu tại: **`E:\web-truyen-ads`**

---

## 🚀 1. CÁCH CHẠY WEBSITE TRÊN MÁY TÍNH (1 CLICK LÀ CHẠY)

Bạn chỉ cần vào thư mục `E:\web-truyen-ads` và bấm đúp chuột vào tệp:
👉 **`start.bat`**

Hệ thống sẽ tự động:
1. Cài đặt các thư viện Python cần thiết (`fastapi`, `uvicorn`, `jinja2`).
2. Khởi tạo cơ sở dữ liệu SQLite và nạp sẵn các câu chuyện mẫu đa phần (Part 1, Part 2, Part 3).
3. Bật máy chủ và tự động mở trình duyệt tại:
   - **Trang chủ đọc truyện:** [http://localhost:8000](http://localhost:8000)
   - **Bảng quản trị Admin:** [http://localhost:8000/admin](http://localhost:8000/admin)
   - **Tài khoản đăng nhập mặc định:** Mật khẩu: `admin123`

---

## 🌐 2. HƯỚNG DẪN TRỎ TÊN MIỀN BẠN ĐÃ CÓ VÀO WEBSITE

Bạn đã có tên miền riêng (ví dụ: `truyenhay24h.com` mua ở Namecheap, GoDaddy, iNet, Mắt Bão, Cloudflare,...), có 2 bước chính:

### Bước 2.1: Chuẩn bị Server / Hosting để chạy code
Website viết bằng **Python FastAPI siêu nhẹ** (chạy cực nhanh, chịu tải hàng chục nghìn lượt đọc/ngày). Bạn có 2 lựa chọn:

* **Cách 1: Thuê 1 máy chủ VPS giá rẻ (Khuyên dùng)**
  - Thuê VPS khoảng 70k - 100k/tháng (ở Vietnix, BKNS, TinoHost, hoặc Hetzner, Vultr).
  - Copy toàn bộ thư mục `E:\web-truyen-ads` lên VPS và chạy lệnh:
    ```bash
    pip install -r requirements.txt
    python -m uvicorn app.main:app --host 0.0.0.0 --port 80
    ```
* **Cách 2: Dùng nền tảng lưu trữ đám mây (Render.com hoặc Railway.app)**
  - Đẩy code lên GitHub và kết nối với Render.com (gói Free hoặc $7/tháng).

---

### Bước 2.2: Cấu hình DNS trỏ tên miền (Tại nơi bạn mua tên miền)

Đăng nhập vào trang quản lý tên miền (hoặc Cloudflare), vào mục **Quản lý DNS (DNS Management)** và thêm 2 bản ghi sau:

| Loại (Type) | Tên (Host / Name) | Giá trị (Target / Points to) | TTL |
| :--- | :--- | :--- | :--- |
| **A** | `@` | `Địa chỉ IP máy chủ VPS của bạn` (Ví dụ: `103.123.45.67`) | Auto |
| **CNAME** | `www` | `tenmiencuaban.com` | Auto |

> 💡 **Khuyên dùng Cloudflare:** Nên trỏ DNS Nameserver của tên miền về [Cloudflare.com](https://cloudflare.com) (Miễn phí 100%).
> - Bật icon đám mây màu cam (Proxy).
> - Tự động có chứng chỉ bảo mật HTTPS (ổ khóa xanh) miễn phí trọn đời.
> - Chống DDoS và nén trang siêu tốc giống hệt trang mẫu `tinyhousewow.com`.

---

## 💰 3. HƯỚNG DẪN CHÈN QUẢNG CÁO & KIẾM TIỀN (ADS MONETIZATION)

Website đã được thiết kế sẵn **6 vị trí quảng cáo vàng** có tỷ lệ click (CTR) và hiển thị (CPM) cao nhất theo đúng chuẩn của `tinyhousewow.com`:

Truy cập: **[http://localhost:8000/admin/ads](http://localhost:8000/admin/ads)**

1. **1. Banner Đầu Trang (Header Banner Ad - 728x90 hoặc Responsive):**
   - Đặt ngay dưới menu trang chủ và trang đọc truyện.
2. **2. Quảng Cáo Giữa Bài Đọc (In-Content Auto Ad) ⭐ TỶ LỆ CLICK CAO NHẤT:**
   - Hệ thống tự động chia các đoạn văn trong truyện và chèn quảng cáo sau mỗi 2 - 3 đoạn văn.
   - Bạn có thể tùy chỉnh tần suất (mỗi 2 đoạn, 3 đoạn hoặc 4 đoạn) chỉ với 1 cú click.
3. **3. Quảng Cáo Trước Nút "ĐỌC TIẾP PHẦN 2" (Pre-Next CTA Ad):**
   - Nằm ngay phía trên nút bấm chuyển phần. Độc giả buộc phải nhìn thấy khi đọc hết Phần 1 để chuyển sang Phần 2.
4. **4. Quảng Cáo Sau Nút Chuyển Trang (Post-Next Ad):**
   - Nằm dưới nút chuyển trang và danh sách các phần.
5. **5. Banner Ghim Đáy Màn Hình (Sticky Footer Anchor Ad):**
   - Luôn nổi cố định ở đáy màn hình điện thoại & máy tính, có nút bấm **[✕ Đóng]**. Vị trí này có viewability đạt 100%.
6. **6. Quảng Cáo Cột Phải (Sidebar Ad):**
   - Hiển thị trên máy tính ở trang chủ bên cạnh danh sách truyện đọc nhiều.
7. **Tệp `ads.txt` tự động:**
   - Truy cập ngay tại đường dẫn `tenmiencuaban.com/ads.txt`.
   - Vào Admin > Quản Lý Quảng Cáo để dán dòng xác minh của Google AdSense (ví dụ: `google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0`).

---

## 📱 4. CÁCH KÉO TRAFFIC VIRAL TỪ FACEBOOK NHƯ TINYHOUSEWOW

Mô hình kiếm tiền của trang tham khảo `tinyhousewow.com`:
1. **Làm Video Ngắn / Bài Viết Mồi (Reels / Fanpage / Group):**
   - Kể câu chuyện kịch tính, hấp dẫn dừng lại ở đoạn cao trào của **Phần 1**.
   - Kèm lời kêu gọi: *"Xem tiếp Phần 2 hồi kết tại link dưới phần bình luận!"*.
2. **Độc giả bấm vào link:**
   - Đọc xong Phần 1 trên web, độc giả sẽ bấm nút to nổi bật **"ĐỌC TIẾP PHẦN 2 NGAY ➔"**.
   - Mỗi độc giả sẽ tạo ra **2 đến 3 lượt xem trang (Pageviews)** và nhìn thấy từ **6 đến 12 lượt quảng cáo**.
   - Tối đa hóa doanh thu RPM mà không làm người đọc khó chịu.
3. **Tính năng hỗ trợ người đọc:**
   - Có thanh tiến trình đọc ở đỉnh màn hình (Reading progress bar).
   - Có thanh công cụ đổi cỡ chữ (A- / A / A+ / A++).
   - Có chế độ đọc ban đêm (Dark Mode) và chế độ giấy ngả vàng (Sepia dịu mắt).
   - Có nút chia sẻ nhanh lên Facebook, Zalo, Copy link.

---

## 📁 CẤU TRÚC THƯ MỤC DỰ ÁN TẠI `E:\web-truyen-ads`

```
E:\web-truyen-ads\
├── app\
│   ├── database.py             # Cơ sở dữ liệu SQLite & dữ liệu mẫu
│   ├── main.py                 # File chạy chính FastAPI
│   ├── routers\
│   │   ├── public.py           # Trang chủ, đọc truyện, chuyên mục, sitemap, ads.txt
│   │   └── admin.py            # Bảng quản trị đăng truyện, quản lý quảng cáo
│   ├── templates\              # Giao diện HTML (Jinja2 + Tailwind CSS)
│   │   ├── base.html           # Khung giao diện chuẩn SEO & Sticky Ads
│   │   ├── index.html          # Trang chủ
│   │   ├── story.html          # Trang đọc truyện & chuyển phần Part 1 -> Part 2
│   │   ├── category.html       # Chuyên mục
│   │   ├── search.html         # Tìm kiếm
│   │   └── admin\              # Toàn bộ trang quản trị (Đăng bài, Cấu hình Ads)
│   └── static\
│       └── js\reader.js        # Điều khiển cỡ chữ, dark mode, thanh cuộn đọc
├── data\
│   └── stories.db              # File cơ sở dữ liệu SQLite (tự động tạo)
├── requirements.txt            # Danh sách thư viện Python
└── start.bat                   # File bấm đúp để chạy web ngay lập tức
```
