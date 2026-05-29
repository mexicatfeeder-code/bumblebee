import importlib
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .routers import health
from .services.config_loader import load_config

log = logging.getLogger(__name__)
app = FastAPI(title="Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:8765", "http://127.0.0.1:8765"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api")

# Auto-discover optional routers
for _rname in ["intake", "uploads", "tickets", "projects", "telemetry", "logs", "loops", "pixel_stats", "research", "research_executor", "ai_config", "qa_chat", "decompose", "executor", "costs", "reset"]:
    try:
        _rmod = importlib.import_module(f".routers.{_rname}", __package__)
        if hasattr(_rmod, "router"):
            app.include_router(_rmod.router, prefix="/api")
            log.info("Loaded router: %s", _rname)
    except ImportError:
        log.debug("Router not available: %s", _rname)


@app.on_event("startup")
async def startup():
    load_config()
    # Pre-warm caches in background so first panel load is fast
    import asyncio
    from .services.wmi_poller import get_hardware_telemetry, get_gpu_telemetry
    asyncio.get_event_loop().run_in_executor(None, get_hardware_telemetry)
    asyncio.get_event_loop().run_in_executor(None, get_gpu_telemetry)


# --- Launch App redirect: /app/{slug} -> project dev server ---
from fastapi.responses import RedirectResponse as _RedirectResponse

# Map slugs to dev server ports
_APP_PORTS = {"food-cart": 4177}

@app.get("/app/{slug}")
@app.get("/app/{slug}/{rest:path}")
async def launch_app(slug: str, rest: str = ""):
    port = _APP_PORTS.get(slug)
    if port:
        target = f"http://localhost:{port}/{rest}" if rest else f"http://localhost:{port}/"
        return _RedirectResponse(target)
    from fastapi.responses import JSONResponse
    return JSONResponse({"error": f"No app server for '{slug}'"}, status_code=404)


# --- Serve built frontend (production mode) ---
# Mount SvelteKit static assets first (/_app, /favicon, etc.)
_build = Path(__file__).resolve().parent.parent / "ui" / "build"
if _build.exists():
    # Mount static asset directories
    for _static_dir in ["_app", "assets"]:
        _d = _build / _static_dir
        if _d.exists():
            app.mount(f"/{_static_dir}", StaticFiles(directory=str(_d)), name=_static_dir)

    # Catch-all: serve index.html for any non-API path (SPA routing)
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Don't intercept API routes
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Not found"}, status_code=404)
        # Check if a real file exists (favicon.png, robots.txt, etc.)
        file = _build / full_path
        if file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_build / "index.html"))

    log.info("Serving built frontend from %s", _build)
else:
    log.info("No built frontend found at %s — running API-only (use Vite dev server)", _build)
