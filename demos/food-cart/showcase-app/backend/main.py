from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from routers import menu, orders, admin, settings

app = FastAPI(title="Food Cart API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for uploaded photos
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Routers
app.include_router(menu.router)
app.include_router(orders.router)   # no prefix — mixes /api/orders + /ws/* routes
app.include_router(admin.router)    # no prefix — already has /api/admin/* paths
app.include_router(settings.router) # no prefix — /api/settings

# --- Serve built frontend ---
_frontend = Path(__file__).resolve().parent.parent / "frontend"
if _frontend.exists():
    # Mount static assets
    _assets = _frontend / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="frontend-assets")

    # Catch-all: serve index.html for SPA routing
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws"):
            return  # Let API/WS routes handle these
        file = _frontend / full_path
        if file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_frontend / "index.html"))
