"""
Story Publisher
===============
Pushes a story (plain text, e.g. the output of the video analyzer) to a
Blogbio-based story site through its public REST API:

    POST {STORY_SITE_URL}/api/posts   with mode="chapter"

In chapter mode the site creates the series itself: everything before the
first "CHAPTER N - Title" line becomes the series description and every
marker becomes one chapter post.  So one request = one series + N chapters.

Configuration (environment variables):
    STORY_SITE_URL          required - e.g. https://example.com (no trailing /api)
    STORY_SITE_TOKEN        API token (sent as Bearer) for the public /api
    STORY_SITE_EMAIL        admin login e-mail  } when both are set the admin
    STORY_SITE_PASSWORD     admin login password} session API is used instead
                            (/admin/api/v1/posts/chapter-batch), same call the
                            admin "Create post > Chapter" form makes
    STORY_SITE_CATEGORY_ID  optional - default category id for new posts
    STORY_SITE_AUTHOR       optional - username on the site to credit as author
    STORY_SITE_TIMEOUT_S    optional - HTTP timeout per request (default 120)
    STORY_CHAPTER_WORDS     optional - target words per chapter (default 400)
"""
import os
import re
import sys
import html
import json
from typing import Callable, List, Optional

import requests

from story_scraper import UniversalStoryScraper

SITE_URL = os.environ.get("STORY_SITE_URL", "").strip().rstrip("/")
SITE_TOKEN = os.environ.get("STORY_SITE_TOKEN", "").strip()
SITE_EMAIL = os.environ.get("STORY_SITE_EMAIL", "").strip()
SITE_PASSWORD = os.environ.get("STORY_SITE_PASSWORD", "")
SITE_CATEGORY_ID = os.environ.get("STORY_SITE_CATEGORY_ID", "").strip()
SITE_AUTHOR = os.environ.get("STORY_SITE_AUTHOR", "").strip()
TIMEOUT_S = int(os.environ.get("STORY_SITE_TIMEOUT_S", "120"))
CHAPTER_WORDS = int(os.environ.get("STORY_CHAPTER_WORDS", "400"))

CHAPTER_MARKER_RE = re.compile(r"^\s*(?:#+\s*|\*\*)?CHAPTER\s+(\d+)\s*[-–—:]\s*(.*?)(?:\*\*)?\s*$", re.I)


class PublishError(Exception):
    """User-facing error (safe to show in the UI)."""


def use_session() -> bool:
    return bool(SITE_URL and SITE_EMAIL and SITE_PASSWORD)


def is_configured() -> bool:
    return bool(SITE_URL and (SITE_TOKEN or use_session()))


def site_name() -> str:
    return re.sub(r"^https?://", "", SITE_URL)


def _log(cb: Optional[Callable[[str], None]], msg: str) -> None:
    if cb:
        cb(msg)


# ---------------------------------------------------------------------------
# Text -> chapter content
# ---------------------------------------------------------------------------
def _clean_line(line: str) -> str:
    """Strips markdown decorations the LLM tends to add around titles."""
    line = line.strip()
    line = re.sub(r"^#+\s*", "", line)
    line = re.sub(r"^\*\*(.*)\*\*$", r"\1", line)
    line = re.sub(r"^[\"“”']+|[\"“”']+$", "", line)
    return line.strip()


def guess_title(text: str) -> str:
    """First non-empty line that is not a chapter marker, max 200 chars."""
    for line in (text or "").splitlines():
        clean = _clean_line(line)
        if clean and not CHAPTER_MARKER_RE.match(clean):
            return clean[:200]
    return ""


def has_chapter_markers(text: str) -> bool:
    return any(CHAPTER_MARKER_RE.match(l) for l in (text or "").splitlines())


def split_into_chapters(text: str, story_title: str, target_words: int = CHAPTER_WORDS) -> List[dict]:
    """
    Returns [{"chapter_num", "chapter_title", "paragraphs"}].
    If the text already carries CHAPTER N - Title markers they are respected
    (renumbered 1..N); otherwise the text is chunked by ~target_words like the
    scraper tab does.
    """
    lines = (text or "").splitlines()

    if has_chapter_markers(text):
        chapters, current = [], None
        for line in lines:
            m = CHAPTER_MARKER_RE.match(line)
            if m:
                current = {"chapter_num": len(chapters) + 1, "chapter_title": "", "paragraphs": []}
                sub = _clean_line(m.group(2))
                current["chapter_title"] = f"CHAPTER {current['chapter_num']} - {sub.upper() if sub else story_title.upper()}"
                chapters.append(current)
            elif current is not None:
                clean = line.strip()
                if clean:
                    current["paragraphs"].append(clean)
        return [c for c in chapters if c["paragraphs"]]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    # drop the title line if it is the first paragraph
    if paragraphs and _clean_line(paragraphs[0]) == story_title:
        paragraphs = paragraphs[1:]
    paragraphs = [" ".join(p.split("\n")) for p in paragraphs]
    scraper = UniversalStoryScraper()
    return scraper.chunk_paragraphs_by_words(paragraphs, target_words=target_words, story_title=story_title)


def build_chapter_html(chapters: List[dict], intro: str = "") -> str:
    """
    HTML the site expects in chapter mode: optional intro paragraphs, then for
    each chapter a line starting with "CHAPTER N - Title" followed by its
    paragraphs.  Markers sit on their own line so both HTML and plain-text
    parsing find them.
    """
    parts = []
    for p in (intro or "").strip().splitlines():
        if p.strip():
            parts.append(f"<p>{html.escape(p.strip())}</p>")
    for ch in chapters:
        parts.append(f"<p><strong>{html.escape(ch['chapter_title'])}</strong></p>")
        for p in ch["paragraphs"]:
            parts.append(f"<p>{html.escape(p)}</p>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _headers() -> dict:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {SITE_TOKEN}",
        "Content-Type": "application/json",
    }


def _explain_error(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        body = {}
    err = str(body.get("error") or "")
    msg = str(body.get("message") or body.get("error") or resp.text[:300])
    if err == "blogbio_verify_failed" or "verify" in msg.lower():
        return (f"Web truyện từ chối token (HTTP {resp.status_code}, verify_status="
                f"{body.get('verify_status', '?')}). Dịch vụ xác minh của Blogbio đang lỗi hoặc token không hợp lệ.")
    if resp.status_code in (401, 403):
        return f"Token không được chấp nhận (HTTP {resp.status_code}): {msg}"
    if resp.status_code == 422:
        errors = body.get("errors") or {}
        detail = "; ".join(f"{k}: {', '.join(map(str, v))}" for k, v in errors.items()) if isinstance(errors, dict) else ""
        return f"Dữ liệu không hợp lệ (422): {msg} {detail}".strip()
    return f"Web truyện trả lỗi HTTP {resp.status_code}: {msg}"


def _request(method: str, path: str, **kwargs) -> dict:
    if not is_configured():
        raise PublishError("Chưa cấu hình STORY_SITE_URL / STORY_SITE_TOKEN trên server.")
    url = f"{SITE_URL}/api{path}"
    try:
        resp = requests.request(method, url, headers=_headers(), timeout=TIMEOUT_S, **kwargs)
    except requests.RequestException as exc:
        raise PublishError(f"Không kết nối được tới {site_name()}: {exc}")
    if not resp.ok:
        raise PublishError(_explain_error(resp))
    try:
        return resp.json()
    except ValueError:
        raise PublishError("Web truyện trả về dữ liệu không phải JSON.")


def list_series(search: str = "", page: int = 1) -> dict:
    """GET /api/series -> {"data": [...], pagination...}"""
    params = {"page": page}
    if search:
        params["search"] = search
    return _request("GET", "/series", params=params)


def check_connection() -> dict:
    """Cheap authenticated call used by the UI to verify the token works."""
    return _request("GET", "/categories", params={"page": 1})



# ---------------------------------------------------------------------------
# Admin session API (login with e-mail + password, like the admin UI)
# ---------------------------------------------------------------------------
_CSRF_INPUT_RE = re.compile(r'name="_token"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*name="_token"')
_CSRF_META_RE = re.compile(r'<meta[^>]+name="csrf-token"[^>]+content="([^"]+)"')


def _admin_login() -> tuple:
    """Returns (requests.Session, csrf_token) for an authenticated admin session."""
    sess = requests.Session()
    sess.headers["User-Agent"] = "story-scraper-publisher/1.0"
    try:
        page = sess.get(f"{SITE_URL}/login", timeout=TIMEOUT_S)
        m = _CSRF_INPUT_RE.search(page.text)
        if not m:
            raise PublishError("Không đọc được form đăng nhập của web truyện.")
        resp = sess.post(f"{SITE_URL}/login", timeout=TIMEOUT_S, allow_redirects=True, data={
            "_token": m.group(1) or m.group(2), "email": SITE_EMAIL, "password": SITE_PASSWORD, "remember": "on",
        })
        if resp.url.rstrip("/").endswith("/login"):
            raise PublishError("Đăng nhập web truyện thất bại: sai email hoặc mật khẩu (STORY_SITE_EMAIL / STORY_SITE_PASSWORD).")
        admin = sess.get(f"{SITE_URL}/admin/series", timeout=TIMEOUT_S)
        meta = _CSRF_META_RE.search(admin.text)
        if admin.url.rstrip("/").endswith("/login") or not meta:
            raise PublishError("Đăng nhập xong nhưng không vào được trang admin.")
    except requests.RequestException as exc:
        raise PublishError(f"Không kết nối được tới {site_name()}: {exc}")
    return sess, html.unescape(meta.group(1))


def _admin_request(sess, csrf: str, method: str, path: str, **kwargs) -> dict:
    headers = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest", "X-CSRF-TOKEN": csrf}
    try:
        resp = sess.request(method, f"{SITE_URL}/admin/api/v1{path}", headers=headers, timeout=TIMEOUT_S, **kwargs)
    except requests.RequestException as exc:
        raise PublishError(f"Không kết nối được tới {site_name()}: {exc}")
    if not resp.ok:
        raise PublishError(_explain_error(resp))
    try:
        body = resp.json()
    except ValueError:
        raise PublishError("Web truyện trả về dữ liệu không phải JSON (có thể phiên đăng nhập hết hạn).")
    if isinstance(body, dict) and body.get("ok") is False:
        raise PublishError(f"Web truyện báo lỗi: {body.get('message')}")
    return body


def _publish_via_session(title, chapters, intro, series_id, feature_image, category_id) -> dict:
    """Same payload the admin form sends to POST /admin/api/v1/posts/chapter-batch."""
    sess, csrf = _admin_login()
    intro_html = "".join(f"<p>{html.escape(l.strip())}</p>" for l in (intro or "").splitlines() if l.strip())
    payload = {
        "title": title, "slug": "", "image": feature_image or "", "description": intro_html,
        "seo_title": "", "seo_description": "", "seo_keywords": "",
        "selected_categories": [int(category_id)] if category_id else [],
        "selected_tags": [],
        "is_active": True, "is_home": True, "is_top": True,
        "series_id": int(series_id) if series_id else None,
        "prev_chapter": None, "next_chapter": None,
        "skip_intro": True,
        "chapters": [{
            "title": ch["chapter_title"], "slug": "",
            "description": "".join(f"<p>{html.escape(p)}</p>" for p in ch["paragraphs"]),
            "image": feature_image or "",
        } for ch in chapters],
    }
    return _admin_request(sess, csrf, "POST", "/posts/chapter-batch", json=payload)

# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------
def build_payload(title: str, text: str, intro: str = "", series_id: Optional[int] = None,
                  feature_image: str = "", category_id: Optional[int] = None,
                  target_words: int = CHAPTER_WORDS, chapters: Optional[List[dict]] = None) -> dict:
    title = (title or "").strip()
    if not title:
        raise PublishError("Tên truyện đang trống.")
    chapters = chapters or split_into_chapters(text, title, target_words)
    if not chapters:
        raise PublishError("Không tách được chương nào từ nội dung.")
    payload = {
        "title": title,
        "content": build_chapter_html(chapters, intro),
        "mode": "chapter",
        "apply_image_to_all": bool(feature_image),
    }
    if feature_image:
        payload["feature_image"] = feature_image
    if series_id:
        payload["series_id"] = int(series_id)
    cat = category_id or (int(SITE_CATEGORY_ID) if SITE_CATEGORY_ID.isdigit() else None)
    if cat:
        payload["category"] = int(cat)
    if SITE_AUTHOR:
        payload["author"] = SITE_AUTHOR
    payload["_chapters"] = chapters  # local preview only, stripped before sending
    return payload


def _extract_posts(data) -> List[dict]:
    """Normalises the create response into a list of {id, slug, link, title}."""
    if isinstance(data, dict):
        for key in ("data", "posts", "chapters", "items"):
            if isinstance(data.get(key), (list, dict)):
                return _extract_posts(data[key])
        return [data] if ("slug" in data or "id" in data) else []
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return []


def publish_story(title: str, text: str, intro: str = "", series_id: Optional[int] = None,
                  feature_image: str = "", category_id: Optional[int] = None,
                  status_callback=None, chapters: Optional[List[dict]] = None) -> dict:
    """
    Creates series + chapters in one request. Returns
    {"chapters": N, "posts": [{id, slug, link, title}], "raw": response}.
    """
    payload = build_payload(title, text, intro, series_id, feature_image, category_id, chapters=chapters)
    chapters = payload.pop("_chapters")
    _log(status_callback, f"📦 {len(chapters)} chương, {sum(len(' '.join(c['paragraphs']).split()) for c in chapters):,} từ.")
    _log(status_callback, f"📤 Đang gửi lên {site_name()}...")
    if use_session():
        _log(status_callback, "🔐 Đăng nhập admin...")
        data = _publish_via_session(title, chapters, intro, series_id, feature_image,
                                    payload.get("category"))
    else:
        data = _request("POST", "/posts", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    posts = _extract_posts(data)
    _log(status_callback, f"✅ Web đã tạo {len(posts)} bài.")
    return {
        "title": title,
        "chapters": len(chapters),
        "posts": [{"id": p.get("id"), "slug": p.get("slug"), "link": p.get("link") or p.get("url") or (f"{SITE_URL}/blog/{p['slug']}" if p.get("slug") else None),
                   "title": p.get("title")} for p in posts],
        "series_url": f"{SITE_URL}/admin/series",
        "raw": data,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python story_publisher.py <story.txt> [--dry-run] [--title 'Tên']")
        sys.exit(1)
    args = sys.argv[1:]
    dry = "--dry-run" in args
    title = args[args.index("--title") + 1] if "--title" in args else ""
    text = open(args[0], encoding="utf-8").read()
    title = title or guess_title(text)
    if dry:
        payload = build_payload(title, text)
        chs = payload.pop("_chapters")
        print(f"title: {title}\nchapters: {len(chs)}")
        for c in chs:
            print(f"  {c['chapter_title']}  ({len(' '.join(c['paragraphs']).split())} words)")
        print(f"content bytes: {len(payload['content'].encode('utf-8'))}")
    else:
        res = publish_story(title, text, status_callback=print)
        print(json.dumps(res["posts"], ensure_ascii=False, indent=2))
