import os
import io
import sys
import time
import zipfile
import streamlit as st
from story_scraper import UniversalStoryScraper

# =========================================================================
# CONFIGURATION & PAGE SETUP
# =========================================================================
st.set_page_config(
    page_title="Universal Story Scraper - Cloud & Batch Edition",
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
    .badge-success {
        background-color: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
</style>
""", unsafe_allow_html=True)


def create_zip_archive(stories_results: list) -> bytes:
    """Creates a downloadable .zip archive containing all scraped .txt files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, s in enumerate(stories_results):
            if s.get("status") == "success" and s.get("full_text"):
                filename = s.get("file_name") or f"Story_{idx+1}.txt"
                zf.writestr(filename, s["full_text"])
    return buf.getvalue()


def main():
    # -------------------------------------------------------------------------
    # SIDEBAR CONFIGURATION
    # -------------------------------------------------------------------------
    with st.sidebar:
        st.markdown("### ⚙️ Tuỳ Chọn Chia Chapter")
        
        chunk_by_words = st.checkbox(
            "Tự động tách Chapter (~400 từ/chap)",
            value=True,
            help="Tự động chia đều toàn bộ truyện thành các Chapter khoảng 400 từ, có đánh dấu 'Chapter 1', 'Chapter 2'..."
        )

        words_per_chapter = st.number_input(
            "Số từ ước tính mỗi Chapter:",
            min_value=150,
            max_value=2000,
            value=400,
            step=50,
            help="Mặc định là 400 từ theo chuẩn web truyện và đọc tiện lợi."
        ) if chunk_by_words else 400

        filter_chapter_titles = st.checkbox(
            "Lọc bỏ tiêu đề Chapter cũ (Chapter 1, Chương 1...)",
            value=True,
            help="Tự động loại bỏ các tiêu đề chương cũ của trang gốc để câu chuyện liền mạch 100% trước khi chia lại."
        )

        st.markdown("---")
        st.markdown("### 🚀 Công Nghệ Cào Đa Tầng")
        st.markdown("""
        1. **Mục lục thông minh (TOC):** Tự quét toàn bộ chương có sẵn.
        2. **Bắt nút Next Chapter:** Lần theo liên kết trang tiếp đến hết truyện.
        3. **Dò mẫu URL:** Tự động bắt pattern `/chapter-N`, `/part-N`, `?page=N`.
        4. **Tách Chapter ~400 từ:** Gắn sẵn `Chapter 1`, `Chapter 2`... ở đầu mỗi phần.
        """)
        st.markdown("---")
        st.caption("Universal Story Scraper Cloud v3.5 • Batch & 400-Word Engine")

    # Header
    st.markdown('<div class="main-header">📖 Universal Story Scraper Studio</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-header">Cào trọn vẹn 100% mọi chương trên bất kỳ website nào • Tự động chia Chapter (~{words_per_chapter} từ/chap) • Hỗ trợ cào hàng loạt</div>',
        unsafe_allow_html=True
    )

    # Tabs for Single and Batch
    tab_single, tab_batch = st.tabs(["📖 Cào 1 Truyện (Single)", "📚 Cào Hàng Loạt (Batch Scrape)"])

    # =========================================================================
    # TAB 1: SINGLE STORY SCRAPE
    # =========================================================================
    with tab_single:
        with st.form("single_scraper_form"):
            story_url = st.text_input(
                "📌 Dán link web truyện bất kỳ (Chương 1 hoặc trang truyện gốc):",
                placeholder="https://spotlight.treeiq.biz/blog/... hoặc https://stories.thebustednews.com/p/... hoặc https://newsfeed.cafex.biz/..."
            )
            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                submit_single_btn = st.form_submit_button("🚀 BẮT ĐẦU CÀO", type="primary", use_container_width=True)

        if submit_single_btn:
            if not story_url.strip():
                st.warning("⚠️ Vui lòng nhập đường link web truyện.")
            else:
                with st.status("📖 Đang cào toàn bộ các chương và tách Chapter...", expanded=True) as status_box:
                    try:
                        scraper = UniversalStoryScraper()
                        result = scraper.scrape_story(
                            story_url.strip(),
                            filter_chapter_titles=filter_chapter_titles,
                            chunk_by_words=chunk_by_words,
                            words_per_chapter=words_per_chapter,
                            status_callback=lambda msg: status_box.write(msg)
                        )
                        status_box.update(
                            label=f"🎉 Hoàn thành! Đã tạo {result['total_chapters']} Chapter ({result['total_words']:,} từ)!",
                            state="complete"
                        )
                        st.session_state["scraped_story"] = result
                    except Exception as e:
                        status_box.update(label=f"❌ Có lỗi xảy ra: {e}", state="error")
                        st.error(f"Chi tiết lỗi: {e}")

        # Display Single Result
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
                    <div class="stat-label">Chapter (~{words_per_chapter} từ)</div>
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

            # Action Buttons
            col_act1, col_act2 = st.columns(2)
            with col_act1:
                st.download_button(
                    label=f"⬇️ TẢI FILE .TXT VỀ MÁY ({res['total_chapters']} Chapters)",
                    data=res["full_text"],
                    file_name=res["file_name"],
                    mime="text/plain",
                    type="primary",
                    use_container_width=True
                )
            with col_act2:
                st.button(
                    f"✅ Đã gắn 'Chapter 1, 2...' ở mỗi ~{words_per_chapter} từ",
                    disabled=True,
                    use_container_width=True
                )

            # Sub-tabs for viewing
            tab_full, tab_chapters = st.tabs(["📄 Toàn Văn Truyện (Chia Chapter 1, 2...)", "📑 Xem Từng Chapter (~400 từ)"])

            with tab_full:
                st.caption("👉 Bấm vào icon Copy ở góc trên bên phải khung chữ dưới đây để sao chép toàn bộ truyện (có sẵn Chapter 1, Chapter 2...):")
                st.code(res["formatted_chapters_text"], language="text")

            with tab_chapters:
                st.markdown(f"**Danh sách {len(res['chapter_chunks'])} Chapter đã được chia tự động:**")
                for ch in res["chapter_chunks"]:
                    with st.expander(f"📖 {ch['chapter_title']} ({ch['word_count']} từ - {len(ch['paragraphs'])} đoạn)"):
                        st.caption("Bấm copy ở góc trên bên phải khung dưới đây:")
                        st.code(f"{ch['chapter_title']}\n\n{ch['content']}", language="text")

    # =========================================================================
    # TAB 2: BATCH SCRAPING (CÀO HÀNG LOẠT)
    # =========================================================================
    with tab_batch:
        st.markdown("### 📚 Cào Hàng Loạt Nhiều Truyện Cùng Lúc")
        st.markdown("Dán danh sách các đường link web truyện (mỗi link nằm trên 1 dòng). Hệ thống sẽ tự động cào lần lượt toàn bộ, lọc sạch rác, tách Chapter (~400 từ) và cho phép bạn **tải về trọn bộ file ZIP** chỉ với 1 click!")

        with st.form("batch_scraper_form"):
            batch_urls_text = st.text_area(
                "📌 Danh sách link truyện (mỗi dòng 1 link):",
                placeholder="https://stories.treeiq.biz/blog/story-1\nhttps://news.treeiq.biz/blog/story-2\nhttps://stories.thebustednews.com/p/story-3",
                height=180
            )
            submit_batch_btn = st.form_submit_button("🚀 BẮT ĐẦU CÀO HÀNG LOẠT", type="primary")

        if submit_batch_btn:
            urls = [u.strip() for u in batch_urls_text.splitlines() if u.strip().startswith("http")]
            if not urls:
                st.warning("⚠️ Vui lòng nhập ít nhất một đường link web truyện hợp lệ (bắt đầu bằng http:// hoặc https://).")
            else:
                st.info(f"🚀 Bắt đầu tiến trình cào **{len(urls)}** truyện...")
                progress_bar = st.progress(0.0)
                status_text = st.empty()

                batch_results = []
                scraper = UniversalStoryScraper()

                for idx, url in enumerate(urls, 1):
                    status_text.markdown(f"**[{idx}/{len(urls)}]** Đang cào: `{url}`...")
                    try:
                        res = scraper.scrape_story(
                            url,
                            filter_chapter_titles=filter_chapter_titles,
                            chunk_by_words=chunk_by_words,
                            words_per_chapter=words_per_chapter
                        )
                        res["status"] = "success"
                        batch_results.append(res)
                    except Exception as e:
                        batch_results.append({
                            "status": "error",
                            "url": url,
                            "error": str(e),
                            "title": "Lỗi cào truyện",
                            "total_chapters": 0,
                            "total_words": 0
                        })

                    progress_bar.progress(idx / len(urls))
                    time.sleep(0.5)

                status_text.markdown(f"🎉 **Đã hoàn thành quét {len(urls)} truyện!**")
                st.session_state["batch_results"] = batch_results

        # Display Batch Results
        if "batch_results" in st.session_state:
            b_results = st.session_state["batch_results"]
            successful_items = [b for b in b_results if b.get("status") == "success"]
            st.markdown("---")
            st.subheader(f"📊 Kết Quả Cào Hàng Loạt: Thành công {len(successful_items)}/{len(b_results)} truyện")

            # Download ALL as ZIP
            if successful_items:
                zip_data = create_zip_archive(successful_items)
                st.download_button(
                    label=f"📦 TẢI VỀ TOÀN BỘ {len(successful_items)} TRUYỆN (FILE .ZIP)",
                    data=zip_data,
                    file_name=f"Stories_Batch_Export_{int(time.time())}.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True
                )

            st.markdown("<br>", unsafe_allow_html=True)

            # Details list
            for i, item in enumerate(b_results, 1):
                if item.get("status") == "success":
                    with st.expander(f"✅ #{i}: {item['title']} — {item['total_chapters']} Chapters ({item['total_words']:,} từ)"):
                        st.caption(f"Nguồn: {item['url']}")
                        c1, c2 = st.columns([1, 3])
                        with c1:
                            st.download_button(
                                label="⬇️ Tải file .txt truyện này",
                                data=item["full_text"],
                                file_name=item["file_name"],
                                mime="text/plain",
                                key=f"dl_batch_{i}",
                                use_container_width=True
                            )
                        st.caption("Sao chép toàn văn (đã chia Chapter 1, 2...):")
                        st.code(item["formatted_chapters_text"], language="text")
                else:
                    with st.expander(f"❌ #{i}: Lỗi tại link: {item['url']}"):
                        st.error(f"Chi tiết lỗi: {item.get('error')}")


if __name__ == "__main__":
    main()
