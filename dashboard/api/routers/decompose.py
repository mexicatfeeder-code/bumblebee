"""
Decomposition — PRD → ticket plan → commit to DB.

Endpoints:
  POST /api/projects/{slug}/decompose         — generate ticket plan from PRD + Q&A summary
  POST /api/projects/{slug}/decompose/commit   — approve and commit plan to DB
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.config_loader import get_config
from ..services.registry import get_project, update_project

log = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["decompose"])

# Add bumblebee root to path so we can import scripts/decompose.py
_BUMBLEBEE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_BUMBLEBEE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BUMBLEBEE_ROOT))

DEFAULT_LEMONADE_URL = "http://[::1]:13305"


# ---------------------------------------------------------------------------
# LLM bridge for decompose.py
# ---------------------------------------------------------------------------

def _resolve_decomp_model(project: dict | None = None) -> tuple[str, str, str]:
    """Resolve the decomposition model endpoint. Returns (base_url, model_id, api_key)."""
    config = get_config()
    ai = config.get("ai", {})

    source = ai.get("decomp_model_source", "lemonade")
    model_id = ai.get("decomp_model_id", "")

    if project:
        proj_ai = project.get("ai_config", {})
        if proj_ai.get("decomp_model_source"):
            source = proj_ai["decomp_model_source"]
        if proj_ai.get("decomp_model_id"):
            model_id = proj_ai["decomp_model_id"]

    if source == "lemonade":
        base_url = config.get("lemonadeUrl") or ai.get("lemonade_url", DEFAULT_LEMONADE_URL)
        # Auto-detect model from Lemonade if not explicitly set
        if not model_id:
            try:
                resp = httpx.get(f"{base_url.rstrip('/')}/api/v1/health", timeout=5.0)
                if resp.status_code == 200:
                    model_id = resp.json().get("model_loaded", "")
            except Exception:
                pass
        return base_url, model_id, ""
    else:
        base_url = ai.get("custom_api_base_url", "https://api.openai.com/v1")
        api_key = ai.get("custom_api_key", "")
        return base_url, model_id, api_key


def _make_llm_fn(base_url: str, model_id: str, api_key: str):
    """Create a synchronous llm_fn callback for decompose.generate_decomp_plan()."""
    def llm_fn(system_prompt: str, user_prompt: str, image_path: str | None = None) -> str:
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.3,  # Lower temp for structured output
            "max_tokens": 8192,
        }

        # Synchronous call (decompose.py expects sync llm_fn)
        resp = httpx.post(url, json=payload, headers=headers, timeout=180.0)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM returned {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("LLM returned no choices")
        return choices[0].get("message", {}).get("content", "")

    return llm_fn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_prd_text(project: dict) -> str:
    prd_path = project.get("prd_path")
    if not prd_path:
        return ""
    try:
        p = Path(prd_path)
        if not p.is_absolute():
            dashboard_root = Path(__file__).resolve().parent.parent.parent
            p = (dashboard_root / p).resolve()
        return p.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def _get_qa_summary(slug: str) -> str:
    """Read the Q&A summary if it exists."""
    dashboard_root = Path(__file__).resolve().parent.parent.parent
    # Check demos directory first
    demos_path = dashboard_root.parent / "demos" / slug / "qa-summary.md"
    if demos_path.exists():
        return demos_path.read_text(encoding="utf-8", errors="replace").strip()
    # Then check workspace projects
    config = get_config()
    ws = config.get("workspaceRoot", "")
    if ws:
        p = Path(ws) / "bumblebee" / "projects" / slug / "qa-summary.md"
    else:
        p = _BUMBLEBEE_ROOT / "projects" / slug / "qa-summary.md"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace").strip()
    return ""


def _get_project_config_path(slug: str) -> Path:
    """Get the project-config.json path for a project."""
    return _project_dir(slug) / "project-config.json"


def _project_dir(slug: str) -> Path:
    """Resolve the project directory, checking demos/ first."""
    dashboard_root = Path(__file__).resolve().parent.parent.parent
    demos = dashboard_root.parent / "demos" / slug
    if demos.exists():
        return demos
    config = get_config()
    ws = config.get("workspaceRoot", "")
    if ws:
        return Path(ws) / "bumblebee" / "projects" / slug
    return _BUMBLEBEE_ROOT / "projects" / slug


def _plan_cache_path(slug: str) -> Path:
    """Temporary storage for the generated plan before commit."""
    d = _project_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    return d / "decomp-plan.json"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/{slug}/decompose")
def decompose_project(slug: str):
    """
    Generate a ticket plan from the project's PRD + Q&A summary.
    Returns the plan for human review — does NOT commit to DB.
    """
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    prd_text = _get_prd_text(project)
    if not prd_text:
        raise HTTPException(status_code=400, detail="No PRD found. Upload a PRD first.")

    qa_summary = _get_qa_summary(slug)
    base_url, model_id, api_key = _resolve_decomp_model(project)

    if not model_id:
        raise HTTPException(
            status_code=400,
            detail="No decomposition model configured. Set a model in AI Configuration.",
        )

    # Import decompose functions
    from scripts.decompose import generate_decomp_plan

    # Build architecture text from Q&A summary
    arch_text = qa_summary if qa_summary else ""

    # Create LLM callback
    llm_fn = _make_llm_fn(base_url, model_id, api_key)

    # Generate plan
    try:
        plan = generate_decomp_plan(
            prd_text=prd_text,
            architecture_text=arch_text,
            project_slug=slug,
            tech_stack=project.get("tech_stack", ""),
            llm_fn=llm_fn,
        )
    except Exception as e:
        log.exception("Decomposition failed for project '%s'", slug)
        raise HTTPException(status_code=502, detail=f"Decomposition failed: {e}")

    plan_dict = plan.to_dict()

    # Cache the plan for later commit
    cache_path = _plan_cache_path(slug)
    cache_path.write_text(json.dumps(plan_dict, indent=2), encoding="utf-8")

    return {
        "plan": plan_dict,
        "cached": True,
    }


@router.post("/{slug}/decompose/commit")
def commit_decomposition(slug: str):
    """
    Approve and commit the cached decomposition plan to the tickets DB.
    Also creates the project scaffold (project-config.json, DB, directories)
    if it doesn't exist yet.
    """
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load cached plan
    cache_path = _plan_cache_path(slug)
    if not cache_path.exists():
        raise HTTPException(status_code=400, detail="No decomposition plan found. Run decompose first.")

    plan_dict = json.loads(cache_path.read_text(encoding="utf-8"))

    # Re-hydrate the plan
    from scripts.decompose import DecompPlan, TicketSpec, commit_plan

    tickets = []
    for t in plan_dict.get("tickets", []):
        tickets.append(TicketSpec(
            id=t["id"],
            gate=t["gate"],
            description=t["description"],
            required_output_files=t.get("required_output_files", []),
            depends_on=t.get("depends_on", []),
            parent_id=t.get("parent_id"),
            interaction_spec=t.get("interaction_spec", ""),
            constraints=t.get("constraints", []),
            context_files=t.get("context_files", []),
            worker_done_criteria=t.get("worker_done_criteria", ""),
            qa_done_criteria=t.get("qa_done_criteria", ""),
            qa_cmd=t.get("qa_cmd", []),
            requires_live_review=t.get("requires_live_review", False),
            is_parent=t.get("is_parent", False),
        ))

    plan = DecompPlan(
        tickets=tickets,
        total_tickets=plan_dict.get("total_tickets", len(tickets)),
        gate_count=plan_dict.get("gate_count", 0),
        parent_count=plan_dict.get("parent_count", 0),
        child_count=plan_dict.get("child_count", 0),
    )

    if not tickets:
        raise HTTPException(status_code=400, detail="Plan has no tickets to commit.")

    # Ensure project scaffold exists via new_project.py
    from scripts.new_project import create_project as create_project_scaffold, NewProjectRequest

    config_path = _get_project_config_path(slug)
    if not config_path.exists():
        req = NewProjectRequest(
            slug=slug,
            display_name=project.get("name", slug),
            deliverable_root=project.get("deliverable_root", f"./output/{slug}"),
            tech_stack=project.get("tech_stack", ""),
        )
        scaffold_result = create_project_scaffold(
            request=req,
            engine_root=_BUMBLEBEE_ROOT / "engine",
            workspace_root=_BUMBLEBEE_ROOT,
        )
        if not scaffold_result.success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create project scaffold: {scaffold_result.errors}",
            )
        config_path = Path(scaffold_result.config_path)

    # Write AI config into project-config.json
    _inject_ai_config(config_path, project)

    # Get DB path from project config
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    db_path = config_data.get("db_path", str(config_path.parent / "tickets.db"))

    # Commit plan to DB
    from engine.event_log import init_db
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)

    result = commit_plan(plan, conn)
    conn.close()

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to commit plan: {result.errors}",
        )

    # Update project status
    checklist = {**project.get("checklist", {}), "approved": True, "scaffolded": True}
    update_project(slug, {
        "status": "approved",
        "checklist": checklist,
    })

    # Update dashboard config with the new DB path
    dashboard_config = get_config()
    db_paths = dashboard_config.setdefault("ticketDbPaths", {})
    db_paths[slug] = db_path
    from ..services.config_loader import save_config
    save_config(dashboard_config)

    return {
        "success": True,
        "tickets_created": result.tickets_created,
        "db_path": db_path,
    }


def _inject_ai_config(config_path: Path, project: dict) -> None:
    """Write AI model config into the project's project-config.json."""
    config = get_config()
    ai = config.get("ai", {})
    proj_ai = project.get("ai_config", {})

    config_data = json.loads(config_path.read_text(encoding="utf-8"))

    # Determine forge model settings
    forge_source = proj_ai.get("forge_model_source") or ai.get("forge_model_source", "custom")
    forge_model = proj_ai.get("forge_model_id") or ai.get("forge_model_id", "")
    vision_source = proj_ai.get("vision_model_source") or ai.get("vision_model_source", "custom")
    vision_model = proj_ai.get("vision_model_id") or ai.get("vision_model_id", "")
    decomp_source = proj_ai.get("decomp_model_source") or ai.get("decomp_model_source", "lemonade")
    decomp_model = proj_ai.get("decomp_model_id") or ai.get("decomp_model_id", "")

    config_data["models"] = {
        "forge": forge_model,
        "vision": vision_model,
        "decomp": decomp_model,
    }

    # Set API base URL and key based on forge source (coding is the primary consumer)
    if forge_source == "lemonade":
        config_data["api_base_url"] = ai.get("lemonade_url", DEFAULT_LEMONADE_URL) + "/v1"
        config_data["api_key"] = ""
    else:
        config_data["api_base_url"] = ai.get("custom_api_base_url", "https://api.openai.com/v1")
        config_data["api_key"] = ai.get("custom_api_key", "")

    # Also store lemonade URL for phases that use local
    config_data["lemonade_url"] = ai.get("lemonade_url", DEFAULT_LEMONADE_URL)

    config_path.write_text(json.dumps(config_data, indent=2) + "\n", encoding="utf-8")
