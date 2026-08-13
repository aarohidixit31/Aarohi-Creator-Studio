from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .routers import media_kit, collabs, invoices, auth_routes, brands, content, social_stats, automation, calendar
from .config import cors_origins, is_production, validate_production_config

validate_production_config()
app = FastAPI(title="Creator Dashboard API")
UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_routes.router)
app.include_router(media_kit.router)
app.include_router(collabs.router)
app.include_router(invoices.router)
app.include_router(brands.router)
app.include_router(content.router)
app.include_router(social_stats.router)
app.include_router(automation.router)
app.include_router(calendar.router)
app.mount("/api/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "environment": "production" if is_production() else "development"}
