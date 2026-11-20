import os
import io
import sys
import time
import zipfile
import streamlit as st
from story_scraper import UniversalStoryScraper
from video_analyzer import (
    analyze_facebook_video, load_default_instruction, is_facebook_url,
    VideoAnalyzerError, DEFAULT_MODEL, available_models,
    load_saved_instructions, save_instruction, delete_instruction,
)
import story_publisher as publisher

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


AUTO_PUBLISH_LABEL = "📤 Tự đăng lên web truyện sau khi xong"


def publish_scraped(item: dict, write=None) -> None:
    """Publishes a scraped story (already chunked) and records the outcome on the item."""
    try:
        out = publisher.publish_story(
            item["title"], item.get("formatted_chapters_text", ""),
            chapters=item.get("chapter_chunks") or None, status_callback=write,
        )
        item["publish"] = {"ok": True, "chapters": out["chapters"], "posts": out["posts"],
                           "series_url": out.get("series_url", "")}
    except publisher.PublishError as e:
        item["publish"] = {"ok": False, "error": str(e)}
    except Exception as e:
        item["publish"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}


def render_publish_box(item: dict, key: str) -> None:
    """Shows the publish outcome of a scraped story, or a manual publish button."""
    if not publisher.is_configured():
        return
    pub = item.get("publish")
    if pub and pub.get("ok"):
        first = (pub.get("posts") or [{}])[0].get("link")
        msg = f"✅ Đã đăng lên {publisher.site_name()}: {pub['chapters']} chương."
        if first:
            msg += f" [Mở Chapter 1]({first})"
        if pub.get("series_url"):
            msg += f" · [Quản lý series]({pub['series_url']})"
        st.success(msg)
        return
    if pub and not pub.get("ok"):
        st.error(f"❌ Đăng lên web thất bại: {pub['error']}")
    label = "🔁 THỬ ĐĂNG LẠI" if pub else f"📤 ĐĂNG LÊN WEB TRUYỆN ({publisher.site_name()})"
    if st.button(label, key=key, use_container_width=True):
        with st.spinner("Đang đăng lên web truyện..."):
            publish_scraped(item)
        st.rerun()


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
    tab_single, tab_batch, tab_video = st.tabs([
        "📖 Cào 1 Truyện (Single)",
        "📚 Cào Hàng Loạt (Batch Scrape)",
        "🎬 Phân Tích Video Facebook",
    ])

    # =========================================================================
    # TAB 1: SINGLE STORY SCRAPE
    # =========================================================================
    with tab_single:
        with st.form("single_scraper_form"):
            story_url = st.text_input(
                "📌 Dán link web truyện bất kỳ (Chương 1 hoặc trang truyện gốc):",
                placeholder="https://spotlight.treeiq.biz/blog/... hoặc https://stories.thebustednews.com/p/... hoặc https://newsfeed.cafex.biz/..."
            )
            auto_publish_single = publisher.is_configured() and st.toggle(
                AUTO_PUBLISH_LABEL, value=True, key="auto_publish_single",
                help="Bật: cào xong tự tạo series và đăng toàn bộ chapter lên web truyện. Tắt: bạn tự bấm nút đăng sau.",
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
                        if auto_publish_single:
                            publish_scraped(result, write=lambda msg: status_box.write(msg))
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
            render_publish_box(res, key="publish_single_btn")

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
            auto_publish_batch = publisher.is_configured() and st.toggle(
                AUTO_PUBLISH_LABEL, value=True, key="auto_publish_batch",
                help="Bật: mỗi truyện cào xong sẽ tự đăng lên web truyện. Tắt: tự bấm nút đăng ở từng truyện.",
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
                        if auto_publish_batch:
                            status_text.markdown(f"**[{idx}/{len(urls)}]** Đang đăng lên web: `{res['title']}`...")
                            publish_scraped(res)
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
                        render_publish_box(item, key=f"publish_batch_{i}")
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

    # =========================================================================
    # TAB 3: FACEBOOK VIDEO -> LLM ANALYSIS
    # =========================================================================
    with tab_video:
        st.markdown("### 🎬 Phân Tích Video Facebook Bằng AI")
        st.markdown(
            "Dán link **video Facebook công khai**. Hệ thống tải video về, gửi cho Gemini kèm "
            "instruction bên dưới và hiển thị kết quả để bạn **copy 1 click**."
        )

        NEW_INSTRUCTION = "➕ Instruction mới (bắt đầu từ bản mặc định)"

        # A save/delete click happens after the selectbox has been drawn, so the
        # new selection is parked here and applied at the top of the next rerun.
        pending_choice = st.session_state.pop("_video_instr_pending", None)
        if pending_choice is not None:
            st.session_state["video_instr_choice"] = pending_choice
            st.session_state.pop("_video_instr_loaded", None)

        col_url, col_model = st.columns([3, 1])
        with col_url:
            video_url = st.text_input(
                "🔗 Link video Facebook:",
                placeholder="https://www.facebook.com/watch/?v=1234567890 hoặc https://fb.watch/xxxx/",
                key="video_url",
            )
        with col_model:
            video_model = st.selectbox(
                "🧠 Model:",
                options=available_models(),
                index=0,
                key="video_model",
                help="Mặc định là model ổn định nhất. Nếu model chọn quá tải (503/504), hệ thống tự chuyển sang model dự phòng.",
            )

        # ----- Instruction: default toggle / saved library -------------------
        st.markdown("#### 📝 Instruction gửi cho AI")
        default_instruction = load_default_instruction()
        use_default = st.toggle(
            "Dùng instruction mặc định của hệ thống",
            value=True,
            key="video_use_default",
            help="Bật: dùng bản mặc định trên server. Tắt: chọn một instruction đã lưu hoặc tự soạn / lưu bản mới.",
        )

        if use_default:
            instruction_text = default_instruction
            with st.expander("👁️ Xem instruction mặc định", expanded=False):
                st.text_area(
                    "Instruction mặc định:",
                    value=default_instruction,
                    height=260,
                    disabled=True,
                    label_visibility="collapsed",
                )
        else:
            saved = load_saved_instructions()
            saved_names = list(saved.keys())
            options = [NEW_INSTRUCTION] + saved_names
            if st.session_state.get("video_instr_choice") not in options:
                st.session_state["video_instr_choice"] = NEW_INSTRUCTION
                st.session_state.pop("_video_instr_loaded", None)

            choice = st.selectbox(
                "📚 Instruction đã lưu:",
                options=options,
                key="video_instr_choice",
                help=f"Đã lưu {len(saved_names)} instruction. Danh sách dùng chung cho mọi người truy cập web.",
            )
            # Reload the editor only when the selection changes, so edits survive reruns.
            if st.session_state.get("_video_instr_loaded") != choice:
                st.session_state["video_instr_editor"] = (
                    default_instruction if choice == NEW_INSTRUCTION else saved.get(choice, "")
                )
                st.session_state["_video_instr_loaded"] = choice

            instruction_text = st.text_area(
                "Nội dung instruction:",
                key="video_instr_editor",
                height=320,
                help="Sửa thoải mái; bấm 💾 Lưu để giữ lại dưới một tên, lần sau chọn lại từ danh sách.",
            )

            col_name, col_save, col_del = st.columns([3, 1, 1])
            with col_name:
                save_name = st.text_input(
                    "Tên để lưu:",
                    value="" if choice == NEW_INSTRUCTION else choice,
                    placeholder="VD: Phân tích cinematic V3",
                    label_visibility="collapsed",
                )
            with col_save:
                if st.button("💾 Lưu", use_container_width=True):
                    try:
                        saved_as = save_instruction(save_name, instruction_text)
                        st.session_state["_video_instr_pending"] = saved_as
                        st.toast(f"Đã lưu instruction “{saved_as}”.", icon="✅")
                        st.rerun()
                    except VideoAnalyzerError as e:
                        st.error(str(e))
            with col_del:
                if st.button("🗑️ Xoá", use_container_width=True, disabled=(choice == NEW_INSTRUCTION)):
                    delete_instruction(choice)
                    st.session_state["_video_instr_pending"] = NEW_INSTRUCTION
                    st.toast(f"Đã xoá instruction “{choice}”.", icon="🗑️")
                    st.rerun()

        auto_publish_video = publisher.is_configured() and st.toggle(
            AUTO_PUBLISH_LABEL, value=False, key="auto_publish_video",
            help="Bật: phân tích xong tự đăng kết quả lên web truyện, tên series lấy từ dòng đầu kết quả. Tắt (mặc định): xem kết quả rồi tự bấm nút đăng.",
        )
        submit_video_btn = st.button("🚀 PHÂN TÍCH VIDEO", type="primary", use_container_width=True)

        if submit_video_btn:
            if not video_url.strip():
                st.warning("⚠️ Vui lòng dán link video Facebook.")
            elif not is_facebook_url(video_url):
                st.warning("⚠️ Link phải thuộc facebook.com hoặc fb.watch.")
            elif not instruction_text.strip():
                st.warning("⚠️ Instruction đang trống.")
            else:
                status_box = st.status("Đang xử lý...", expanded=True)
                try:
                    with status_box:
                        result = analyze_facebook_video(
                            video_url,
                            instruction_text,
                            model=video_model,
                            status_callback=lambda m: st.write(m),
                        )
                    st.session_state["video_result"] = result
                    st.session_state.pop("publish_result", None)
                    st.session_state.pop("publish_seed", None)
                    if auto_publish_video:
                        auto_title = publisher.guess_title(result["text"])
                        try:
                            with status_box:
                                pub_res = publisher.publish_story(
                                    auto_title, result["text"], status_callback=lambda m: st.write(m))
                            st.session_state["publish_seed"] = f"{result.get('url', '')}|{len(result['text'])}"
                            st.session_state["publish_title"] = auto_title
                            st.session_state["publish_intro"] = ""
                            st.session_state["publish_series_id"] = ""
                            st.session_state["publish_result"] = pub_res
                        except Exception as e:
                            st.session_state["video_publish_error"] = str(e)
                    status_box.update(label="✅ Hoàn thành!", state="complete", expanded=False)
                except VideoAnalyzerError as e:
                    status_box.update(label="❌ Lỗi", state="error", expanded=True)
                    st.error(str(e))
                    st.session_state.pop("video_result", None)
                except Exception as e:
                    status_box.update(label="❌ Lỗi", state="error", expanded=True)
                    st.error(f"Lỗi không mong muốn: {type(e).__name__}: {e}")
                    st.session_state.pop("video_result", None)

        if st.session_state.get("video_result"):
            res = st.session_state["video_result"]
            st.markdown("---")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Model", res.get("model", DEFAULT_MODEL))
            c2.metric("Thời gian", f"{res.get('elapsed_s', 0)}s")
            c3.metric("Video", f"{res.get('video_size_mb', 0)} MB")
            tok = res.get("prompt_tokens")
            c4.metric("Tokens vào/ra", f"{tok or '-'} / {res.get('output_tokens') or '-'}")
            st.caption(f"Nguồn: {res.get('url', '')}")

            st.download_button(
                label="⬇️ TẢI KẾT QUẢ .TXT",
                data=res["text"],
                file_name=f"video_analysis_{int(time.time())}.txt",
                mime="text/plain",
                use_container_width=True,
            )
            st.caption("👉 Bấm icon Copy ở góc trên bên phải khung dưới đây để sao chép toàn bộ kết quả:")
            st.code(res["text"], language="text")

            # ----- Publish to the story site ---------------------------------
            st.markdown("---")
            if not publisher.is_configured():
                st.info("📤 Chưa cấu hình web truyện (STORY_SITE_URL + tài khoản hoặc token trên server) nên chưa đẩy được.")
            else:
                result_key = f"{res.get('url', '')}|{len(res['text'])}"
                if st.session_state.get("publish_seed") != result_key:
                    # new analysis result -> reseed the publish form
                    st.session_state["publish_seed"] = result_key
                    st.session_state["publish_title"] = publisher.guess_title(res["text"])
                    st.session_state["publish_intro"] = ""
                    st.session_state["publish_series_id"] = ""
                    st.session_state.pop("publish_result", None)

                auto_err = st.session_state.pop("video_publish_error", None)
                if auto_err:
                    st.error(f"❌ Tự đăng thất bại: {auto_err}. Bạn có thể sửa tên rồi bấm đăng lại bên dưới.")
                with st.expander(f"📤 Đẩy lên web truyện ({publisher.site_name()})", expanded=True):
                    col_t, col_s = st.columns([3, 1])
                    with col_t:
                        pub_title = st.text_input("📖 Tên truyện / series:", key="publish_title")
                    with col_s:
                        pub_series_id = st.text_input(
                            "ID series có sẵn (tuỳ chọn):", key="publish_series_id",
                            help="Để trống để web tự tạo series mới từ tên truyện. Điền ID để thêm chương vào series đã có.",
                        )
                    pub_intro = st.text_area(
                        "Mô tả series (tuỳ chọn, hiện trước Chapter 1):", key="publish_intro", height=80,
                    )
                    try:
                        preview = publisher.split_into_chapters(res["text"], pub_title or "")
                        n_words = sum(len(" ".join(c["paragraphs"]).split()) for c in preview)
                        st.caption(
                            f"Sẽ tạo **{len(preview)} chương** (~{n_words:,} từ). "
                            + ("Nội dung đã có sẵn marker CHAPTER nên giữ nguyên cách chia." if publisher.has_chapter_markers(res["text"])
                               else f"Chia tự động ~{publisher.CHAPTER_WORDS} từ/chương, tiêu đề dạng CHAPTER X - TÊN TRUYỆN.")
                        )
                    except Exception as e:
                        preview = []
                        st.warning(f"Không xem trước được: {e}")

                    already = st.session_state.get("publish_result")
                    if already:
                        st.success(f"✅ Đã đẩy lên: {already['chapters']} chương.")
                        for p in already["posts"]:
                            if p.get("link"):
                                st.markdown(f"- [{p.get('title') or p.get('slug')}]({p['link']})")
                            else:
                                st.markdown(f"- {p.get('title') or p.get('slug') or p.get('id')}")
                        st.markdown(f"[Mở trang quản lý series]({already.get('series_url', '')})")
                        label, kind = "🔁 ĐẨY LẠI (tạo bản mới)", "secondary"
                    else:
                        label, kind = "📤 ĐẨY LÊN WEB TRUYỆN", "primary"

                    if st.button(label, type=kind, use_container_width=True, disabled=not preview):
                        if not (pub_title or "").strip():
                            st.warning("⚠️ Nhập tên truyện trước.")
                        elif pub_series_id.strip() and not pub_series_id.strip().isdigit():
                            st.warning("⚠️ ID series phải là số.")
                        else:
                            pub_box = st.status("Đang đẩy lên web truyện...", expanded=True)
                            try:
                                with pub_box:
                                    pub_res = publisher.publish_story(
                                        pub_title, res["text"], intro=pub_intro,
                                        series_id=int(pub_series_id) if pub_series_id.strip() else None,
                                        status_callback=lambda m: st.write(m),
                                    )
                                pub_box.update(label="✅ Đã đẩy xong!", state="complete", expanded=False)
                                st.session_state["publish_result"] = pub_res
                                st.rerun()
                            except publisher.PublishError as e:
                                pub_box.update(label="❌ Lỗi", state="error", expanded=True)
                                st.error(str(e))
                            except Exception as e:
                                pub_box.update(label="❌ Lỗi", state="error", expanded=True)
                                st.error(f"Lỗi không mong muốn: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
