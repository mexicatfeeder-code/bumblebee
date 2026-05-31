"""
App Launcher — start/stop the built demo app (backend + frontend).

POST /api/projects/{slug}/app/start  — start backend + frontend
POST /api/projects/{slug}/app/stop   — kill both
GET  /api/projects/{slug}/app/status — check if running
"""
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..services.config_loader import get_config
from ..services.registry import get_project

log = logging.getLogger(__name__)
router = APIRouter(tags=["app"])

_BUMBLEBEE_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Track running processes
_running: dict[str, dict] = {}


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _find_project_dir(slug: str) -> Path:
    """Find the project output directory."""
    for base in [_BUMBLEBEE_ROOT / "demos" / slug, _BUMBLEBEE_ROOT / "projects" / slug]:
        output = base / "output"
        if output.exists():
            return output
    raise HTTPException(404, f"No output directory found for '{slug}'")


def _get_ports(slug: str) -> tuple[int, int]:
    """Get backend and frontend ports for a project."""
    project_dir = _find_project_dir(slug)
    frontend_port = 4177  # default
    backend_port = 8000

    # Read from package.json if available
    pkg = project_dir / "frontend" / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            dev_script = data.get("scripts", {}).get("dev", "")
            if "--port" in dev_script:
                parts = dev_script.split("--port")
                if len(parts) > 1:
                    port_str = parts[1].strip().split()[0]
                    frontend_port = int(port_str)
        except (json.JSONDecodeError, ValueError):
            pass

    return backend_port, frontend_port


@router.post("/projects/{slug}/app/start")
def start_app(slug: str):
    project = get_project(slug)
    if not project:
        raise HTTPException(404, "Project not found")

    project_dir = _find_project_dir(slug)
    backend_dir = project_dir / "backend"
    frontend_dir = project_dir / "frontend"
    backend_port, frontend_port = _get_ports(slug)

    if not backend_dir.exists():
        raise HTTPException(400, "No backend directory found")
    if not frontend_dir.exists():
        raise HTTPException(400, "No frontend directory found")

    results = {"backend": None, "frontend": None}

    # Start backend if not running
    if _port_in_use(backend_port):
        results["backend"] = "already running"
    else:
        # Install deps if needed
        req_file = backend_dir / "requirements.txt"
        if req_file.exists():
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)],
                capture_output=True, timeout=60,
            )

        # Seed DB if seed.py exists and DB doesn't
        seed_script = backend_dir / "seed.py"
        db_candidates = list(backend_dir.glob("*.db"))
        if seed_script.exists() and not db_candidates:
            subprocess.run(
                [sys.executable, str(seed_script)],
                cwd=str(backend_dir), capture_output=True, timeout=10,
            )

        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app",
             "--host", "0.0.0.0", "--port", str(backend_port)],
            cwd=str(backend_dir),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        _running.setdefault(slug, {})["backend_pid"] = proc.pid
        results["backend"] = f"started (pid {proc.pid})"

    # Start frontend if not running
    if _port_in_use(frontend_port):
        results["frontend"] = "already running"
    else:
        # Install deps if needed
        if not (frontend_dir / "node_modules").exists():
            subprocess.run(
                "npm install", shell=True,
                cwd=str(frontend_dir), capture_output=True, timeout=120,
            )

        # Use local vite
        vite_bin = frontend_dir / "node_modules" / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")
        if vite_bin.exists():
            proc = subprocess.Popen(
                [str(vite_bin), "--host", "0.0.0.0", "--port", str(frontend_port)],
                cwd=str(frontend_dir),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        else:
            proc = subprocess.Popen(
                "npm run dev", shell=True,
                cwd=str(frontend_dir),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        _running.setdefault(slug, {})["frontend_pid"] = proc.pid
        results["frontend"] = f"started (pid {proc.pid})"

    # Wait a moment and verify
    time.sleep(3)
    results["backend_up"] = _port_in_use(backend_port)
    results["frontend_up"] = _port_in_use(frontend_port)
    results["url"] = f"http://localhost:{frontend_port}"

    return results


@router.post("/projects/{slug}/app/stop")
def stop_app(slug: str):
    backend_port, frontend_port = _get_ports(slug)
    killed = []

    pids = _running.get(slug, {})
    for key in ["backend_pid", "frontend_pid"]:
        pid = pids.get(key)
        if pid:
            try:
                os.kill(pid, signal.SIGTERM if os.name != "nt" else signal.SIGTERM)
                killed.append(pid)
            except (OSError, ProcessLookupError):
                pass

    _running.pop(slug, None)
    return {"stopped": killed, "backend_up": _port_in_use(backend_port), "frontend_up": _port_in_use(frontend_port)}


@router.get("/projects/{slug}/app/status")
def app_status(slug: str):
    backend_port, frontend_port = _get_ports(slug)
    return {
        "backend_up": _port_in_use(backend_port),
        "frontend_up": _port_in_use(frontend_port),
        "backend_port": backend_port,
        "frontend_port": frontend_port,
        "url": f"http://localhost:{frontend_port}",
    }
