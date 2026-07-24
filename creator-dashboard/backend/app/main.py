from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from . import models
from .database import engine
from .schema_migrations import ensure_compatibility_columns
from .routers import media_kit, collabs, invoices, auth_routes, brands

models.Base.metadata.create_all(bind=engine)
ensure_compatibility_columns()

app = FastAPI(title="Creator Dashboard API")
UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# In production, replace "*" with your actual frontend domain (e.g. https://aarohi.vercel.app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(media_kit.router)
app.include_router(collabs.router)
app.include_router(invoices.router)
app.include_router(brands.router)
app.mount("/api/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
