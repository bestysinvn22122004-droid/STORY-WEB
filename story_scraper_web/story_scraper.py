import os
import re
import sys
import time
import html as html_lib
import urllib.request
import urllib.parse
from typing import Optional, Callable, List, Dict, Tuple, Set
from bs4 import BeautifulSoup
import requests

class UniversalStoryScraper:
    """
    Universal Novel / Web Story Scraper (Multi-Strategy Engine).
    Supports TreeIQ, The Busted News, Cafex, Onplusnews, Hadoo, WPVina, Cotich, Dekorstyling, and ANY novel website.
    Features:
    - Multi-Strategy Crawling (TOC -> Next Button Crawler -> Adaptive URL Probing)
    - Auto-chunking into ~400 words chapters with 'Chapter 1', 'Chapter 2' headers
    - 100% junk and ad removal
    - Batch scraping compatible
    """

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_dir = output_dir
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.output_dir = os.path.join(base_dir, "output", "stories")

        os.makedirs(self.output_dir, exist_ok=True)

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Upgrade-Insecure-Requests': '1'
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.chapter_regex = re.compile(
            r'^(?:(?:Chapter|Chương|Part|Phần|Ch\.|Hồi|Tập)\s*\d+.*|PART\s*\d+\s*[:\-–—].*)$',
            re.I
        )

        self.next_text_pattern = re.compile(
            r'^(?:next(?:\s*(?:chapter|part|page|post|story))?[\s»>]*|chương\s*(?:sau|tiếp)|tiếp\s*theo|đọc\s*tiếp|part\s*\d+|chapter\s*\d+|\s*»\s*|\s*>\s*|\s*>>\s*|continue\s*reading.*)$',
            re.I
        )

        self.junk_phrases = [
            'may you like', 'next chapter', 'previous chapter', 'share this',
            'share on facebook', 'share on twitter', 'whatsapp', 'linkedin',
            'pinterest', 'reddit', 'telegram', 'follow us', 'read more',
            'table of contents', 'mục lục', 'gợi ý cho bạn', 'bình luận',
            'leave a comment', 'post comment', 'see also', 'related posts',
            'tags:', 'categories:', 'author:', 'published in', 'subscribe to our'
        ]

        self.disallowed_url_patterns = re.compile(
            r'/(?:category|tag|author|login|register|cart|checkout|wp-admin|privacy-policy|terms|contact|about)(?:/|$)|'
            r'(?:facebook\.com|twitter\.com|x\.com|pinterest\.com|reddit\.com|t\.me|linkedin\.com)|\.(?:jpg|jpeg|png|gif|webp|svg|pdf|mp4)$',
            re.I
        )

    def format_chapter_title(self, n: int, story_title: str = "") -> str:
        """Heading for each auto-split chunk: 'CHAPTER X - STORY TITLE'."""
        t = (story_title or "").strip()
        return f"CHAPTER {n} - {t.upper()}" if t else f"CHAPTER {n}"

    def clean_title(self, title: str) -> str:
        if not title:
            return "Untitled Story"
        t = html_lib.unescape(title).strip()
        t = re.sub(r'^(?:Chapter|Chương|Part|Phần)\s*\d+\s*[-:–—]\s*', '', t, flags=re.I)
        t = re.sub(r'\s*[-:–—]\s*(?:Chapter|Chương|Part|Phần)\s*\d+.*$', '', t, flags=re.I)
        t = re.sub(r'\s*\|\s*.*$', '', t)
        t = re.sub(r'\s*–\s*.*$', '', t) if '–' in t and len(t.split('–')[-1]) < 30 else t
        t = re.sub(r'\s*-\s*(?:TreeIQ|The Busted News|Stories|Novelplus|Onplusnews|Cafex|Hadoo|Cotich|WPVina|Dekorstyling).*$', '', t, flags=re.I)
        return t.strip() or "Untitled Story"

    def fetch_page(self, url: str) -> Tuple[BeautifulSoup, str]:
        """Fetches page HTML with fallback to requests session."""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=18) as resp:
                final_url = resp.geturl()
                html = resp.read().decode('utf-8', errors='ignore')
                return BeautifulSoup(html, 'html.parser'), final_url
        except Exception:
            resp = self.session.get(url, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, 'html.parser'), resp.url

    def is_valid_next_url(self, candidate_url: str, current_url: str) -> bool:
        if not candidate_url or not candidate_url.startswith(('http://', 'https://')):
            return False

        clean_cand = candidate_url.split('#')[0].rstrip('/')
        clean_curr = current_url.split('#')[0].rstrip('/')

        if clean_cand == clean_curr:
            return False

        if self.disallowed_url_patterns.search(clean_cand):
            return False

        cand_host = urllib.parse.urlparse(candidate_url).netloc.lower()
        curr_host = urllib.parse.urlparse(current_url).netloc.lower()

        cand_host = re.sub(r'^www\.', '', cand_host)
        curr_host = re.sub(r'^www\.', '', curr_host)

        if cand_host != curr_host:
            return False

        return True

    def find_all_toc_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Discovers full Table of Contents (TOC) links across different website layouts."""
        links = []

        toc_containers = soup.find_all(
            ['div', 'ul', 'ol', 'nav', 'section'],
            class_=re.compile(r'\b(?:chapter-toc|toc|chapter-list|list-chapter|table-of-contents|all-chapters|chapters-list|wp-block-table-of-contents|list-item|chapter-nav)\b', re.I)
        )

        for cid in ['chapter-toc-list-desktop', 'chapter-toc-modal', 'toc', 'chapters', 'chapter-list', 'list-chapter']:
            el = soup.find(id=cid)
            if el and el not in toc_containers:
                toc_containers.append(el)

        for container in toc_containers:
            for a in container.find_all('a', href=True):
                full_url = urllib.parse.urljoin(base_url, a['href'])
                if self.is_valid_next_url(full_url, base_url):
                    links.append(full_url)

        for sel in soup.find_all('select', attrs={'name': re.compile(r'chapter|part', re.I)}):
            for opt in sel.find_all('option', value=True):
                val = opt['value']
                if val and val.startswith(('http', '/')):
                    full_url = urllib.parse.urljoin(base_url, val)
                    if self.is_valid_next_url(full_url, base_url):
                        links.append(full_url)

        seen = set()
        deduped = []
        for l in links:
            clean = l.split('#')[0].rstrip('/')
            if clean not in seen and clean != base_url.rstrip('/'):
                seen.add(clean)
                deduped.append(l)

        return deduped

    def find_next_chapter_link(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Dynamically discovers the 'Next Chapter' link on the page."""
        for rel_tag in soup.find_all(['a', 'link'], rel=True):
            rel_vals = rel_tag.get('rel', [])
            if isinstance(rel_vals, str):
                rel_vals = [rel_vals]
            if any('next' in r.lower() for r in rel_vals):
                href = rel_tag.get('href')
                if href:
                    full_url = urllib.parse.urljoin(current_url, href)
                    if self.is_valid_next_url(full_url, current_url):
                        return full_url

        next_class_pattern = re.compile(
            r'\b(?:next|next-chapter|next-post|btn-next|chapter-next|nav-next|next_page|page-next|nav-next-button|next-link)\b',
            re.I
        )
        for a in soup.find_all('a', class_=next_class_pattern, href=True):
            full_url = urllib.parse.urljoin(current_url, a['href'])
            if self.is_valid_next_url(full_url, current_url):
                return full_url

        for a in soup.find_all('a', id=re.compile(r'\b(?:next|next-chapter|btn-next)\b', re.I), href=True):
            full_url = urllib.parse.urljoin(current_url, a['href'])
            if self.is_valid_next_url(full_url, current_url):
                return full_url

        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            if self.next_text_pattern.match(text):
                full_url = urllib.parse.urljoin(current_url, a['href'])
                if self.is_valid_next_url(full_url, current_url):
                    return full_url

        page_nav = soup.find(class_=re.compile(r'\b(?:pagination|page-links|nav-links|wp-pagenavi|post-page-numbers|chapter-pagination)\b', re.I))
        if page_nav:
            curr_el = page_nav.find(class_=re.compile(r'\b(?:current|active)\b', re.I))
            if curr_el:
                next_a = curr_el.find_next('a', href=True)
                if next_a and next_a in page_nav.descendants:
                    full_url = urllib.parse.urljoin(current_url, next_a['href'])
                    if self.is_valid_next_url(full_url, current_url):
                        return full_url

        return None

    def detect_url_pattern(self, url: str) -> Tuple[Optional[str], int]:
        """Detects if url follows a numbered pattern (e.g. chapter-1, part-1, /1, ?page=1)."""
        clean_url = url.split('?')[0].split('#')[0].rstrip('/')

        m = re.search(r'/(chapter|part|chap|ch|chuong)-(\d+)$', clean_url, re.I)
        if m:
            prefix = m.group(1)
            num = int(m.group(2))
            base = clean_url[:m.start()]
            return f"{base}/{prefix}-{{n}}", num

        m = re.search(r'/(\d+)$', clean_url)
        if m:
            num = int(m.group(1))
            base = clean_url[:m.start()]
            return f"{base}/{{n}}", num

        m = re.search(r'/page/(\d+)/?$', clean_url, re.I)
        if m:
            num = int(m.group(1))
            base = clean_url[:m.start()]
            return f"{base}/page/{{n}}/", num

        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        for param in ['chapter', 'part', 'page', 'p']:
            if param in qs and qs[param][0].isdigit():
                num = int(qs[param][0])
                template = re.sub(rf'([?&]{param}=)\d+', rf'\g<1>{{n}}', url)
                return template, num

        return None, 1

    def extract_paragraphs_from_soup(self, soup: BeautifulSoup, filter_chapter_titles: bool = True) -> List[str]:
        """Extracts clean story paragraphs, handling both standard <p> and <br><br> layouts."""
        candidates = []
        named_selectors = [
            'div.prose', 'div.v5-prose', 'div.v4-prose',
            '#single-detail', '.deail-content', '.entry-content', '.post-content',
            '.story-content', '.novel-content', '.reading-content', '.chapter-content',
            '.text-left', '.content-story', '.article-content', '.post_content',
            '.td-post-content', '.elementor-widget-theme-post-content', 'article'
        ]
        for sel in named_selectors:
            for el in soup.select(sel):
                candidates.append(el)

        for el in soup.find_all(['div', 'article', 'section', 'main']):
            ps = el.find_all('p', recursive=False)
            if len(ps) >= 3:
                candidates.append(el)

        container = None
        if candidates:
            def score(c):
                return sum(len(p.get_text(strip=True)) for p in c.find_all('p'))
            candidates.sort(key=score, reverse=True)
            container = candidates[0]
        else:
            container = soup.find('main') or soup.find('article') or soup.find('body') or soup

        if not container:
            return []

        for tag in container.find_all(['script', 'style', 'iframe', 'noscript', 'svg', 'canvas', 'form', 'button', 'nav', 'aside', 'footer', 'header']):
            tag.decompose()

        ad_selector = re.compile(r'\b(?:ads?|adsense|adsconex|code-block|social-share|share-box|in-article-ad|sharedaddy|addtoany|banner|sponsored)\b', re.I)
        for junk in container.find_all(class_=ad_selector):
            junk.decompose()
        for junk in container.find_all(id=re.compile(r'div_adsconex|div-gpt-ad|ad-|google_ads', re.I)):
            junk.decompose()

        raw_ps = container.find_all('p')

        if len(raw_ps) < 3:
            text_content = ""
            for elem in container.descendants:
                if isinstance(elem, str):
                    text_content += elem
                elif elem.name in ['br', 'p', 'div']:
                    text_content += "\n"
            raw_lines = [line.strip() for line in text_content.split("\n")]
            raw_items = [l for l in raw_lines if len(l) >= 15]
        else:
            raw_items = []
            for p in raw_ps:
                t = html_lib.unescape(p.get_text()).strip()
                if t:
                    raw_items.append(t)

        paragraphs = []
        for text in raw_items:
            if len(text) < 15:
                continue

            if filter_chapter_titles:
                if self.chapter_regex.match(text):
                    continue
                if re.match(r'^PART\s*\d+\s*[:\-–—].*$', text, re.I):
                    continue

            text_lower = text.lower()
            if any(junk in text_lower for junk in self.junk_phrases):
                continue

            if not paragraphs or paragraphs[-1] != text:
                paragraphs.append(text)

        return paragraphs

    def chunk_paragraphs_by_words(self, paragraphs: List[str], target_words: int = 400, story_title: str = "") -> List[Dict]:
        """
        Groups paragraphs into chapters of approximately target_words (default 400 words).
        Ensures each chapter chunk starts with 'Chapter 1', 'Chapter 2', etc.
        Splits excessively long paragraphs along natural sentence boundaries.
        """
        if not paragraphs:
            return []

        def make_title(n: int) -> str:
            return self.format_chapter_title(n, story_title)

        # 1. Normalize and break down any excessively long paragraph (> target_words * 1.4)
        normalized_paragraphs = []
        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue
            words = p_clean.split()
            if len(words) > int(target_words * 1.4):
                sentences = re.split(r'(?<=[.!?])\s+', p_clean)
                curr_sent = []
                curr_sent_len = 0
                for s in sentences:
                    s_words = len(s.split())
                    if curr_sent and (curr_sent_len + s_words > target_words):
                        normalized_paragraphs.append(" ".join(curr_sent))
                        curr_sent = [s]
                        curr_sent_len = s_words
                    else:
                        curr_sent.append(s)
                        curr_sent_len += s_words
                if curr_sent:
                    normalized_paragraphs.append(" ".join(curr_sent))
            else:
                normalized_paragraphs.append(p_clean)

        # 2. Group into chapters around target_words
        chapters = []
        current_chapter_ps = []
        current_chapter_words = 0
        chapter_num = 1

        for p in normalized_paragraphs:
            p_words = len(p.split())
            if p_words == 0:
                continue

            # Check if current chapter has accumulated enough words
            if current_chapter_ps and (current_chapter_words >= target_words or (current_chapter_words >= int(target_words * 0.75) and (current_chapter_words + p_words) > int(target_words * 1.3))):
                chapters.append({
                    "chapter_num": chapter_num,
                    "chapter_title": make_title(chapter_num),
                    "paragraphs": current_chapter_ps,
                    "word_count": current_chapter_words,
                    "content": "\n\n".join(current_chapter_ps)
                })
                chapter_num += 1
                current_chapter_ps = []
                current_chapter_words = 0

            current_chapter_ps.append(p)
            current_chapter_words += p_words

        if current_chapter_ps:
            chapters.append({
                "chapter_num": chapter_num,
                "chapter_title": make_title(chapter_num),
                "paragraphs": current_chapter_ps,
                "word_count": current_chapter_words,
                "content": "\n\n".join(current_chapter_ps)
            })

        return chapters

    def scrape_story(
        self,
        url: str,
        filter_chapter_titles: bool = True,
        chunk_by_words: bool = True,
        words_per_chapter: int = 400,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> dict:
        """
        Scrapes full story across all chapters using multi-strategy cascading:
        1. TOC Discovery
        2. Next Chapter button/link traversal
        3. Adaptive URL pattern probing
        Then automatically partitions story into ~400 words chapters with Chapter 1, 2... headers.
        """
        def log(msg: str):
            if status_callback:
                status_callback(msg)
            print(msg)

        clean_url = url.split('?')[0].split('#')[0].rstrip('/')
        log(f"🔍 Đang truy cập URL truyện: {url}")

        first_soup, final_start_url = self.fetch_page(url)

        title_el = first_soup.find('meta', property='og:title')
        raw_title = title_el['content'] if title_el else (
            first_soup.find('h1').get_text() if first_soup.find('h1') else (
                first_soup.title.string if first_soup.title else "Untitled Story"
            )
        )
        title = self.clean_title(raw_title)
        log(f"📖 Tiêu đề truyện: {title}")

        all_paragraphs = []
        raw_chapter_details = []
        visited_urls: Set[str] = set()
        seen_first_paragraphs: Set[str] = set()

        # 1. TOC
        toc_links = self.find_all_toc_links(first_soup, final_start_url)
        if len(toc_links) >= 2:
            log(f"📑 Tìm thấy mục lục với {len(toc_links)} chương.")
            for i, ch_url in enumerate(toc_links, 1):
                clean_ch_url = ch_url.split('#')[0].rstrip('/')
                if clean_ch_url in visited_urls:
                    continue
                visited_urls.add(clean_ch_url)

                try:
                    soup, _ = self.fetch_page(ch_url) if i > 1 else (first_soup, final_start_url)
                    ps = self.extract_paragraphs_from_soup(soup, filter_chapter_titles=filter_chapter_titles)
                    if ps:
                        all_paragraphs.extend(ps)
                        raw_chapter_details.append({"chapter": i, "paragraphs": ps, "url": ch_url})
                        log(f"  ✓ Đã cào Chương {i}: {len(ps)} đoạn văn.")
                except Exception as e:
                    log(f"  ⚠️ Lỗi tại chương {i}: {e}")
                    break

        # 2. Next Button Crawler
        if not raw_chapter_details:
            log("⚡ Quét tự động qua nút 'Next Chapter' / liên kết trang tiếp...")
            curr_soup = first_soup
            curr_url = final_start_url
            chapter_num = 1

            while chapter_num <= 100:
                clean_curr_url = curr_url.split('#')[0].rstrip('/')
                if clean_curr_url in visited_urls:
                    break
                visited_urls.add(clean_curr_url)

                ps = self.extract_paragraphs_from_soup(curr_soup, filter_chapter_titles=filter_chapter_titles)
                if ps:
                    first_p = ps[0]
                    if first_p in seen_first_paragraphs:
                        log(f"  🛑 Nội dung chương {chapter_num} trùng lặp với chương trước. Kết thúc truyện.")
                        break
                    seen_first_paragraphs.add(first_p)

                    all_paragraphs.extend(ps)
                    raw_chapter_details.append({"chapter": chapter_num, "paragraphs": ps, "url": curr_url})
                    log(f"  ✓ Đã cào Chương {chapter_num}: {len(ps)} đoạn văn.")

                next_url = self.find_next_chapter_link(curr_soup, curr_url)
                if next_url and next_url.split('#')[0].rstrip('/') not in visited_urls:
                    try:
                        curr_soup, curr_url = self.fetch_page(next_url)
                        chapter_num += 1
                        time.sleep(0.3)
                    except Exception:
                        break
                else:
                    break

        # 3. Adaptive URL Probing
        if len(raw_chapter_details) <= 1:
            template, start_num = self.detect_url_pattern(url)
            candidate_templates = []

            if template:
                candidate_templates.append((template, start_num))
            else:
                base = clean_url
                candidate_templates.extend([
                    (f"{base}/chapter-{{n}}", 1),
                    (f"{base}/part-{{n}}", 1),
                    (f"{base}/{{n}}", 1),
                    (f"{base}/page/{{n}}/", 1),
                    (f"{base}?page={{n}}", 1),
                    (f"{base}?part={{n}}", 1),
                    (f"{base}?chapter={{n}}", 1)
                ])

            for tmpl, s_num in candidate_templates:
                probe_url = tmpl.format(n=2)
                if probe_url.split('#')[0].rstrip('/') in visited_urls:
                    continue

                try:
                    probe_soup, final_probe_url = self.fetch_page(probe_url)
                    if final_probe_url.rstrip('/') != clean_url.rstrip('/') and not final_probe_url.endswith('/chapter-1'):
                        probe_ps = self.extract_paragraphs_from_soup(probe_soup, filter_chapter_titles=filter_chapter_titles)
                        if probe_ps and probe_ps[0] not in seen_first_paragraphs:
                            log(f"🎯 Phát hiện cấu trúc phân chương: {tmpl}")
                            all_paragraphs = []
                            raw_chapter_details = []
                            visited_urls.clear()
                            seen_first_paragraphs.clear()

                            for n in range(1, 100):
                                ch_url = tmpl.format(n=n)
                                try:
                                    soup, final_u = self.fetch_page(ch_url)
                                    if n > 1 and (final_u.rstrip('/') == clean_url.rstrip('/') or final_u.endswith('/chapter-1')):
                                        break
                                    ps = self.extract_paragraphs_from_soup(soup, filter_chapter_titles=filter_chapter_titles)
                                    if not ps or ps[0] in seen_first_paragraphs:
                                        break
                                    seen_first_paragraphs.add(ps[0])

                                    all_paragraphs.extend(ps)
                                    raw_chapter_details.append({"chapter": n, "paragraphs": ps, "url": ch_url})
                                    log(f"  ✓ Đã cào Chương {n}: {len(ps)} đoạn văn.")
                                    time.sleep(0.3)
                                except Exception:
                                    break
                            break
                except Exception:
                    continue

        total_original_chapters = len(raw_chapter_details) if raw_chapter_details else 1
        total_words = sum(len(p.split()) for p in all_paragraphs)
        read_time_mins = max(1, round(total_words / 200))

        # Chunk paragraphs into ~400 words chapters (with 'Chapter 1', 'Chapter 2' headers)
        if chunk_by_words:
            chapter_chunks = self.chunk_paragraphs_by_words(all_paragraphs, target_words=words_per_chapter, story_title=title)
        else:
            chapter_chunks = [{
                "chapter_num": 1,
                "chapter_title": self.format_chapter_title(1, title),
                "paragraphs": all_paragraphs,
                "word_count": total_words,
                "content": "\n\n".join(all_paragraphs)
            }]

        total_chunks = len(chapter_chunks)

        # Build formatted chapters text
        chapter_blocks = []
        for ch in chapter_chunks:
            chapter_blocks.append(f"{ch['chapter_title']}\n\n" + "\n\n".join(ch['paragraphs']))
        formatted_chapters_text = "\n\n\n".join(chapter_blocks)

        header_text = (
            f"========================================\n"
            f"{title.upper()}\n"
            f"Source URL: {url}\n"
            f"Total Words: {total_words:,} | Total Chapters: {total_chunks} (~{words_per_chapter} words/chapter)\n"
            f"Estimated Reading Time: ~{read_time_mins} minutes\n"
            f"Scraped Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"========================================\n\n"
        )
        full_text = header_text + formatted_chapters_text

        safe_title = re.sub(r'[\\/*?:"<>|’‘“”\']', '', title)
        safe_title = safe_title.replace('—', '-').replace('–', '-').strip()[:80]
        if not safe_title:
            safe_title = f"Story_{int(time.time())}"
        file_name = f"{safe_title}.txt"
        file_path = os.path.join(self.output_dir, file_name)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_text)
        except Exception:
            pass

        log(f"🎉 Hoàn tất cào truyện! {total_chunks} chương (~{words_per_chapter} từ/chương), {len(all_paragraphs)} đoạn văn, {total_words:,} từ.")
        log(f"💾 File truyện đã được lưu: {file_path}")

        return {
            "title": title,
            "url": url,
            "total_original_chapters": total_original_chapters,
            "total_chapters": total_chunks,
            "total_paragraphs": len(all_paragraphs),
            "total_words": total_words,
            "read_time_mins": read_time_mins,
            "paragraphs": all_paragraphs,
            "raw_chapter_details": raw_chapter_details,
            "chapter_chunks": chapter_chunks,
            "formatted_chapters_text": formatted_chapters_text,
            "full_text": full_text,
            "file_name": file_name,
            "file_path": file_path
        }
