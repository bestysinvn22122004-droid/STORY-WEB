import html
import re
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
import os
from ..database import get_db

router = APIRouter()
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def get_site_settings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM site_settings")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def get_ads_config():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT slot_key, name, is_enabled, ad_code, extra_settings FROM ads_config")
    rows = cursor.fetchall()
    conn.close()
    return {row["slot_key"]: dict(row) for row in rows}

def get_categories():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, slug, description, sort_order FROM categories ORDER BY sort_order ASC, name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def inject_in_content_ads(content: str, in_content_ad: dict, interval: int = 3, show_placeholders: bool = True) -> str:
    """Inject ad blocks every N paragraphs into story text"""
    # Split content by double newlines or single newlines into paragraphs
    raw_paragraphs = [p.strip() for p in re.split(r'\n+', content) if p.strip()]
    if not raw_paragraphs:
        return ""

    ad_code = in_content_ad.get("ad_code", "").strip() if in_content_ad else ""
    is_enabled = bool(in_content_ad.get("is_enabled", 1)) if in_content_ad else False

    if not is_enabled:
        return "".join(f"<p class='mb-5 leading-relaxed text-lg'>{html.escape(p)}</p>" for p in raw_paragraphs)

    # Determine ad markup
    if ad_code:
        ad_html = f"""
        <div class="my-8 p-3 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-dashed border-gray-300 dark:border-gray-700 text-center flex flex-col items-center justify-center min-h-[120px]">
            <span class="text-[10px] uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-2 font-mono">Advertisement</span>
            <div class="w-full flex justify-center overflow-hidden">{ad_code}</div>
        </div>
        """
    elif show_placeholders:
        ad_html = """
        <div class="my-8 p-4 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-gray-800 dark:to-gray-800/80 rounded-xl border border-dashed border-amber-300 dark:border-amber-700/50 text-center flex flex-col items-center justify-center min-h-[130px] transition-all">
            <span class="text-[10px] uppercase tracking-wider text-amber-700/70 dark:text-amber-400 font-semibold mb-1">In-Content Sponsored Ad Slot</span>
            <p class="text-xs text-gray-600 dark:text-gray-300 max-w-md">Auto-injected between paragraphs (Google AdSense, Adsterra, Responsive Banner).</p>
            <span class="mt-2 text-[11px] text-amber-600 dark:text-amber-400 bg-white dark:bg-gray-700 px-2 py-0.5 rounded border border-amber-200 dark:border-gray-600">Prime CTR location while readers enjoy the story</span>
        </div>
        """
    else:
        ad_html = ""

    result = []
    p_count = 0
    for p in raw_paragraphs:
        result.append(f"<p class='story-paragraph mb-5 leading-relaxed text-lg'>{html.escape(p)}</p>")
        p_count += 1
        if ad_html and p_count % interval == 0 and p_count < len(raw_paragraphs):
            result.append(ad_html)

    return "".join(result)

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    conn = get_db()
    cursor = conn.cursor()

    # Featured stories
    cursor.execute("""
    SELECT s.*, c.name as category_name, c.slug as category_slug,
           (SELECT COUNT(*) FROM story_parts WHERE story_id = s.id) as part_count
    FROM stories s
    LEFT JOIN categories c ON s.category_id = c.id
    WHERE s.is_featured = 1
    ORDER BY s.id DESC
    LIMIT 5
    """)
    featured_stories = [dict(r) for r in cursor.fetchall()]

    # Latest stories
    cursor.execute("""
    SELECT s.*, c.name as category_name, c.slug as category_slug,
           (SELECT COUNT(*) FROM story_parts WHERE story_id = s.id) as part_count
    FROM stories s
    LEFT JOIN categories c ON s.category_id = c.id
    ORDER BY s.id DESC
    LIMIT 12
    """)
    latest_stories = [dict(r) for r in cursor.fetchall()]

    conn.close()

    settings = get_site_settings()
    ads = get_ads_config()
    categories = get_categories()

    return templates.TemplateResponse(request=request, name="index.html", context={
        "request": request,
        "settings": settings,
        "ads": ads,
        "categories": categories,
        "featured_stories": featured_stories,
        "latest_stories": latest_stories,
        "active_category": None,
        "page_title": settings.get("site_name", "Truyện Hay 24h") + " - " + settings.get("tagline", "")
    })

@router.get("/category/{slug}", response_class=HTMLResponse)
async def category_view(request: Request, slug: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM categories WHERE slug = ?", (slug,))
    category = cursor.fetchone()
    if not category:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy chuyên mục")

    cursor.execute("""
    SELECT s.*, c.name as category_name, c.slug as category_slug,
           (SELECT COUNT(*) FROM story_parts WHERE story_id = s.id) as part_count
    FROM stories s
    LEFT JOIN categories c ON s.category_id = c.id
    WHERE s.category_id = ?
    ORDER BY s.id DESC
    """, (category["id"],))
    stories = [dict(r) for r in cursor.fetchall()]
    conn.close()

    settings = get_site_settings()
    ads = get_ads_config()
    categories = get_categories()

    return templates.TemplateResponse(request=request, name="category.html", context={
        "request": request,
        "settings": settings,
        "ads": ads,
        "categories": categories,
        "category": dict(category),
        "stories": stories,
        "active_category": slug,
        "page_title": f"{category['name']} - {settings.get('site_name', 'Truyện Hay 24h')}"
    })

@router.get("/story/{slug}", response_class=HTMLResponse)
async def story_redirect(request: Request, slug: str):
    # Redirect or show Part 1 directly
    return await story_part_view(request, slug, part_number=1)

@router.get("/story/{slug}/part-{part_number}", response_class=HTMLResponse)
async def story_part_view(request: Request, slug: str, part_number: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT s.*, c.name as category_name, c.slug as category_slug
    FROM stories s
    LEFT JOIN categories c ON s.category_id = c.id
    WHERE s.slug = ?
    """, (slug,))
    story = cursor.fetchone()
    if not story:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện")

    story = dict(story)

    # Get all parts of this story
    cursor.execute("""
    SELECT id, part_number, title, created_at, views
    FROM story_parts
    WHERE story_id = ?
    ORDER BY part_number ASC
    """, (story["id"],))
    all_parts = [dict(r) for r in cursor.fetchall()]

    if not all_parts:
        conn.close()
        raise HTTPException(status_code=404, detail="Truyện chưa có nội dung phần đọc")

    # Find current part
    current_part = None
    for p in all_parts:
        if p["part_number"] == part_number:
            cursor.execute("SELECT * FROM story_parts WHERE id = ?", (p["id"],))
            current_part = dict(cursor.fetchone())
            break

    if not current_part:
        # Default to first part if requested part does not exist
        part_number = all_parts[0]["part_number"]
        cursor.execute("SELECT * FROM story_parts WHERE id = ?", (all_parts[0]["id"],))
        current_part = dict(cursor.fetchone())

    # Detect referrer source (Facebook, Google, TikTok, Twitter, Direct)
    referer_header = request.headers.get("referer", "").lower()
    user_agent = (request.headers.get("user-agent") or "")[:150]

    source = "Direct"
    if "facebook.com" in referer_header or "fb.me" in referer_header or "l.facebook" in referer_header:
        source = "Facebook"
    elif "t.co" in referer_header or "twitter.com" in referer_header or "x.com" in referer_header:
        source = "Twitter / X"
    elif "google." in referer_header:
        source = "Google"
    elif "pinterest" in referer_header:
        source = "Pinterest"
    elif "tiktok" in referer_header:
        source = "TikTok"
    elif referer_header and str(request.base_url.netloc) not in referer_header:
        source = "External Web"

    # Increment views
    cursor.execute("UPDATE stories SET views = views + 1 WHERE id = ?", (story["id"],))
    cursor.execute("UPDATE story_parts SET views = views + 1 WHERE id = ?", (current_part["id"],))

    # Log view event
    cursor.execute("""
    INSERT INTO analytics_events (story_id, part_number, event_type, referrer, user_agent)
    VALUES (?, ?, 'view', ?, ?)
    """, (story["id"], current_part["part_number"], source, user_agent))

    # Log Next Part button click if navigated via CTA button
    if request.query_params.get("click") == "1" or request.query_params.get("from_part"):
        cursor.execute("UPDATE stories SET next_clicks = COALESCE(next_clicks, 0) + 1 WHERE id = ?", (story["id"],))
        cursor.execute("""
        INSERT INTO analytics_events (story_id, part_number, event_type, referrer, user_agent)
        VALUES (?, ?, 'next_part_click', ?, ?)
        """, (story["id"], current_part["part_number"], source, user_agent))

    conn.commit()

    # Related stories
    cursor.execute("""
    SELECT s.*, c.name as category_name, c.slug as category_slug,
           (SELECT COUNT(*) FROM story_parts WHERE story_id = s.id) as part_count
    FROM stories s
    LEFT JOIN categories c ON s.category_id = c.id
    WHERE s.id != ? AND (s.category_id = ? OR s.category_id IS NULL)
    ORDER BY s.views DESC, s.id DESC
    LIMIT 6
    """, (story["id"], story["category_id"]))
    related_stories = [dict(r) for r in cursor.fetchall()]
    conn.close()

    settings = get_site_settings()
    ads = get_ads_config()
    categories = get_categories()

    # Determine next and previous parts
    next_part = next((p for p in all_parts if p["part_number"] == part_number + 1), None)
    prev_part = next((p for p in all_parts if p["part_number"] == part_number - 1), None)

    # Process story text with auto ad injection
    interval = int(settings.get("paragraph_ad_interval", 3) or 3)
    show_placeholders = settings.get("show_ad_placeholders", "1") == "1"
    processed_content = inject_in_content_ads(
        current_part["content"],
        ads.get("in_content_ad"),
        interval=interval,
        show_placeholders=show_placeholders
    )

    canonical_url = f"{request.base_url}story/{story['slug']}/part-{part_number}"
    og_image = story.get("cover_image") or "https://images.unsplash.com/photo-1519791883288-dc8bd696e667?auto=format&fit=crop&w=1200&q=80"

    return templates.TemplateResponse(request=request, name="story.html", context={
        "request": request,
        "settings": settings,
        "ads": ads,
        "categories": categories,
        "story": story,
        "current_part": current_part,
        "all_parts": all_parts,
        "next_part": next_part,
        "prev_part": prev_part,
        "processed_content": processed_content,
        "related_stories": related_stories,
        "canonical_url": canonical_url,
        "og_image": og_image,
        "active_category": story.get("category_slug"),
        "page_title": f"{current_part['title']} - {story['title']}"
    })

@router.get("/search", response_class=HTMLResponse)
async def search_view(request: Request, q: str = ""):
    q = q.strip()
    stories = []
    if q:
        conn = get_db()
        cursor = conn.cursor()
        search_term = f"%{q}%"
        cursor.execute("""
        SELECT DISTINCT s.*, c.name as category_name, c.slug as category_slug,
               (SELECT COUNT(*) FROM story_parts WHERE story_id = s.id) as part_count
        FROM stories s
        LEFT JOIN categories c ON s.category_id = c.id
        LEFT JOIN story_parts sp ON s.id = sp.story_id
        WHERE s.title LIKE ? OR s.excerpt LIKE ? OR sp.content LIKE ?
        ORDER BY s.id DESC
        LIMIT 20
        """, (search_term, search_term, search_term))
        stories = [dict(r) for r in cursor.fetchall()]
        conn.close()

    settings = get_site_settings()
    ads = get_ads_config()
    categories = get_categories()

    return templates.TemplateResponse(request=request, name="search.html", context={
        "request": request,
        "settings": settings,
        "ads": ads,
        "categories": categories,
        "query": q,
        "stories": stories,
        "active_category": None,
        "page_title": f"Tìm kiếm: {q} - {settings.get('site_name', 'Truyện Hay 24h')}"
    })

@router.get("/ads.txt", response_class=Response)
async def ads_txt():
    settings = get_site_settings()
    content = settings.get("ads_txt", "google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0")
    return Response(content=content, media_type="text/plain; charset=utf-8")

@router.get("/robots.txt", response_class=Response)
async def robots_txt(request: Request):
    content = f"""User-agent: *
Allow: /
Disallow: /admin/

Sitemap: {request.base_url}sitemap.xml
"""
    return Response(content=content, media_type="text/plain; charset=utf-8")

@router.get("/sitemap.xml", response_class=Response)
async def sitemap_xml(request: Request):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT slug, updated_at FROM stories ORDER BY id DESC")
    stories = cursor.fetchall()
    cursor.execute("SELECT slug FROM categories")
    categories = cursor.fetchall()
    conn.close()

    base = str(request.base_url).rstrip("/")
    xml_items = [
        f"<url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>"
    ]

    for cat in categories:
        xml_items.append(f"<url><loc>{base}/category/{cat['slug']}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>")

    for st in stories:
        xml_items.append(f"<url><loc>{base}/story/{st['slug']}</loc><changefreq>daily</changefreq><priority>0.9</priority></url>")

    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{''.join(xml_items)}
</urlset>"""
    return Response(content=xml_content, media_type="application/xml")
