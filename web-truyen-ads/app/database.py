import sqlite3
import os
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stories.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # Table: Categories
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT,
        icon TEXT DEFAULT 'book-open',
        sort_order INTEGER DEFAULT 0
    )
    """)

    # Table: Stories
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        excerpt TEXT,
        cover_image TEXT,
        category_id INTEGER,
        views INTEGER DEFAULT 0,
        is_featured INTEGER DEFAULT 0,
        reading_time INTEGER DEFAULT 5,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
    """)

    # Table: Story Parts (Chapters/Parts)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS story_parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        story_id INTEGER NOT NULL,
        part_number INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        views INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (story_id) REFERENCES stories (id) ON DELETE CASCADE,
        UNIQUE(story_id, part_number)
    )
    """)

    # Table: Ads Config
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ads_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_key TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        is_enabled INTEGER DEFAULT 1,
        ad_code TEXT DEFAULT '',
        extra_settings TEXT DEFAULT ''
    )
    """)

    # Table: Site Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS site_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()

    # Seed Default Settings if not exist
    default_settings = {
        "site_name": "Truyện Hay 24h",
        "tagline": "Kho Truyện Cảm Động & Bài Học Cuộc Sống Đầy Ý Nghĩa",
        "meta_description": "Đọc truyện ngắn, truyện gia đình, bài học cuộc sống, nhân quả, tình huống kịch tính hấp dẫn nhất mỗi ngày.",
        "contact_email": "contact@yourdomain.com",
        "admin_password_hash": hash_password("admin123"),
        "adsense_client_id": "",
        "head_scripts": "",
        "body_scripts": "",
        "ads_txt": "google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0",
        "paragraph_ad_interval": "3",
        "show_ad_placeholders": "1" # Show preview banner when ad_code is empty
    }

    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?)", (k, v))

    # Seed Default Ads Slots
    default_ads = [
        ("header_ad", "Banner Đầu Trang (Header Ad)", "Hiển thị phía dưới thanh menu, vị trí dễ thấy nhất khi vừa vào bài viết (728x90 hoặc Responsive)."),
        ("in_content_ad", "Quảng Cáo Giữa Bài Đọc (In-Content Ad)", "Tự động chèn sau mỗi 3-4 đoạn văn trong câu chuyện. Vị trí có tỷ lệ click (CTR) cao nhất."),
        ("before_next_button", "Quảng Cáo Trước Nút 'Đọc Tiếp' (Pre-Next Ad)", "Nằm ngay phía trên nút bấm chuyển sang Phần tiếp theo. Độc giả dừng lại trước khi bấm chuyển trang."),
        ("after_next_button", "Quảng Cáo Sau Nút Chuyển Trang (Post-Next Ad)", "Nằm ngay phía dưới cụm nút chuyển trang / chia sẻ."),
        ("sticky_footer_ad", "Banner Ghim Đáy Màn Hình (Sticky Anchor Ad)", "Banner nổi cố định ở mép dưới điện thoại/máy tính có nút đóng (X). Tỷ lệ hiển thị 100%."),
        ("sidebar_ad", "Quảng Cáo Cột Phải (Sidebar Ad)", "Hiển thị ở cột bên phải khi đọc trên máy tính/laptop (300x250 hoặc 300x600).")
    ]

    for key, name, desc in default_ads:
        cursor.execute("""
        INSERT OR IGNORE INTO ads_config (slot_key, name, description, is_enabled, ad_code)
        VALUES (?, ?, ?, 1, '')
        """, (key, name, desc))

    # Seed Default Categories
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        categories = [
            ("Gia Đình & Bi Kịch", "gia-dinh", "Những góc khuất gia đình, xung đột và tình thâm đầy nước mắt", 1),
            ("Nhân Quả & Bài Học", "nhan-qua-bai-hoc", "Chân lý cuộc đời, thiện ác phân minh và bài học đắt giá", 2),
            ("Giấu Kín Danh Tính", "giau-danh-tinh", "Chủ tịch giả nghèo, đại gia ẩn danh và những màn lật kèo ngoạn mục", 3),
            ("Bảo Vệ Người Yếu Thế", "bao-ve-yeu-the", "Hành động nghĩa hiệp, bảo vệ người già và trẻ em trước bất công", 4),
            ("Tình Cảm & Hôn Nhân", "tinh-cam-hon-nhan", "Câu chuyện tình yêu, sự thủy chung và phản bội chốn hôn nhân", 5),
            ("Biker & Công Lý", "biker-cong-ly", "Tinh thần trượng nghĩa trên những cung đường và bảo vệ lẽ phải", 6),
        ]
        for name, slug, desc, sort_order in categories:
            cursor.execute("INSERT INTO categories (name, slug, description, sort_order) VALUES (?, ?, ?, ?)",
                           (name, slug, desc, sort_order))

    # Seed Sample Stories with Multi-Parts (Viral format like tinyhousewow)
    cursor.execute("SELECT COUNT(*) FROM stories")
    if cursor.fetchone()[0] == 0:
        sample_stories = [
            {
                "title": "Phần 2: Người Anh Trai Trở Về Khi Không Ai Bảo Vệ Tôi",
                "slug": "nguoi-anh-trai-tro-ve-khi-khong-ai-bao-ve-toi",
                "excerpt": "Cả gia đình chồng xúm vào đuổi tôi ra khỏi nhà giữa đêm mưa bão. Nhưng khi tiếng gầm rú của đoàn xe moto vang lên ngoài cổng, sắc mặt mẹ chồng lập tức tái mét...",
                "cover_image": "https://images.unsplash.com/photo-1519791883288-dc8bd696e667?auto=format&fit=crop&w=1000&q=80",
                "category_id": 1,
                "is_featured": 1,
                "reading_time": 4,
                "parts": [
                    {
                        "part_number": 1,
                        "title": "Phần 1: Đêm Bão Tố Và Chiếc Va Ly Bị Ném Ra Sân",
                        "content": """Trời mưa như trút nước vào đêm thứ Bảy. Căn nhà ba tầng của gia đình chồng vốn ấm cúng, bỗng chốc trở thành nơi lạnh lẽo nhất trần đời đối với tôi.

Mẹ chồng đứng ở đầu cầu thang, tay chống nạnh, giọng the thé chĩa thẳng vào mặt tôi: "Cô tưởng sinh được đứa con gái là có quyền ngồi mát ăn bát vàng à? Nhà này không nuôi báo cô kẻ vô dụng!"

Tôi ôm chặt bé Bống mới vừa tròn 8 tháng tuổi vào lòng. Con bé run lên từng đợt vì tiếng sấm chớp rền vang ngoài trời. Chồng tôi - người đàn ông từng thề non hẹn biển sẽ che chở cho tôi suốt đời - lúc này chỉ biết ngồi im góc sofa, cắm mặt vào chiếc điện thoại như một kẻ vô hồn.

"Anh... anh nói một lời đi. Con còn quá nhỏ, ngoài trời đang bão lớn thế này, mẹ con em biết đi đâu?" - Tôi nghẹn ngào, nhìn thẳng vào anh ta tìm kiếm một chút tình nghĩa cuối cùng.

Nhưng câu trả lời tôi nhận được chỉ là cái phẩy tay hờ hững: "Mẹ nói đúng đấy, em sang nhà ngoại vài hôm cho yên cửa yên nhà đi. Anh mệt mỏi với cảnh mẹ chồng nàng dâu này lắm rồi."

Chiếc va ly đựng vài bộ quần áo cũ của hai mẹ con bị em chồng ném thẳng ra giữa sân ướt sũng. Cánh cổng sắt nặng nề đóng sầm lại trước mắt tôi, khóa chặt bằng tiếng chốt lạnh lùng.

Tôi ôm con bước từng bước trên con đường vắng, nước mắt hòa lẫn nước mưa buốt giá. Trong túi tôi lúc đó chỉ còn vỏn vẹn 45 nghìn đồng, điện thoại thì gần cạn pin. Tôi không dám gọi về cho bố mẹ ở quê vì sợ hai cụ tuổi già sức yếu không chịu nổi cú sốc này.

Nhưng tôi đã quên mất một điều... Bảy năm trước, anh trai tôi đã rời quê hương đi làm ăn xa. Suốt ngần ấy năm, ai cũng nghĩ anh chỉ là một gã lang bạt vô tích sự. Cho đến khi chiếc điện thoại gần sập nguồn của tôi rung lên một tin nhắn lạ..."""
                    },
                    {
                        "part_number": 2,
                        "title": "Phần 2: Tiếng Động Cơ Gầm Rú Và Cuộc Chạm Trán Định Mệnh",
                        "content": """Màn hình điện thoại le lói chút ánh sáng cuối cùng hiện lên dòng tin nhắn: "Bé Út, em đang ở đâu? Anh đã về tới đầu thị trấn."

Là anh Lâm - anh trai tôi! Bảy năm bặt vô âm tín, người anh từng cõng tôi đi qua bao mùa lũ lụt của tuổi thơ đã trở về đúng vào khoảnh khắc tôi tuyệt vọng nhất.

Tôi vội vàng bấm gọi lại với đôi tay run rẩy: "Anh ơi... cứu mẹ con em... Nhà họ đuổi em ra đường rồi..."

Chưa kịp nói hết địa chỉ, điện thoại tắt phụt. Tôi ngồi sụp xuống mái hiên của một cửa hàng tạp hóa đóng cửa, cởi áo khoác ngoài quấn chặt lấy con gái đang sốt nhẹ.

Chỉ đúng 15 phút sau, tiếng gầm rú vang dội của động cơ xé toạc màn mưa đêm. Ánh đèn pha cực mạnh quét thẳng vào góc hiên nơi tôi đang co ro. Không phải một chiếc, mà là cả một đoàn xe phân khối lớn và hai chiếc SUV đen bóng rẽ nước lao tới.

Người đàn ông bước xuống đầu tiên mặc áo khoác da phong trần, vai rộng như núi. Khi anh tháo mũ bảo hiểm ra, dù khuôn mặt đã có thêm vài vết sẹo sương gió, tôi vẫn nhận ra ngay đôi mắt ấm áp quen thuộc.

"Út! Ai làm em ra nông nỗi này?" - Giọng anh Lâm gầm lên, nghẹn lại khi thấy tôi ướt sũng, run rẩy ôm đứa bé.

Đêm hôm đó, đoàn xe không đưa tôi về khách sạn ngay. Anh Lâm bảo tài xế chở tôi và con vào bệnh viện kiểm tra trước, còn anh cùng những người anh em quay xe thẳng về hướng căn nhà ba tầng của gia đình chồng tôi.

Khi cánh cổng sắt bị đập vang rền lúc 1 giờ sáng, mẹ chồng tôi tức tối chạy ra chửi bới: "Đứa nào dám phá cửa nhà này giữa đêm thế hả?". Nhưng khi cổng mở ra, nhìn thấy hàng chục người đàn ông cao lớn cùng dàn xe sang đậu kín con ngõ, mặt bà ta cắt không còn một giọt máu..."""
                    },
                    {
                        "part_number": 3,
                        "title": "Phần 3: Cái Kết Thấu Tình Đạt Lý Và Bài Học Nhớ Đời",
                        "content": """Anh Lâm không hề dùng đến bạo lực. Anh bước vào nhà, bình thản kéo ghế ngồi đối diện với cả gia đình chồng tôi đang run như cầy sấy.

Hóa ra, bảy năm qua ở nước ngoài, anh tôi không phải đi lang bạt mà cùng bạn bè gầy dựng một tập đoàn vận tải và chuỗi cung ứng logistics quy mô lớn. Chiếc xe SUV đưa anh về chỉ là một trong số hàng chục chiếc xe của doanh nghiệp anh.

"Tôi nghe nói gia đình bác chê em gái tôi nhà nghèo, không môn đăng hộ đối, lại còn chê nó sinh cháu gái?" - Anh Lâm rút từ trong cặp ra một tệp tài liệu dày đặt lên bàn.

Đó chính là hợp đồng cung ứng vật liệu xây dựng độc quyền cho công ty của chồng tôi - hợp đồng mà suốt 6 tháng qua công ty anh ta đang sống dở chết dở để xin ký kết. Người ký duyệt cuối cùng của tập đoàn đầu tư đối tác... chính là Tổng giám đốc Trần Văn Lâm.

Chồng tôi lúc này hai chân mềm nhũn, quỳ sụp xuống van xin: "Anh Lâm... con xin lỗi anh... em không biết... Xin anh bỏ qua cho gia đình em, xin anh đừng hủy hợp đồng..."

Mẹ chồng tôi trước đó còn cao giọng xua đuổi, giờ lắp bắp không nói nên lời: "Bác... bác chỉ là đùa giỡn chút thôi cháu à, mẹ con nó giận dỗi bác bảo về ngoại chơi mấy hôm chứ ai nỡ đuổi..."

Anh Lâm cười nhạt, ánh mắt lạnh băng: "Gia đình các người đối xử với mẹ con em gái tôi thế nào, trời đất đều thấy. Hợp đồng này chính thức chấm dứt. Còn đơn ly hôn, sáng mai luật sư của tôi sẽ mang sang tận nơi."

Ngày tôi dọn sạch đồ đạc rời đi, tôi ngẩng cao đầu bước lên chiếc xe đưa mẹ con tôi đến một cuộc sống mới. Đứa con gái nhỏ của tôi sau này sẽ lớn lên trong tình thương và lòng tự trọng, chứ không bao giờ phải chịu sự khinh khi của những kẻ coi trọng đồng tiền hơn nhân phẩm.

Cuộc đời này luôn có luật nhân quả tuần hoàn. Khi bạn gieo sự tàn nhẫn, bạn sẽ nhận lại sự cô độc."""
                    }
                ]
            },
            {
                "title": "Bí Mật Của Chiếc Hộp Gỗ Cũ Dưới Gầm Giường Người Mẹ Kế",
                "slug": "bi-mat-chiec-hop-go-cu-duoi-gam-giuong-me-ke",
                "excerpt": "Suốt 15 năm, tôi luôn căm ghét người mẹ kế kiệm lời và keo kiệt. Chỉ đến ngày bà qua đời, mở chiếc hộp gỗ khóa chặt dưới gầm giường, tôi mới bật khóc nức nở...",
                "cover_image": "https://images.unsplash.com/photo-1544717305-2782549b5136?auto=format&fit=crop&w=1000&q=80",
                "category_id": 2,
                "is_featured": 1,
                "reading_time": 5,
                "parts": [
                    {
                        "part_number": 1,
                        "title": "Phần 1: Sự Nghi Ngờ Suốt Mười Lăm Năm Dài",
                        "content": """Mẹ ruột tôi mất năm tôi lên bảy tuổi. Một năm sau, bố tôi dẫn về một người phụ nữ gầy gò, ít nói tên Lan để làm mẹ kế.

Từ ngày về chung một nhà, bà Lan chưa từng một lần cười đùa với tôi. Bữa cơm gia đình lúc nào cũng đạm bạc: rau luộc, đậu phụ và cá kho mặn chát. Ngay cả khi bố tôi đưa tiền sinh hoạt khá dư dả, bà vẫn chắt bóp từng đồng, đi chợ mặc cả từng cọng hành.

Tôi ghét cay ghét đắng sự keo kiệt của bà. Những lần tôi xin tiền mua sách tham khảo hay đóng tiền học thêm, bà đều ghi chép cẩn thận vào một cuốn sổ nhỏ và tra hỏi cặn kẽ từng khoản mục.

"Tiền không phải vỏ hến mà phung phí," - Đó là câu nói cửa miệng của bà khiến tôi phát ngấy suốt những năm tháng tuổi thơ.

Năm tôi thi đỗ đại học Y Hà Nội, bố tôi lâm bệnh nặng rồi qua đời. Mọi người họ hàng đều lắc đầu bảo tôi phải bỏ học đi làm công nhân kiếm sống vì "bà mẹ kế chắc chắn sẽ ôm tiền bỏ đi".

Thế nhưng, bà Lan lại bất ngờ đưa cho tôi một cọc tiền vừa đủ đóng học phí kỳ đầu tiên, nói ngắn gọn: "Lên trường mà học cho đàng hoàng. Thiếu tiền thì gọi về."

Suốt 6 năm đại học, cứ đúng ngày đầu tháng, tài khoản tôi lại nhận được đúng số tiền ăn ở tối thiểu. Tôi tốt nghiệp, trở thành bác sĩ nội trú, có việc làm ổn định ở thủ đô và hiếm khi về thăm lại ngôi nhà cũ, nơi bà mẹ kế già nua vẫn cặm cụi sống một mình..."""
                    },
                    {
                        "part_number": 2,
                        "title": "Phần 2: Chiếc Hộp Khóa Chặt Và Sự Thật Đau Lòng",
                        "content": """Một buổi chiều mùa đông, tôi nhận được cuộc gọi từ trưởng thôn báo tin bà Lan đã qua đời trong giấc ngủ sau một cơn đột quỵ.

Tôi vội vã bắt xe về quê trong tâm trạng bối rối. Căn nhà ngói ba gian vẫn lạnh lẽo và cũ kỹ như xưa, chẳng có lấy một món đồ đắt tiền nào.

Sau khi lo xong tang lễ chu tất cho bà, theo lời dặn của bác trưởng thôn, tôi bước vào căn phòng nhỏ của bà Lan. Dưới gầm giường phủ đầy bụi là một chiếc hộp gỗ lim cũ kỹ, bên ngoài khóa bằng một ổ khóa đồng nhỏ.

Chiếc chìa khóa được giấu cẩn thận dưới đáy bát hương của bố tôi. Khi chiếc nắp hộp bật mở, những thứ bên trong khiến tôi chết lặng...

Không phải vàng bạc châu báu, mà là hàng chục cuốn sổ tiết kiệm nhỏ, từng tập biên lai gửi tiền viện phí của bố tôi năm xưa, và một tập giấy khám bệnh đã ố vàng mang tên Trần Thị Lan.

Tờ kết quả xét nghiệm ghi rõ: Bà đã phát hiện bị suy thận mãn tính giai đoạn cuối từ 10 năm trước. Bác sĩ yêu cầu chạy thận nhân tạo định kỳ, nhưng ở góc dưới có chữ ký từ chối điều trị của bà với dòng chữ nắn nót: "Tôi xin tự nguyện điều trị bằng thuốc nam tại nhà để tiết kiệm chi phí".

Bà đã từ chối cứu sống chính mình, chấp nhận chịu đựng những cơn đau thể xác hành hạ suốt cả thập kỷ, chỉ để dành từng đồng bạc lẻ nuôi tôi học xong 6 năm trường Y!

Kẹp trong cuốn sổ tay là một bức thư ngắn viết nguệch ngoạc gửi cho tôi: "Thành à, con tha lỗi cho mẹ vì đã không thể làm một người mẹ dịu dàng. Mẹ sợ nếu nuông chiều, con sẽ không thể tự đứng vững khi bố mẹ không còn. Số tiền trong hộp này là toàn bộ tiền mẹ tích cóp và tiền bán mẫu ruộng sau nhà, đủ để con đặt cọc mua một căn hộ nhỏ ở thành phố..."

Tôi quỳ sụp xuống sàn nhà lạnh ngắt, ôm chặt chiếc hộp gỗ vào lòng và khóc nấc lên như một đứa trẻ. Sự hy sinh thầm lặng của người phụ nữ mà tôi từng ghét bỏ hóa ra lại vĩ đại đến nhường này!"""
                    }
                ]
            },
            {
                "title": "Vị Khách Ăn Mày Và Tờ Hóa Đơn Một Trăm Triệu Trong Quán Cơm Bình Dân",
                "slug": "vi-khach-an-may-va-to-hoa-don-tram-trieu",
                "excerpt": "Ông lão ăn mày rách rưới vào quán xin một bát cơm nguội chan nước canh. Cô chủ quán trẻ không những không xua đuổi mà còn làm một suất cơm nóng hổi...",
                "cover_image": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1000&q=80",
                "category_id": 4,
                "is_featured": 1,
                "reading_time": 4,
                "parts": [
                    {
                        "part_number": 1,
                        "title": "Phần 1: Bát Cơm Nóng Giữa Chiều Mưa Rét",
                        "content": """Quán cơm bình dân của Mai nằm nép mình ở một góc phố nhỏ gần bến xe miền Tây. Trời đã xế chiều, mưa phùn bắt đầu rơi hạt nặng hơn, khách khứa trong quán thưa thớt dần.

Mai đang dọn dẹp bàn ghế thì nhìn thấy một bóng dáng tiều tụy đứng thập thò trước cửa. Đó là một ông lão chừng gần 70 tuổi, quần áo rách rưới vá chằng vá đụp, đôi chân trần lem luốc bùn đất. Ông run rẩy ngập ngừng nhìn vào tủ kính thức ăn.

Vài vị khách còn ngồi trong quán nhíu mày khó chịu, có người còn lớn tiếng: "Chủ quán đâu, đuổi gã ăn mày này đi chứ nhìn bẩn thỉu mất vệ sinh quá!"

Mai không hề bực bội. Cô bước nhanh ra cửa, nhẹ nhàng hỏi: "Bác ơi, bác đói bụng lắm phải không ạ?"

Ông lão lúng túng, xòe bàn tay thô ráp chỉ có vỏn vẹn vài tờ tiền lẻ rách nát: "Cô ơi... tôi làm mất hết tiền xe về quê, đói quá... Cô có bát cơm nguội nào thừa chan chút nước canh cho tôi xin, tôi gửi chỗ tiền này..."

Mai nhìn ánh mắt đầy tủi hổ của ông lão, lòng nhói đau. Cô kéo ghế mời ông ngồi vào một bàn góc ấm cúng: "Bác cất tiền đi ạ. Hôm nay quán cháu có phần cơm đặc biệt tặng bác."

Cô tự tay xới một bát cơm đầy ắp, xếp thịt kho trứng, đùi gà chiên mắm và một bát canh xương nóng hổi bốc khói nghi ngút bưng ra cho ông..."""
                    },
                    {
                        "part_number": 2,
                        "title": "Phần 2: Sự Đền Đáp Đầy Bất Ngờ",
                        "content": """Ông lão nhìn khay cơm thịnh soạn mà hai mắt đỏ hoe. Ông ăn từng miếng một cách trân trọng, như thể đây là bữa ăn ngon nhất đời mình.

Sau khi ăn xong, ông xin phép dùng nhờ nhà vệ sinh để rửa mặt và thay chiếc áo cũ. Khi ông bước ra, Mai đã chuẩn bị sẵn một hộp cơm khác kèm một chai nước suối và 200 nghìn đồng nhét vào tay ông: "Bác cầm thêm chút lộ phí để bắt xe về quê nhé ạ."

Ông lão nhìn sâu vào mắt Mai, mỉm cười gật đầu rồi lặng lẽ rời đi trong cơn mưa chiều.

Ba tháng sau, quán cơm của Mai rơi vào biến cố lớn. Chủ nhà bất ngờ thông báo đòi lại mặt bằng để bán cho một tập đoàn địa ốc với giá cao, buộc cô phải dọn đi trong vòng một tuần dù hợp đồng thuê vẫn còn hạn. Mai đứng trước nguy cơ mất trắng toàn bộ vốn liếng đầu tư tu sửa quán.

Đúng vào ngày hạn cuối, một chiếc xe Maybach sang trọng bất ngờ dừng trước cửa quán. Bước xuống xe là một người đàn ông lớn tuổi phong độ trong bộ vest lịch lãm, đi cùng hai trợ lý và luật sư.

Mai ngỡ ngàng khi nhận ra giọng nói quen thuộc: "Cô chủ quán tốt bụng, còn nhận ra tôi không?"

Chính là ông lão ăn mày ngày mưa năm đó! Hóa ra ông là Chủ tịch một tập đoàn bất động sản lớn, hôm đó đi khảo sát thực tế khu vực quy hoạch thì không may bị cướp giật túi xách và điện thoại.

"Lòng tốt và nhân cách của cháu ngày hôm đó là thứ quý giá nhất ta từng gặp," - Vị chủ tịch trao cho Mai một tập hồ sơ đỏ. Đó là hợp đồng bàn giao toàn bộ quyền sở hữu mặt bằng căn nhà này cho Mai, với giá trị chuyển nhượng tượng trưng: đúng bằng giá của một suất cơm gà!

Lòng tốt trao đi bằng sự chân thành, sớm hay muộn cũng sẽ nở hoa kết trái."""
                    }
                ]
            }
        ]

        for s in sample_stories:
            cursor.execute("""
            INSERT INTO stories (title, slug, excerpt, cover_image, category_id, is_featured, reading_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (s["title"], s["slug"], s["excerpt"], s["cover_image"], s["category_id"], s["is_featured"], s["reading_time"]))
            story_id = cursor.lastrowid

            for p in s["parts"]:
                cursor.execute("""
                INSERT INTO story_parts (story_id, part_number, title, content)
                VALUES (?, ?, ?, ?)
                """, (story_id, p["part_number"], p["title"], p["content"]))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
