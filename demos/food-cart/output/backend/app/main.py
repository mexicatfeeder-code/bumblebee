"""
FastAPI application entry point for the Food Cart backend.

Configures the FastAPI app with SQLite database connection,
dependency injection for database sessions, CORS middleware
for local network access, and serves the built React frontend
from the root route with static files.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import categories, menu_items, orders, settings
from db.models import Base

# SQLite database configuration
DATABASE_URL = "sqlite:///./foodcart.db"

# Create SQLAlchemy engine with check_same_thread=False for SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for database sessions.

    Yields a database session and ensures proper cleanup
    (session close) after the request is complete.

    Yields:
        Session: An active SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Creates database tables on startup and performs cleanup on shutdown.

    Args:
        app: The FastAPI application instance.
    """
    # Startup: Create all tables
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: Cleanup (optional - close engine connections)
    engine.dispose()


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.

    Returns:
        FastAPI: The configured FastAPI application instance.
    """
    app = FastAPI(
        title="Food Cart API",
        description="Backend API for the Food Cart ordering application",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware for local network access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─── Include API Routers ──────────────────────────────────────────────

    # Categories router
    app.include_router(categories.router)

    # Menu Items router
    app.include_router(menu_items.router)

    # Orders router
    app.include_router(orders.router)

    # Settings router
    app.include_router(settings.router)

    # ─── Static Files & Frontend Serving ──────────────────────────────────

    # Determine paths relative to this file's location
    backend_dir = Path(__file__).resolve().parent.parent
    frontend_build_dir = backend_dir.parent / "frontend" / "build"
    uploads_dir = backend_dir / "uploads"

    # Serve uploaded files (menu photos, etc.)
    if uploads_dir.exists():
        app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    # Serve built React frontend static assets
    if frontend_build_dir.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(frontend_build_dir / "static")),
            name="static",
        )

    @app.get("/", response_class=FileResponse)
    async def serve_frontend(request: Request):
        """
        Serve the React frontend index.html for the root route.

        Args:
            request: The incoming HTTP request.

        Returns:
            FileResponse: The index.html file from the React build.
        """
        index_path = frontend_build_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return FileResponse(
            str(index_path),
            status_code=404,
            media_type="text/html",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    @app.get("/{full_path:path}", response_class=FileResponse)
    async def serve_frontend_fallback(request: Request, full_path: str):
        """
        Catch-all route to serve the React frontend for client-side routing.

        Returns index.html for any path that doesn't match an API route,
        enabling React Router's client-side navigation.

        Args:
            request: The incoming HTTP request.
            full_path: The full path requested.

        Returns:
            FileResponse: The index.html file from the React build.
        """
        # Skip API routes and static file routes
        if full_path.startswith("api/") or full_path.startswith("docs") or \
           full_path.startswith("redoc") or full_path.startswith("openapi.json") or \
           full_path.startswith("uploads") or full_path.startswith("static"):
            return FileResponse(
                str(frontend_build_dir / "index.html"),
                status_code=404,
            )

        index_path = frontend_build_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return FileResponse(
            str(index_path),
            status_code=404,
            media_type="text/html",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    return app


# Create the application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
