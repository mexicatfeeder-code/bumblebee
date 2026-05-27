from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
from pathlib import Path

log = logging.getLogger(__name__)
router = APIRouter(prefix="/intake", tags=["intake"])

from ..services.registry import list_projects, get_project, create_project, update_project
import json


def _read_prd(prd_path: str | None, max_chars: int = 4000) -> str | None:
    """Read PRD file content, truncating if large."""
    if not prd_path:
        return None
    try:
        p = Path(prd_path)
        if not p.is_absolute():
            # Resolve relative to dashboard root
            dashboard_root = Path(__file__).resolve().parent.parent.parent
            p = (dashboard_root / p).resolve()
        text = p.read_text(encoding="utf-8", errors="replace").strip()
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[…truncated at {max_chars} chars]"
        return text
    except Exception as e:
        log.warning("Could not read PRD at %s: %s", prd_path, e)
        return None


def _build_qa_kickoff_message(project: dict) -> str:
    """Build the Telegram message Pixel receives when Q&A is kicked off."""
    name = project.get("name", "(unnamed)")
    slug = project.get("slug", "")
    description = project.get("description", "").strip()
    deliverable = project.get("deliverable_root", "")
    tech_stack = project.get("tech_stack") or "not specified"
    target_system = project.get("target_system") or "local"
    prd_text = _read_prd(project.get("prd_path"))

    # Ref images — stored paths from the registry
    raw_refs = project.get("ref_paths") or []
    if isinstance(raw_refs, str):
        # Registry sometimes stores as JSON string
        try:
            raw_refs = json.loads(raw_refs)
        except Exception:
            raw_refs = [r.strip() for r in raw_refs.split(",") if r.strip()]
    ref_paths = [str(p) for p in raw_refs if p]

    lines = [
        f"🐾 New project intake started from the dashboard.",
        "",
        f"**Project:** {name} (`{slug}`)",
    ]
    if description:
        lines.append(f"**Description:** {description}")
    lines += [
        f"**Deliverable root:** `{deliverable}`",
        f"**Tech stack:** {tech_stack}",
        f"**Target system:** {target_system}",
    ]
    if prd_text:
        lines += ["", "**PRD:**", "```", prd_text, "```"]
    else:
        lines.append("\n_(No PRD file found — check the project's bumblebee directory.)_")
    if ref_paths:
        lines.append("")
        lines.append(f"**Visual references ({len(ref_paths)} file{'s' if len(ref_paths) != 1 else ''}):**")
        for p in ref_paths:
            lines.append(f"- `{p}`")
        lines.append("_Use the `image` tool on each path above to review the visuals before asking design questions._")
    else:
        lines.append("\n_(No visual references uploaded.)_")
    lines += [
        "",
        "Please start the Q&A for this project. Ask the questions needed to produce a solid VISUAL-SPEC.md and ARCHITECTURE.md.",
    ]
    return "\n".join(lines)


def _write_qa_request(project: dict) -> None:
    """Write a qa-request.json in the project's bumblebee directory so Pixel can find it."""
    try:
        from ..services.config_loader import get_config
        config = get_config()
        ws = config.get("workspaceRoot", "")
        slug = project.get("slug", "")
        proj_dir = Path(ws) / "bumblebee" / "projects" / slug
        proj_dir.mkdir(parents=True, exist_ok=True)
        request_file = proj_dir / "qa-request.json"
        request_file.write_text(json.dumps({
            "slug": slug,
            "name": project.get("name"),
            "description": project.get("description"),
            "deliverable_root": project.get("deliverable_root"),
            "prd_path": project.get("prd_path"),
            "ref_paths": project.get("ref_paths", []),
            "target_system": project.get("target_system"),
            "status": "qa_pending",
        }, indent=2))
        log.info("Wrote Q&A request to %s", request_file)
    except Exception as e:
        log.warning("Failed to write Q&A request file: %s", e)


class AIConfigRequest(BaseModel):
    qa_model_source: Optional[str] = None
    qa_model_id: Optional[str] = None
    decomp_model_source: Optional[str] = None
    decomp_model_id: Optional[str] = None
    forge_model_source: Optional[str] = None
    forge_model_id: Optional[str] = None
    vision_model_source: Optional[str] = None
    vision_model_id: Optional[str] = None
    custom_api_base_url: Optional[str] = None
    custom_api_key: Optional[str] = None


class CreateProjectRequest(BaseModel):
    name: str
    slug: str
    description: str
    deliverable_root: str
    target_system: str = "local"
    ai_config: Optional[AIConfigRequest] = None


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    deliverable_root: Optional[str] = None
    target_system: Optional[str] = None
    status: Optional[str] = None
    tech_stack: Optional[str] = None
    checklist: Optional[dict] = None


def _blocked_counts() -> dict[str, int]:
    """Return {slug: blocked_ticket_count} for all projects with a known tickets DB."""
    from ..services.config_loader import get_config
    import sqlite3
    cfg = get_config()
    db_paths = cfg.get("ticketDbPaths", {})
    counts = {}
    for slug, db_path in db_paths.items():
        try:
            conn = sqlite3.connect(db_path, timeout=2)
            row = conn.execute(
                "SELECT COUNT(*) FROM tickets WHERE status = 'blocked'"
            ).fetchone()
            counts[slug] = row[0] if row else 0
            conn.close()
        except Exception:
            counts[slug] = 0
    return counts


@router.get("/projects")
def get_projects():
    projects = list_projects()
    blocked = _blocked_counts()
    for p in projects:
        p["blocked_count"] = blocked.get(p["slug"], 0)
    return {"projects": projects}


@router.post("/projects", status_code=201)
def post_project(body: CreateProjectRequest):
    try:
        project = create_project(
            name=body.name,
            slug=body.slug,
            description=body.description,
            deliverable_root=body.deliverable_root,
            target_system=body.target_system,
        )
        # Store AI config in registry for this project
        if body.ai_config:
            ai_dict = body.ai_config.model_dump(exclude_none=True)
            if ai_dict:
                update_project(body.slug, {"ai_config": ai_dict})
                project["ai_config"] = ai_dict
        return project
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/projects/{slug}")
def get_project_by_slug(slug: str):
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/projects/{slug}")
def patch_project(slug: str, body: UpdateProjectRequest):
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    updated = update_project(slug, body.model_dump(exclude_none=True))
    return updated


@router.post("/projects/{slug}/begin-qa")
def begin_qa(slug: str):
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("status") != "intake":
        raise HTTPException(
            status_code=400,
            detail=f"Project status is '{project.get('status')}', expected 'intake'",
        )
    if not project.get("checklist", {}).get("prd_uploaded"):
        raise HTTPException(
            status_code=400,
            detail="PRD not yet uploaded (checklist.prd_uploaded is False)",
        )
    updated = update_project(slug, {"status": "qa_pending"})
    # Write a Q&A request file so Pixel can find the project details
    _write_qa_request(project)
    log.info("Q&A requested for project '%s' (%s). PRD at: %s", project.get('name'), slug, project.get('prd_path'))

    # Notify Pixel via Telegram
    try:
        from ..services.config_loader import get_config
        from ..services.openclaw_gateway import send_telegram_message
        cfg = get_config()
        chat_id = cfg.get("telegramChatId", "")
        if chat_id:
            msg = _build_qa_kickoff_message(project)
            sent = send_telegram_message(chat_id, msg)
            if not sent:
                log.warning("Telegram notification failed for Q&A kickoff (non-fatal)")
        else:
            log.info("telegramChatId not configured — skipping Telegram notification")
    except Exception as e:
        log.warning("Q&A Telegram notification error (non-fatal): %s", e)

    return {"ok": True, "status": "qa_pending", "project": updated or project}


@router.post("/projects/{slug}/approve")
def approve_project(slug: str):
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("status") != "qa_complete":
        raise HTTPException(
            status_code=400,
            detail=f"Project status is '{project.get('status')}', expected 'qa_complete'",
        )
    if not project.get("checklist", {}).get("qa_complete"):
        raise HTTPException(
            status_code=400,
            detail="QA not yet complete (checklist.qa_complete is False)",
        )
    checklist = {**project.get("checklist", {}), "approved": True}
    updated = update_project(slug, {"status": "approved", "checklist": checklist})
    return {"ok": True, "status": "approved"}


@router.post("/projects/{slug}/begin-build")
def begin_build(slug: str):
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("status") != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Project status is '{project.get('status')}', expected 'approved'",
        )
    checklist = {**project.get("checklist", {}), "scaffolded": True}
    updated = update_project(slug, {"status": "scaffolded", "checklist": checklist})
    return {"ok": True, "status": "scaffolded"}


@router.get("/projects/{slug}/qa-status")
def qa_status(slug: str):
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    deliverable_root = project.get("deliverable_root", "bumblebee")
    base = Path(deliverable_root) / "projects" / slug
    visual_spec_found = (base / "VISUAL-SPEC.md").exists()
    architecture_found = (base / "ARCHITECTURE-SUMMARY.md").exists()
    return {
        "visual_spec_found": visual_spec_found,
        "architecture_found": architecture_found,
    }
