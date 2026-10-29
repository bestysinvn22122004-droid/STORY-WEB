import os
import sys
import time
import streamlit as st
from story_scraper import UniversalStoryScraper

# =========================================================================
# CONFIGURATION & PAGE SETUP
# =========================================================================
st.set_page_config(
    page_title="Universal Story Scraper - Cloud Edition",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for clean, high-contrast modern UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #10b981, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    .stat-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 12px 18px;
        text-align: center;
    }
    .stat-number {
        font-size: 1.8rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .stat-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 6px;
        background-color: #334155;
        color: #f1f5f9;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Tuỳ Chọn Quét Truyện")
        filter_chapter_titles = st.checkbox(
            "Lọc bỏ tiêu đề Chapter (Chapter 1, Chương 1...)",
            value=True,
            help="Tự động loại bỏ các dòng tiêu đề chương để câu chuyện liền mạch 100% khi đọc hoặc đưa vào website."
        )
        st.markdown("---")
        st.markdown("### 🚀 Công Nghệ Cào Đa Tầng")
        st.markdown("""
        1. **Mục lục thông minh (TOC):** Tự động nhận diện danh sách toàn bộ chương.
        2. **Bắt nút Next Chapter:** Tự động lần theo liên kết trang tiếp để cào trọn vẹn đến hết truyện.
        3. **Thích ứng cấu trúc URL:** Tự động dò mẫu `/chapter-N`, `/part-N`, `?page=N`.
        4. **Lọc sạch 100% rác:** Xóa quảng cáo, mạng xã hội, nút chia sẻ.
        """)
        st.markdown("---")
        st.caption("Universal Novel Scraper Cloud v3.0 • Ready for Render")

    # Main Header
    st.markdown('<div class="main-header">📖 Universal Story Scraper (Cloud Edition)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Cào trọn vẹn 100% mọi chương trên bất kỳ trang web truyện nào, tự động lọc sạch quảng cáo và rác.</div>', unsafe_allow_html=True)

    # Input Form
    with st.form("scraper_form"):
        story_url = st.text_input(
            "📌 Dán link web truyện bất kỳ (Chương 1 hoặc trang truyện gốc):",
            placeholder="https://spotlight.treeiq.biz/blog/... hoặc https://stories.thebustednews.com/p/... hoặc https://newsfeed.cafex.biz/..."
        )
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            submit_btn = st.form_submit_button("🚀 BẮT ĐẦU CÀO", type="primary", use_container_width=True)

    # Scrape Execution
    if submit_btn:
        if not story_url.strip():
            st.warning("⚠️ Vui lòng nhập đường link web truyện.")
        else:
            with st.status("📖 Đang cào toàn bộ các chương truyện...", expanded=True) as status_box:
                try:
                    scraper = UniversalStoryScraper()
                    result = scraper.scrape_story(
                        story_url.strip(),
                        filter_chapter_titles=filter_chapter_titles,
                        status_callback=lambda msg: status_box.write(msg)
                    )
                    status_box.update(
                        label=f"🎉 Hoàn thành cào {result['total_chapters']} chương ({result['total_words']:,} từ)!",
                        state="complete"
                    )
                    st.session_state["scraped_story"] = result
                except Exception as e:
                    status_box.update(label=f"❌ Có lỗi xảy ra: {e}", state="error")
                    st.error(f"Chi tiết lỗi: {e}")

    # Result View
    if "scraped_story" in st.session_state:
        res = st.session_state["scraped_story"]
        st.markdown("---")
        st.subheader(f"📖 {res['title']}")
        st.caption(f"Nguồn: [{res['url']}]({res['url']})")

        # Stat cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{res['total_chapters']}</div>
                <div class="stat-label">Tổng Số Chương</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{res['total_paragraphs']}</div>
                <div class="stat-label">Đoạn Văn Sạch</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{res['total_words']:,}</div>
                <div class="stat-label">Tổng Số Từ</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">~{res['read_time_mins']}p</div>
                <div class="stat-label">Thời Gian Đọc</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Download & Copy actions
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            st.download_button(
                label="⬇️ TẢI FILE TRUYỆN .TXT VỀ MÁY",
                data=res["full_text"],
                file_name=res["file_name"],
                mime="text/plain",
                type="primary",
                use_container_width=True
            )
        with col_act2:
            st.button(
                "📋 Nội dung đã sẵn sàng để sao chép bên dưới",
                disabled=True,
                use_container_width=True
            )

        # Content tabs
        tab_full, tab_chapters = st.tabs(["📄 Toàn Văn Truyện (Dạng Text)", "📑 Xem Từng Chương"])

        with tab_full:
            st.caption("👉 Bấm vào icon Copy ở góc trên bên phải khung chữ dưới đây để sao chép toàn bộ truyện:")
            st.code("\n\n".join(res["paragraphs"]), language="text")

        with tab_chapters:
            if res.get("chapter_details"):
                for ch in res["chapter_details"]:
                    with st.expander(f"Chương {ch['chapter']} ({len(ch['paragraphs'])} đoạn)"):
                        st.write("\n\n".join(ch["paragraphs"]))
            else:
                st.info("Truyện đơn trang không phân chương.")

if __name__ == "__main__":
    main()
