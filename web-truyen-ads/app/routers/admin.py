import os
import re
import time
import shutil
import unicodedata
from fastapi import APIRouter, Request, Form, Response, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from ..database import get_db, hash_password

router = APIRouter(prefix="/admin")
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def slugify(text: str) -> str:
    """Convert title to SEO friendly URL slug"""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)

def is_authenticated(request: Request) -> bool:
    session = request.cookies.get("admin_session")
    return session == "authenticated_admin"

def save_uploaded_cover(file: UploadFile) -> str | None:
    if not file or not file.filename:
        return None
    # Sanitize filename
    clean_name = re.sub(r'[^\w\.-]', '_', file.filename)
    filename = f"{int(time.time())}_{clean_name}"
    target_path = os.path.join(UPLOAD_DIR, filename)
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return f"/static/uploads/{filename}"

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    if is_authenticated(request):
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="admin/login.html", context={
        "request": request,
        "error": error
    })

@router.post("/login")
async def login_submit(username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM site_settings WHERE key IN ('admin_username', 'admin_password_hash')")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}
    conn.close()

    expected_user = settings.get("admin_username", "admin")
    expected_hash = settings.get("admin_password_hash", hash_password("admin123"))

    if username.strip() == expected_user and hash_password(password.strip()) == expected_hash:
        response = RedirectResponse(url="/admin/dashboard", status_code=303)
        response.set_cookie(key="admin_session", value="authenticated_admin", max_age=86400 * 7, httponly=True)
        return response
    else:
        return RedirectResponse(url="/admin/login?error=Invalid username or password. Default: admin / admin123", status_code=303)

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("admin_session")
    return response

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM stories")
    total_stories = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM story_parts")
    total_parts = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(views), 0) FROM stories")
    total_views = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(next_clicks), 0) FROM stories")
    total_next_clicks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM ads_config WHERE is_enabled = 1 AND LENGTH(TRIM(ad_code)) > 0")
    active_ads = cursor.fetchone()[0]

    # Stories with detailed traffic metrics
    cursor.execute("""
    SELECT s.*, c.name as category_name,
           (SELECT COUNT(*) FROM story_parts WHERE story_id = s.id) as part_count
    FROM stories s
    LEFT JOIN categories c ON s.category_id = c.id
    ORDER BY s.views DESC, s.id DESC
    LIMIT 10
    """)
    stories_raw = cursor.fetchall()
    stories = []
    for row in stories_raw:
        item = dict(row)
        views = item.get("views", 0) or 0
        clicks = item.get("next_clicks", 0) or 0
        item["retention_rate"] = f"{round((clicks / views) * 100, 1)}%" if views > 0 else "0%"
        stories.append(item)

    # Top traffic sources
    cursor.execute("""
    SELECT referrer, COUNT(*) as count
    FROM analytics_events
    WHERE event_type = 'view'
    GROUP BY referrer
    ORDER BY count DESC
    LIMIT 5
    """)
    top_referrers = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return templates.TemplateResponse(request=request, name="admin/dashboard.html", context={
        "request": request,
        "total_stories": total_stories,
        "total_parts": total_parts,
        "total_views": total_views,
        "total_next_clicks": total_next_clicks,
        "active_ads": active_ads,
        "stories": stories,
        "top_referrers": top_referrers
    })

# Stories List with Traffic & Clicks
@router.get("/stories", response_class=HTMLResponse)
async def stories_list(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, c.name as category_name,
           (SELECT COUNT(*) FROM story_parts WHERE story_id = s.id) as part_count
    FROM stories s
    LEFT JOIN categories c ON s.category_id = c.id
    ORDER BY s.id DESC
    """)
    raw_stories = cursor.fetchall()
    stories = []
    for r in raw_stories:
        item = dict(r)
        v = item.get("views", 0) or 0
        nc = item.get("next_clicks", 0) or 0
        item["retention_rate"] = f"{round((nc / v) * 100, 1)}%" if v > 0 else "0%"

        # Query top traffic source for this story
        cursor.execute("""
        SELECT referrer, COUNT(*) as ref_count
        FROM analytics_events
        WHERE story_id = ? AND event_type = 'view'
        GROUP BY referrer
        ORDER BY ref_count DESC
        LIMIT 1
        """, (item["id"],))
        top_ref = cursor.fetchone()
        item["top_referrer"] = top_ref["referrer"] if top_ref else "Direct"

        stories.append(item)

    conn.close()

    return templates.TemplateResponse(request=request, name="admin/stories.html", context={
        "request": request,
        "stories": stories
    })

# Story Traffic Details
@router.get("/stories/{story_id}/traffic", response_class=HTMLResponse)
async def story_traffic_details(request: Request, story_id: int):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stories WHERE id = ?", (story_id,))
    story = cursor.fetchone()
    if not story:
        conn.close()
        raise HTTPException(status_code=404, detail="Story not found")

    story = dict(story)

    # Traffic by Referrer
    cursor.execute("""
    SELECT referrer, COUNT(*) as count
    FROM analytics_events
    WHERE story_id = ? AND event_type = 'view'
    GROUP BY referrer
    ORDER BY count DESC
    """, (story_id,))
    sources = [dict(r) for r in cursor.fetchall()]

    # Views per Part
    cursor.execute("""
    SELECT part_number, views, title
    FROM story_parts
    WHERE story_id = ?
    ORDER BY part_number ASC
    """, (story_id,))
    parts_stats = [dict(r) for r in cursor.fetchall()]

    # Recent Event Logs
    cursor.execute("""
    SELECT event_type, part_number, referrer, created_at
    FROM analytics_events
    WHERE story_id = ?
    ORDER BY id DESC
    LIMIT 25
    """, (story_id,))
    recent_logs = [dict(r) for r in cursor.fetchall()]

    conn.close()

    views = story.get("views", 0) or 0
    next_clicks = story.get("next_clicks", 0) or 0
    story["retention_rate"] = f"{round((next_clicks / views) * 100, 1)}%" if views > 0 else "0%"

    return templates.TemplateResponse(request=request, name="admin/story_traffic.html", context={
        "request": request,
        "story": story,
        "sources": sources,
        "parts_stats": parts_stats,
        "recent_logs": recent_logs
    })

# New Story Page
@router.get("/stories/new", response_class=HTMLResponse)
async def story_new_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM categories ORDER BY sort_order ASC")
    categories = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return templates.TemplateResponse(request=request, name="admin/story_form.html", context={
        "request": request,
        "story": None,
        "categories": categories,
        "is_new": True
    })

@router.post("/stories/new")
async def story_create(
    title: str = Form(...),
    slug: str = Form(None),
    category_id: int = Form(...),
    excerpt: str = Form(""),
    cover_image: str = Form(""),
    cover_file: UploadFile = File(None),
    is_featured: int = Form(0),
    reading_time: int = Form(5),
    part_1_title: str = Form("Part 1: The Beginning"),
    part_1_content: str = Form(...)
):
    if not slug or not slug.strip():
        slug = slugify(title)

    # Check for uploaded cover file
    if cover_file and cover_file.filename:
        saved_path = save_uploaded_cover(cover_file)
        if saved_path:
            cover_image = saved_path

    conn = get_db()
    cursor = conn.cursor()

    # Ensure slug unique
    cursor.execute("SELECT id FROM stories WHERE slug = ?", (slug,))
    if cursor.fetchone():
        slug = f"{slug}-{int(os.urandom(2).hex(), 16)}"

    cursor.execute("""
    INSERT INTO stories (title, slug, excerpt, cover_image, category_id, is_featured, reading_time)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, slug, excerpt, cover_image, category_id, is_featured, reading_time))
    story_id = cursor.lastrowid

    # Insert Part 1
    cursor.execute("""
    INSERT INTO story_parts (story_id, part_number, title, content)
    VALUES (?, 1, ?, ?)
    """, (story_id, part_1_title, part_1_content))

    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/admin/stories/{story_id}/parts", status_code=303)

# Edit Story
@router.get("/stories/{story_id}/edit", response_class=HTMLResponse)
async def story_edit_page(request: Request, story_id: int):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stories WHERE id = ?", (story_id,))
    story = cursor.fetchone()
    cursor.execute("SELECT id, name FROM categories ORDER BY sort_order ASC")
    categories = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    return templates.TemplateResponse(request=request, name="admin/story_form.html", context={
        "request": request,
        "story": dict(story),
        "categories": categories,
        "is_new": False
    })

@router.post("/stories/{story_id}/edit")
async def story_update(
    story_id: int,
    title: str = Form(...),
    slug: str = Form(...),
    category_id: int = Form(...),
    excerpt: str = Form(""),
    cover_image: str = Form(""),
    cover_file: UploadFile = File(None),
    is_featured: int = Form(0),
    reading_time: int = Form(5)
):
    # Check for uploaded cover file
    if cover_file and cover_file.filename:
        saved_path = save_uploaded_cover(cover_file)
        if saved_path:
            cover_image = saved_path

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE stories
    SET title = ?, slug = ?, category_id = ?, excerpt = ?, cover_image = ?, is_featured = ?, reading_time = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (title, slug, category_id, excerpt, cover_image, is_featured, reading_time, story_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/stories", status_code=303)

@router.post("/stories/{story_id}/delete")
async def story_delete(story_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM analytics_events WHERE story_id = ?", (story_id,))
    cursor.execute("DELETE FROM story_parts WHERE story_id = ?", (story_id,))
    cursor.execute("DELETE FROM stories WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/stories", status_code=303)

# Story Parts Management
@router.get("/stories/{story_id}/parts", response_class=HTMLResponse)
async def story_parts_page(request: Request, story_id: int):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stories WHERE id = ?", (story_id,))
    story = cursor.fetchone()
    if not story:
        conn.close()
        raise HTTPException(status_code=404, detail="Story not found")

    cursor.execute("SELECT * FROM story_parts WHERE story_id = ? ORDER BY part_number ASC", (story_id,))
    parts = [dict(r) for r in cursor.fetchall()]
    conn.close()

    next_part_num = (max([p["part_number"] for p in parts]) + 1) if parts else 1

    return templates.TemplateResponse(request=request, name="admin/story_parts.html", context={
        "request": request,
        "story": dict(story),
        "parts": parts,
        "next_part_num": next_part_num
    })

@router.post("/stories/{story_id}/parts/new")
async def part_add(
    story_id: int,
    part_number: int = Form(...),
    title: str = Form(...),
    content: str = Form(...)
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO story_parts (story_id, part_number, title, content)
    VALUES (?, ?, ?, ?)
    """, (story_id, part_number, title, content))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/stories/{story_id}/parts", status_code=303)

@router.get("/parts/{part_id}/edit", response_class=HTMLResponse)
async def part_edit_page(request: Request, part_id: int):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM story_parts WHERE id = ?", (part_id,))
    part = cursor.fetchone()
    if not part:
        conn.close()
        raise HTTPException(status_code=404, detail="Story part not found")

    cursor.execute("SELECT * FROM stories WHERE id = ?", (part["story_id"],))
    story = cursor.fetchone()
    conn.close()

    return templates.TemplateResponse(request=request, name="admin/part_edit.html", context={
        "request": request,
        "part": dict(part),
        "story": dict(story)
    })

@router.post("/parts/{part_id}/edit")
async def part_update(
    part_id: int,
    part_number: int = Form(...),
    title: str = Form(...),
    content: str = Form(...)
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT story_id FROM story_parts WHERE id = ?", (part_id,))
    part = cursor.fetchone()
    story_id = part["story_id"]

    cursor.execute("""
    UPDATE story_parts
    SET part_number = ?, title = ?, content = ?
    WHERE id = ?
    """, (part_number, title, content, part_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/stories/{story_id}/parts", status_code=303)

@router.post("/parts/{part_id}/delete")
async def part_delete(part_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT story_id FROM story_parts WHERE id = ?", (part_id,))
    part = cursor.fetchone()
    story_id = part["story_id"]

    cursor.execute("DELETE FROM story_parts WHERE id = ?", (part_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/stories/{story_id}/parts", status_code=303)

# Ads Settings Center
@router.get("/ads", response_class=HTMLResponse)
async def ads_center_page(request: Request, saved: bool = False):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ads_config")
    ads = {row["slot_key"]: dict(row) for row in cursor.fetchall()}

    cursor.execute("SELECT key, value FROM site_settings WHERE key IN ('ads_txt', 'paragraph_ad_interval', 'show_ad_placeholders', 'head_scripts', 'body_scripts')")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}
    conn.close()

    return templates.TemplateResponse(request=request, name="admin/ads_center.html", context={
        "request": request,
        "ads": ads,
        "settings": settings,
        "saved": saved
    })

@router.post("/ads")
async def ads_center_save(request: Request):
    form = await request.form()
    conn = get_db()
    cursor = conn.cursor()

    slot_keys = ["header_ad", "in_content_ad", "before_next_button", "after_next_button", "sticky_footer_ad", "sidebar_ad"]
    for key in slot_keys:
        is_enabled = 1 if f"{key}_enabled" in form else 0
        ad_code = form.get(f"{key}_code", "")
        cursor.execute("UPDATE ads_config SET is_enabled = ?, ad_code = ? WHERE slot_key = ?", (is_enabled, ad_code, key))

    ads_txt = form.get("ads_txt", "")
    paragraph_interval = form.get("paragraph_ad_interval", "3")
    show_placeholders = "1" if "show_ad_placeholders" in form else "0"
    head_scripts = form.get("head_scripts", "")
    body_scripts = form.get("body_scripts", "")

    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'ads_txt'", (ads_txt,))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'paragraph_ad_interval'", (paragraph_interval,))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'show_ad_placeholders'", (show_placeholders,))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'head_scripts'", (head_scripts,))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'body_scripts'", (body_scripts,))

    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin/ads?saved=1", status_code=303)

# Site Settings Page
@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, saved: bool = False, error: str = None):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM site_settings")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}
    conn.close()

    return templates.TemplateResponse(request=request, name="admin/settings.html", context={
        "request": request,
        "settings": settings,
        "saved": saved,
        "error": error
    })

@router.post("/settings")
async def settings_save(
    site_name: str = Form(...),
    tagline: str = Form(""),
    meta_description: str = Form(""),
    contact_email: str = Form(""),
    admin_username: str = Form("admin"),
    current_password: str = Form(""),
    new_password: str = Form("")
):
    conn = get_db()
    cursor = conn.cursor()

    if new_password:
        cursor.execute("SELECT value FROM site_settings WHERE key = 'admin_password_hash'")
        stored = cursor.fetchone()["value"]
        if hash_password(current_password.strip()) != stored:
            conn.close()
            return RedirectResponse(url="/admin/settings?error=Current password is incorrect", status_code=303)
        cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'admin_password_hash'", (hash_password(new_password.strip()),))

    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'admin_username'", (admin_username.strip(),))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'site_name'", (site_name,))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'tagline'", (tagline,))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'meta_description'", (meta_description,))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'contact_email'", (contact_email,))

    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin/settings?saved=1", status_code=303)
