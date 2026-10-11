import os
import re
import unicodedata
from fastapi import APIRouter, Request, Form, Response, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from ..database import get_db, hash_password

router = APIRouter(prefix="/admin")
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def slugify(text: str) -> str:
    """Convert Vietnamese and special characters to URL-friendly slug"""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)

def is_authenticated(request: Request) -> bool:
    session = request.cookies.get("admin_session")
    return session == "authenticated_admin"

def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"}
        )

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    if is_authenticated(request):
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="admin/login.html", context={
        "request": request,
        "error": error
    })

@router.post("/login")
async def login_submit(password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM site_settings WHERE key = 'admin_password_hash'")
    stored_hash = cursor.fetchone()
    conn.close()

    if stored_hash and hash_password(password) == stored_hash["value"]:
        response = RedirectResponse(url="/admin/dashboard", status_code=303)
        response.set_cookie(key="admin_session", value="authenticated_admin", max_age=86400 * 7, httponly=True)
        return response
    else:
        return RedirectResponse(url="/admin/login?error=Mật khẩu không chính xác (Mặc định: admin123)", status_code=303)

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

    cursor.execute("SELECT COUNT(*) FROM ads_config WHERE is_enabled = 1 AND LENGTH(TRIM(ad_code)) > 0")
    active_ads = cursor.fetchone()[0]

    # Recent stories
    cursor.execute("""
    SELECT s.*, c.name as category_name,
           (SELECT COUNT(*) FROM story_parts WHERE story_id = s.id) as part_count
    FROM stories s
    LEFT JOIN categories c ON s.category_id = c.id
    ORDER BY s.id DESC
    LIMIT 10
    """)
    recent_stories = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return templates.TemplateResponse(request=request, name="admin/dashboard.html", context={
        "request": request,
        "total_stories": total_stories,
        "total_parts": total_parts,
        "total_views": total_views,
        "active_ads": active_ads,
        "stories": recent_stories
    })

# Stories List
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
    stories = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return templates.TemplateResponse(request=request, name="admin/stories.html", context={
        "request": request,
        "stories": stories
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
    is_featured: int = Form(0),
    reading_time: int = Form(5),
    part_1_title: str = Form("Phần 1"),
    part_1_content: str = Form(...)
):
    if not slug or not slug.strip():
        slug = slugify(title)

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
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện")

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
    is_featured: int = Form(0),
    reading_time: int = Form(5)
):
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
    cursor.execute("DELETE FROM story_parts WHERE story_id = ?", (story_id,))
    cursor.execute("DELETE FROM stories WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/stories", status_code=303)

# Story Parts Management (Chapters)
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
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện")

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
        raise HTTPException(status_code=404, detail="Không tìm thấy phần truyện")

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

    # General ad settings
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
    current_password: str = Form(""),
    new_password: str = Form("")
):
    conn = get_db()
    cursor = conn.cursor()

    # If updating password
    if new_password:
        cursor.execute("SELECT value FROM site_settings WHERE key = 'admin_password_hash'")
        stored = cursor.fetchone()["value"]
        if hash_password(current_password) != stored:
            conn.close()
            return RedirectResponse(url="/admin/settings?error=Mật khẩu hiện tại không đúng", status_code=303)
        cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'admin_password_hash'", (hash_password(new_password),))

    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'site_name'", (site_name,))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'tagline'", (tagline,))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'meta_description'", (meta_description,))
    cursor.execute("UPDATE site_settings SET value = ? WHERE key = 'contact_email'", (contact_email,))

    conn.commit()
    conn.close()

    return RedirectResponse(url="/admin/settings?saved=1", status_code=303)
