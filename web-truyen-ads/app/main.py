import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from .database import init_db
from .routers import public, admin

app = FastAPI(title="Website Đọc Truyện Kiếm Tiền Ads")

# Static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include routers
app.include_router(public.router)
app.include_router(admin.router)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.on_event("startup")
def on_startup():
    init_db()

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    from .routers.public import get_site_settings, get_ads_config, get_categories
    return templates.TemplateResponse(
        request=request,
        name="404.html",
        context={
            "settings": get_site_settings(),
            "ads": get_ads_config(),
            "categories": get_categories()
        },
        status_code=404
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
