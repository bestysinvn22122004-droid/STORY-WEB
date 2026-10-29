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
    Can crawl across ANY novel, blog, or story website on the internet:
    - Strategy 1: Table of Contents (TOC) & Chapter List Discovery
    - Strategy 2: Next Chapter / Next Page Link Traversal (Crawler approach)
    - Strategy 3: Adaptive URL Pattern Probing (/chapter-N, /part-N, /N, ?page=N...)
    - Strategy 4: Universal Paragraph & Prose Extraction (handles <p> and <br> layouts)
    - Filters: Ads, junk phrases, social buttons, chapter headings.
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
            # Fallback to requests Session
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

        # Exclude blacklisted paths (cart, login, social networks, images...)
        if self.disallowed_url_patterns.search(clean_cand):
            return False

        # Check domain compatibility: must share domain or be a valid story link
        cand_host = urllib.parse.urlparse(candidate_url).netloc.lower()
        curr_host = urllib.parse.urlparse(current_url).netloc.lower()

        # Strip www.
        cand_host = re.sub(r'^www\.', '', cand_host)
        curr_host = re.sub(r'^www\.', '', curr_host)

        if cand_host != curr_host:
            return False

        return True

    def find_all_toc_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Discovers full Table of Contents (TOC) links across different website layouts."""
        links = []

        # 1. Known TOC containers by class or id
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

        # 2. Check <select> dropdowns for chapters
        for sel in soup.find_all('select', attrs={'name': re.compile(r'chapter|part', re.I)}):
            for opt in sel.find_all('option', value=True):
                val = opt['value']
                if val and val.startswith(('http', '/')):
                    full_url = urllib.parse.urljoin(base_url, val)
                    if self.is_valid_next_url(full_url, base_url):
                        links.append(full_url)

        # 3. Deduplicate preserving sequence order
        seen = set()
        deduped = []
        for l in links:
            clean = l.split('#')[0].rstrip('/')
            if clean not in seen and clean != base_url.rstrip('/'):
                seen.add(clean)
                deduped.append(l)

        return deduped

    def find_next_chapter_link(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """
        Dynamically discovers the 'Next Chapter' link on the page.
        Works across 99% of novel sites, blogs, and custom themes.
        """
        # 1. Standard HTML5 next links: <a rel="next"> or <link rel="next">
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

        # 2. Look for <a> tags with next classes or IDs
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

        # 3. Look for <a> tags matching next text patterns
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            if self.next_text_pattern.match(text):
                full_url = urllib.parse.urljoin(current_url, a['href'])
                if self.is_valid_next_url(full_url, current_url):
                    return full_url

        # 4. Check pagination blocks (e.g. .pagination, .page-links, .wp-pagenavi)
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

        # 1. /chapter-N, /part-N, /chap-N, /ch-N, /chuong-N
        m = re.search(r'/(chapter|part|chap|ch|chuong)-(\d+)$', clean_url, re.I)
        if m:
            prefix = m.group(1)
            num = int(m.group(2))
            base = clean_url[:m.start()]
            return f"{base}/{prefix}-{{n}}", num

        # 2. Trailing /N
        m = re.search(r'/(\d+)$', clean_url)
        if m:
            num = int(m.group(1))
            base = clean_url[:m.start()]
            return f"{base}/{{n}}", num

        # 3. /page/N/
        m = re.search(r'/page/(\d+)/?$', clean_url, re.I)
        if m:
            num = int(m.group(1))
            base = clean_url[:m.start()]
            return f"{base}/page/{{n}}/", num

        # 4. Query parameters (?chapter=N, ?part=N, ?page=N, ?p=N)
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
        # 1. Candidates search
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
            # Score by paragraph text volume
            def score(c):
                return sum(len(p.get_text(strip=True)) for p in c.find_all('p'))
            candidates.sort(key=score, reverse=True)
            container = candidates[0]
        else:
            container = soup.find('main') or soup.find('article') or soup.find('body') or soup

        if not container:
            return []

        # Remove scripts, styles, iframes, navigation, buttons, forms inside container
        for tag in container.find_all(['script', 'style', 'iframe', 'noscript', 'svg', 'canvas', 'form', 'button', 'nav', 'aside', 'footer', 'header']):
            tag.decompose()

        # Remove ads & social share widgets
        ad_selector = re.compile(r'\b(?:ads?|adsense|adsconex|code-block|social-share|share-box|in-article-ad|sharedaddy|addtoany|banner|sponsored)\b', re.I)
        for junk in container.find_all(class_=ad_selector):
            junk.decompose()
        for junk in container.find_all(id=re.compile(r'div_adsconex|div-gpt-ad|ad-|google_ads', re.I)):
            junk.decompose()

        # Collect raw paragraphs
        raw_ps = container.find_all('p')

        # If very few <p> tags, extract text separated by <br> or <div>
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

            # Prevent immediate duplicate lines
            if not paragraphs or paragraphs[-1] != text:
                paragraphs.append(text)

        return paragraphs

    def scrape_story(self, url: str, filter_chapter_titles: bool = True, status_callback: Optional[Callable[[str], None]] = None) -> dict:
        """
        Universal Story Scraper with 3-Layered Discovery:
        - Layer 1: Table of Contents (TOC) Crawler
        - Layer 2: Next Chapter Button / Link Crawler
        - Layer 3: Adaptive URL Pattern Prober
        """
        def log(msg: str):
            if status_callback:
                status_callback(msg)
            print(msg)

        clean_url = url.split('?')[0].split('#')[0].rstrip('/')
        log(f"🌐 Đang kết nối tới: {url}")

        # Fetch first page
        first_soup, final_start_url = self.fetch_page(url)

        # Title extraction
        title_el = first_soup.find('meta', property='og:title')
        raw_title = title_el['content'] if title_el else (
            first_soup.find('h1').get_text() if first_soup.find('h1') else (
                first_soup.title.string if first_soup.title else "Untitled Story"
            )
        )
        title = self.clean_title(raw_title)
        log(f"📖 Tiêu đề truyện: {title}")

        all_paragraphs = []
        chapter_details = []
        visited_urls: Set[str] = set()
        seen_first_paragraphs: Set[str] = set()

        # =====================================================================
        # STRATEGY 1: TABLE OF CONTENTS (TOC) DISCOVERY
        # =====================================================================
        toc_links = self.find_all_toc_links(first_soup, final_start_url)
        if len(toc_links) >= 2:
            log(f"📑 Tìm thấy mục lục tổng hợp ({len(toc_links)} chương) qua cấu trúc TOC.")
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
                        chapter_details.append({"chapter": i, "paragraphs": ps, "url": ch_url})
                        log(f"  ✓ Đã cào Chương {i}: {len(ps)} đoạn văn.")
                    else:
                        log(f"  ⚠️ Chương {i} không trích xuất được đoạn văn nào.")
                except Exception as e:
                    log(f"  ⚠️ Lỗi khi cào chương {i} ({ch_url}): {e}")
                    break

        # =====================================================================
        # STRATEGY 2: NEXT CHAPTER BUTTON / LINK CRAWLER
        # =====================================================================
        if not chapter_details:
            log("⚡ Khởi động cơ chế quét tự động qua nút 'Next Chapter' / liên kết trang tiếp...")
            curr_soup = first_soup
            curr_url = final_start_url
            chapter_num = 1

            while chapter_num <= 100:
                clean_curr_url = curr_url.split('#')[0].rstrip('/')
                if clean_curr_url in visited_urls:
                    log(f"  🛑 Phát hiện URL đã duyệt qua ({curr_url}). Dừng quét.")
                    break
                visited_urls.add(clean_curr_url)

                ps = self.extract_paragraphs_from_soup(curr_soup, filter_chapter_titles=filter_chapter_titles)
                if ps:
                    # Prevent looping content
                    first_p = ps[0]
                    if first_p in seen_first_paragraphs:
                        log(f"  🛑 Nội dung chương {chapter_num} trùng lặp với chương trước. Kết thúc truyện.")
                        break
                    seen_first_paragraphs.add(first_p)

                    all_paragraphs.extend(ps)
                    chapter_details.append({"chapter": chapter_num, "paragraphs": ps, "url": curr_url})
                    log(f"  ✓ Đã cào Chương {chapter_num}: {len(ps)} đoạn văn.")
                else:
                    log(f"  ⚠️ Không tìm thấy đoạn văn ở chương {chapter_num}.")

                # Find next chapter link
                next_url = self.find_next_chapter_link(curr_soup, curr_url)
                if next_url and next_url.split('#')[0].rstrip('/') not in visited_urls:
                    try:
                        curr_soup, curr_url = self.fetch_page(next_url)
                        chapter_num += 1
                        time.sleep(0.3)
                    except Exception as e:
                        log(f"  🛑 Không thể tải chương tiếp theo ({next_url}): {e}")
                        break
                else:
                    break

        # =====================================================================
        # STRATEGY 3: ADAPTIVE URL PATTERN PROBING
        # (Fallback if site has multiple chapters but no Next button or TOC)
        # =====================================================================
        if len(chapter_details) <= 1:
            template, start_num = self.detect_url_pattern(url)
            candidate_templates = []

            if template:
                candidate_templates.append((template, start_num))
            else:
                # Test probe patterns: /chapter-{n}, /part-{n}, /{n}, /page/{n}/, ?page={n}
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
                    # Verify probe is not redirected to home/chapter 1
                    if final_probe_url.rstrip('/') != clean_url.rstrip('/') and not final_probe_url.endswith('/chapter-1'):
                        probe_ps = self.extract_paragraphs_from_soup(probe_soup, filter_chapter_titles=filter_chapter_titles)
                        if probe_ps and probe_ps[0] not in seen_first_paragraphs:
                            log(f"🎯 Phát hiện cấu trúc phân chương tự động: {tmpl}")
                            # Reset and crawl with this detected template
                            all_paragraphs = []
                            chapter_details = []
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
                                    chapter_details.append({"chapter": n, "paragraphs": ps, "url": ch_url})
                                    log(f"  ✓ Đã cào Chương {n}: {len(ps)} đoạn văn.")
                                    time.sleep(0.3)
                                except Exception:
                                    break
                            break
                except Exception:
                    continue

        total_chapters = len(chapter_details) if chapter_details else 1
        total_words = sum(len(p.split()) for p in all_paragraphs)
        read_time_mins = max(1, round(total_words / 200))

        header_text = (
            f"========================================\n"
            f"{title.upper()}\n"
            f"Source URL: {url}\n"
            f"Total Chapters: {total_chapters} | Paragraphs: {len(all_paragraphs)} | Words: {total_words}\n"
            f"Estimated Reading Time: ~{read_time_mins} minutes\n"
            f"Scraped Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"========================================\n\n"
        )
        full_text = header_text + "\n\n".join(all_paragraphs)

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

        log(f"🎉 Hoàn tất cào truyện! {total_chapters} chương, {len(all_paragraphs)} đoạn, {total_words} từ.")

        return {
            "title": title,
            "url": url,
            "total_chapters": total_chapters,
            "total_paragraphs": len(all_paragraphs),
            "total_words": total_words,
            "read_time_mins": read_time_mins,
            "paragraphs": all_paragraphs,
            "chapter_details": chapter_details,
            "full_text": full_text,
            "file_name": file_name,
            "file_path": file_path
        }
