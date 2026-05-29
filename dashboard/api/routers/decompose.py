"""
Decomposition — PRD → ticket plan → commit to DB.

Endpoints:
  POST /api/projects/{slug}/decompose         — generate ticket plan from PRD + Q&A summary
  POST /api/projects/{slug}/decompose/commit   — approve and commit plan to DB
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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
DEFAULT_CLOUD_MODEL = "gpt-4.1-mini"
DEFAULT_CLOUD_BASE_URL = "https://api.openai.com/v1"


# ---------------------------------------------------------------------------
# Cloud key / config helpers
# ---------------------------------------------------------------------------

def _load_cloud_config() -> tuple[str, str, str]:
    """Load cloud API config from ~/.bumblebee/. Returns (base_url, model_id, api_key)."""
    bumblebee_dir = Path.home() / ".bumblebee"

    # Read API key
    key_path = bumblebee_dir / "cloud-api-key.txt"
    api_key = ""
    if key_path.exists():
        api_key = key_path.read_text(encoding="utf-8").strip()
    # Fallback to OPENAI_API_KEY env var
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY", "")

    # Read optional config override
    config_path = bumblebee_dir / "cloud-config.json"
    base_url = DEFAULT_CLOUD_BASE_URL
    model_id = DEFAULT_CLOUD_MODEL
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            base_url = cfg.get("base_url", base_url)
            model_id = cfg.get("model", model_id)
        except (json.JSONDecodeError, OSError):
            pass

    return base_url, model_id, api_key


# ---------------------------------------------------------------------------
# LLM bridge for decompose.py
# ---------------------------------------------------------------------------

def _resolve_decomp_model(project: dict | None = None) -> tuple[str, str, str]:
    """Resolve the decomposition model endpoint. Returns (base_url, model_id, api_key).

    Priority:
    1. Cloud API key in ~/.bumblebee/cloud-api-key.txt (best quality)
    2. Fallback to Lemonade local model (limited quality, warns in logs)
    """
    # Try cloud first
    cloud_url, cloud_model, cloud_key = _load_cloud_config()
    if cloud_key:
        log.info("Decompose: using cloud model %s", cloud_model)
        # Ensure /v1 suffix
        if not cloud_url.rstrip('/').endswith('/v1'):
            cloud_url = cloud_url.rstrip('/') + '/v1'
        return cloud_url, cloud_model, cloud_key

    # Fallback to Lemonade
    log.warning("Decompose: no cloud API key found, falling back to Lemonade (limited quality)")
    config = get_config()
    ai = config.get("ai", {})
    base_url = config.get("lemonadeUrl") or ai.get("lemonade_url", DEFAULT_LEMONADE_URL)
    raw_url = base_url
    if not base_url.rstrip('/').endswith('/v1'):
        base_url = base_url.rstrip('/') + '/v1'
    model_id = ""
    try:
        health_url = raw_url.rstrip('/') + '/api/v1/health'
        resp = httpx.get(health_url, timeout=5.0)
        if resp.status_code == 200:
            health_data = resp.json()
            all_loaded = health_data.get("all_models_loaded", [])
            if all_loaded:
                sift_keywords = ["gemma", "e4b", "sift"]
                for m in all_loaded:
                    mid = (m.get("id") or "").lower()
                    if not any(kw in mid for kw in sift_keywords):
                        model_id = m.get("id", "")
                        break
                if not model_id and all_loaded:
                    model_id = all_loaded[0].get("id", "")
            if not model_id:
                model_id = health_data.get("model_loaded", "")
    except Exception:
        pass
    return base_url, model_id, ""


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
            "max_tokens": 32000,
        }

        # Synchronous call (decompose.py expects sync llm_fn)
        resp = httpx.post(url, json=payload, headers=headers, timeout=600.0)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM returned {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("LLM returned no choices")
        return choices[0].get("message", {}).get("content", "")

    return llm_fn


def _make_streaming_llm(base_url: str, model_id: str, api_key: str):
    """Create a streaming LLM generator that yields text chunks."""
    def stream_fn(system_prompt: str, user_prompt: str):
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 32000,
            "stream": True,
        }

        with httpx.stream("POST", url, json=payload, headers=headers, timeout=600.0) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"LLM returned {resp.status_code}")
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        yield text
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue
    return stream_fn


def _extract_tickets_incrementally(text_stream, slug: str):
    """Parse a streaming JSON array of ticket objects, yielding each complete ticket."""
    buffer = ""
    brace_depth = 0
    in_string = False
    escape_next = False
    obj_start = -1
    found_array = False

    for chunk in text_stream:
        buffer += chunk
        # Process new characters
        i = max(0, len(buffer) - len(chunk))
        while i < len(buffer):
            c = buffer[i]
            if escape_next:
                escape_next = False
                i += 1
                continue
            if c == '\\' and in_string:
                escape_next = True
                i += 1
                continue
            if c == '"':
                in_string = not in_string
                i += 1
                continue
            if in_string:
                i += 1
                continue
            # Outside strings
            if c == '[' and not found_array:
                found_array = True
            elif c == '{':
                if brace_depth == 0:
                    obj_start = i
                brace_depth += 1
            elif c == '}':
                brace_depth -= 1
                if brace_depth == 0 and obj_start >= 0:
                    obj_text = buffer[obj_start:i + 1]
                    try:
                        item = json.loads(obj_text)
                        from scripts.decompose import TicketSpec
                        ticket = TicketSpec(
                            id=item.get("id", ""),
                            gate=int(item.get("gate", 0)),
                            description=item.get("description", item.get("objective", "")),
                            required_output_files=item.get("required_output_files", item.get("files", [])),
                            depends_on=item.get("depends_on", []),
                            parent_id=item.get("parent_id", item.get("parent", None)),
                            interaction_spec=item.get("interaction_spec", ""),
                            constraints=item.get("constraints", []),
                            context_files=item.get("context_files", []),
                            worker_done_criteria=item.get("worker_done_criteria", "Files exist and are non-empty"),
                            qa_done_criteria=item.get("qa_done_criteria", "All checks pass"),
                            qa_cmd=item.get("qa_cmd", []),
                            requires_live_review=bool(item.get("requires_live_review", False)),
                            is_parent=bool(item.get("is_parent", False)),
                        )
                        yield ticket
                    except (json.JSONDecodeError, ValueError):
                        pass
                    obj_start = -1
            i += 1


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
    Returns SSE stream of tickets as they are parsed, then a final plan event.
    Falls back to non-streaming JSON if Accept header doesn't include event-stream.
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

    from scripts.decompose import (
        generate_decomp_plan, DecompPlan, _build_system_prompt, _build_user_prompt,
    )

    arch_text = qa_summary if qa_summary else ""

    # --- SSE streaming path ---
    def _stream_decompose():
        from scripts.decompose import TicketSpec
        system_prompt = _build_system_prompt(slug, project.get("tech_stack", ""))
        user_prompt = _build_user_prompt(prd_text, arch_text, "", slug)
        stream_fn = _make_streaming_llm(base_url, model_id, api_key)

        tickets: list[TicketSpec] = []
        try:
            for ticket in _extract_tickets_incrementally(stream_fn(system_prompt, user_prompt), slug):
                tickets.append(ticket)
                yield f"event: ticket\ndata: {json.dumps(ticket.to_dict())}\n\n"
        except Exception as e:
            log.exception("Streaming decomposition failed for '%s'", slug)
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
            return

        # Build final plan
        gates = {t.gate for t in tickets}
        plan = DecompPlan(
            tickets=tickets,
            total_tickets=len(tickets),
            gate_count=len(gates),
            parent_count=sum(1 for t in tickets if t.is_parent),
            child_count=sum(1 for t in tickets if t.parent_id),
        )
        plan_dict = plan.to_dict()

        # Cache for later commit
        cache_path = _plan_cache_path(slug)
        cache_path.write_text(json.dumps(plan_dict, indent=2), encoding="utf-8")

        yield f"event: plan\ndata: {json.dumps(plan_dict)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        _stream_decompose(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    # Always run scaffold to regenerate template files (reset clears output dir)
    from scripts.new_project import create_project as create_project_scaffold, NewProjectRequest

    config_path = _get_project_config_path(slug)
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
        log.warning("Scaffold creation had errors: %s", scaffold_result.errors)
    if scaffold_result.config_path:
        config_path = Path(scaffold_result.config_path)

    # Write AI config into project-config.json
    _inject_ai_config(config_path, project)

    # Get DB path from project config — resolve relative to the config file's directory
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    raw_db_path = config_data.get("db_path", str(config_path.parent / "tickets.db"))
    db_path_obj = Path(raw_db_path)
    if not db_path_obj.is_absolute():
        db_path_obj = (config_path.parent / db_path_obj).resolve()
    db_path = str(db_path_obj)

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
    """Write AI model config into the project's project-config.json.
    
    Default: Lemonade local models. Only use cloud if explicitly configured.
    Preserves existing config values when new values would be empty.
    """
    config = get_config()
    ai = config.get("ai", {})
    proj_ai = project.get("ai_config", {})
    lemonade_url = ai.get("lemonade_url", DEFAULT_LEMONADE_URL)

    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    existing_models = config_data.get("models", {})

    # Determine forge model — default to Lemonade, only override if explicitly set
    forge_source = proj_ai.get("forge_model_source") or ai.get("forge_model_source", "lemonade")
    forge_model = proj_ai.get("forge_model_id") or ai.get("forge_model_id") or existing_models.get("forge", "Qwen3.6-27B-GGUF")
    vision_model = proj_ai.get("vision_model_id") or ai.get("vision_model_id") or existing_models.get("vision", forge_model)
    decomp_model = proj_ai.get("decomp_model_id") or ai.get("decomp_model_id") or existing_models.get("decomp", "")

    # Only update models — preserve all other config keys (paths, etc.)
    models = config_data.get("models", {})
    models["forge"] = forge_model
    models["vision"] = vision_model
    models["decomp"] = decomp_model
    config_data["models"] = models

    # Default to Lemonade for Forge (local coding is the whole point)
    if forge_source == "lemonade" or not ai.get("custom_api_base_url"):
        config_data["api_base_url"] = lemonade_url + "/v1"
        config_data["api_key"] = ""
    else:
        config_data["api_base_url"] = ai.get("custom_api_base_url", "https://api.openai.com/v1")
        config_data["api_key"] = ai.get("custom_api_key", "")

    config_data["lemonade_url"] = lemonade_url

    config_path.write_text(json.dumps(config_data, indent=2) + "\n", encoding="utf-8")
