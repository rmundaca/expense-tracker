from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    accounts_router, auth_router, banks_router, budgets_router, categories_router, exchange_rates_router,
    mail_router, recurring_router, rules_router, stats_router, system_router, transactions_router, users_router,
)
from app import i18n
from app.core import auth
from app.core.app_setup import init_app_database
from app.core.config import APP_NAME, VERSION
from app.core.logs import setup_logging
from app.schedulers.tasks import start_scheduler, stop_scheduler

setup_logging()
# Users' databases are created, migrated and seeded when first opened (core/database.py)
init_app_database()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=APP_NAME, version=VERSION, lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Everything except the login flow and public assets requires a session.
# The SPA is served from this same origin, so no CORS middleware is needed.
PUBLIC_PATHS = {"/", "/api/health", "/manifest.json", "/favicon.ico",
                "/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"}
PUBLIC_PREFIXES = ("/api/auth/",)  # /static/ is public too (handled first in require_session)


@app.middleware("http")
async def require_session(request: Request, call_next):
    # Language of every message this request returns (the routes run in a copy of this context)
    i18n.set_current(i18n.resolve(request.cookies.get(i18n.LANGUAGE_COOKIE), request.headers.get("accept-language")))
    path = request.url.path
    if path.startswith("/static/"):
        # Revalidate on every load (cheap 304 via ETag) so an upgrade never runs a cached, older app.js
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache"
        return response
    if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
        return await call_next(request)
    user = auth.get_session_user(request.cookies.get(auth.SESSION_COOKIE))
    if user:
        request.state.user = user  # routes use it to open this user's database (core/database.get_db)
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": i18n.t("common.not_authenticated")}, status_code=401)
    return RedirectResponse("/")


for router in (auth_router, accounts_router, categories_router, transactions_router, recurring_router, budgets_router,
               rules_router, banks_router, mail_router, stats_router, system_router, exchange_rates_router, users_router):
    app.include_router(router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": VERSION}


@app.get("/apple-touch-icon.png")
@app.get("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    return FileResponse(STATIC_DIR / "img" / "apple-touch-icon.png", media_type="image/png")


@app.get("/manifest.json")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(STATIC_DIR / "img" / "icon.png", media_type="image/png")


@app.get("/")
def serve_spa(request: Request):
    authenticated = auth.get_session_user(request.cookies.get(auth.SESSION_COOKIE)) is not None
    page = "index.html" if authenticated else "login.html"
    return FileResponse(STATIC_DIR / page, headers={"Cache-Control": "no-store"})
