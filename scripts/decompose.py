"""
Swarm Engine — Ticket Decomposition

Reads PRD + ARCHITECTURE.md + visual reference, produces tickets with:
- Gate 0: base components + API contract + design tokens
- Gate 1+: feature tickets with interaction specs
- Parent tickets with E2E Playwright test specs
- Visual reference fed to model for spatially-aware decomposition

Designed as importable functions for both CLI and future dashboard use.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ENGINE_ROOT = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(_ENGINE_ROOT.parent))

from engine.event_log import init_db, now_iso
from engine.config import load_config


# ---------------------------------------------------------------------------
# Data structures (dashboard-friendly)
# ---------------------------------------------------------------------------

@dataclass
class TicketSpec:
    """Specification for a single ticket. Dashboard can display/edit these."""
    id: str
    gate: int
    description: str
    required_output_files: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    parent_id: str | None = None
    interaction_spec: str = ""
    constraints: list[str] = field(default_factory=list)
    context_files: list[str] = field(default_factory=list)
    worker_done_criteria: str = ""
    qa_done_criteria: str = ""
    qa_cmd: list[list[str]] = field(default_factory=list)  # E2E test commands
    requires_live_review: bool = False
    is_parent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "gate": self.gate,
            "description": self.description,
            "required_output_files": self.required_output_files,
            "depends_on": self.depends_on,
            "parent_id": self.parent_id,
            "interaction_spec": self.interaction_spec,
            "constraints": self.constraints,
            "context_files": self.context_files,
            "worker_done_criteria": self.worker_done_criteria,
            "qa_done_criteria": self.qa_done_criteria,
            "qa_cmd": self.qa_cmd,
            "requires_live_review": self.requires_live_review,
            "is_parent": self.is_parent,
        }


@dataclass
class DecompPlan:
    """Full decomposition plan. Dashboard displays for human review before commit."""
    tickets: list[TicketSpec] = field(default_factory=list)
    gate_count: int = 0
    total_tickets: int = 0
    parent_count: int = 0
    child_count: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_count": self.gate_count,
            "total_tickets": self.total_tickets,
            "parent_count": self.parent_count,
            "child_count": self.child_count,
            "tickets": [t.to_dict() for t in self.tickets],
            "errors": self.errors,
        }


@dataclass
class DecompResult:
    """Result of committing a decomposition plan to DB."""
    success: bool
    tickets_created: int = 0
    requirements_created: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "tickets_created": self.tickets_created,
            "requirements_created": self.requirements_created,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Archetype scaffold tickets (no LLM needed)
# ---------------------------------------------------------------------------

def react_spa_scaffold(project_slug: str, tech_stack: str = "") -> list[TicketSpec]:
    """Generate foundational Gate 0 scaffold tickets for a React SPA.
    These are predictable and don't need LLM reasoning."""
    return [
        TicketSpec(
            id=f"{project_slug}-G0-PKG",
            gate=0,
            description=(
                "Create package.json with React 18, ReactDOM, Vite, "
                "@vitejs/plugin-react, and TypeScript as dependencies. "
                "Add scripts: dev (vite), build (vite build), preview (vite preview). "
                "Set name, private: true, type: module."
            ),
            required_output_files=["package.json"],
            worker_done_criteria="package.json exists with react, vite, typescript deps",
        ),
        TicketSpec(
            id=f"{project_slug}-G0-VITE",
            gate=0,
            description=(
                "Create vite.config.ts with @vitejs/plugin-react plugin. "
                "Server port from project config. Host 127.0.0.1."
            ),
            required_output_files=["vite.config.ts"],
            depends_on=[f"{project_slug}-G0-PKG"],
            worker_done_criteria="vite.config.ts exists with react plugin",
        ),
        TicketSpec(
            id=f"{project_slug}-G0-TSCONFIG",
            gate=0,
            description=(
                "Create tsconfig.json targeting ES2020, ESNext modules, bundler resolution, "
                "react-jsx, strict mode. Set noUnusedLocals and noUnusedParameters to false. "
                "Include src directory."
            ),
            required_output_files=["tsconfig.json"],
            worker_done_criteria="tsconfig.json exists with correct compiler options",
        ),
        TicketSpec(
            id=f"{project_slug}-G0-HTML",
            gate=0,
            description=(
                "Create index.html with DOCTYPE, charset UTF-8, root div, "
                "and module script tag pointing to /src/main.tsx."
            ),
            required_output_files=["index.html"],
            worker_done_criteria="index.html exists with root div and main.tsx script",
        ),
        TicketSpec(
            id=f"{project_slug}-G0-MAIN",
            gate=0,
            description=(
                "Create src/main.tsx that imports React, ReactDOM, and App component. "
                "Renders App into the root div using createRoot."
            ),
            required_output_files=["src/main.tsx"],
            depends_on=[f"{project_slug}-G0-HTML"],
            worker_done_criteria="main.tsx exists with createRoot render call",
        ),
    ]


def react_express_scaffold(project_slug: str, tech_stack: str = "") -> list[TicketSpec]:
    """Scaffold for React frontend + Express backend (e.g. Remy)."""
    frontend = react_spa_scaffold(project_slug, tech_stack)

    backend = [
        TicketSpec(
            id=f"{project_slug}-G0-SERVER",
            gate=0,
            description=(
                "Create src/server/index.ts with Express 5 server. "
                "Serve static files from dist/ directory. "
                "Mount API routes under /api/. "
                "Listen on the port from project config. "
                "Import shared types from src/shared/api-types.ts."
            ),
            required_output_files=["src/server/index.ts"],
            worker_done_criteria="Server file exists with Express setup and static serving",
        ),
    ]

    return frontend + backend


ARCHETYPE_SCAFFOLDS = {
    "react-spa": react_spa_scaffold,
    "react-express": react_express_scaffold,
}


# ---------------------------------------------------------------------------
# Plan generation (calls LLM)
# ---------------------------------------------------------------------------

def generate_decomp_plan(
    prd_text: str,
    architecture_text: str,
    mvp_text: str = "",
    visual_ref_path: str | None = None,
    project_slug: str = "project",
    tech_stack: str = "",
    archetype: str = "react-spa",
    llm_fn: Any = None,
) -> DecompPlan:
    """
    Generate a decomposition plan from PRD + architecture.
    
    llm_fn: callable(system_prompt, user_prompt, image_path=None) -> str
    If None, returns scaffold tickets only (for testing or manual feature entry).
    
    This function does NOT write to DB — it produces a plan for human review.
    The dashboard would display this plan and let the human edit before committing.
    """
    plan = DecompPlan()

    # Archetype scaffold files are written directly by templates during
    # project setup — they are NOT tickets. Only feature work needs tickets.
    # Write scaffold files now if deliverable_root is provided.
    # (Scaffold tickets were removed because Forge would overwrite the
    # correct template output with broken imports.)

    if llm_fn is None:
        plan.errors.append("No LLM function provided — scaffold tickets only, add feature tickets manually")
        plan.total_tickets = len(plan.tickets)
        plan.gate_count = len({t.gate for t in plan.tickets})
        return plan

    # Build the decomposition prompt
    system_prompt = _build_system_prompt(project_slug, tech_stack)
    user_prompt = _build_user_prompt(prd_text, architecture_text, mvp_text, project_slug)

    try:
        response = llm_fn(system_prompt, user_prompt, image_path=visual_ref_path)
        tickets = _parse_decomp_response(response, project_slug)
        plan.tickets = tickets
        plan.total_tickets = len(tickets)
        plan.parent_count = sum(1 for t in tickets if t.is_parent)
        plan.child_count = sum(1 for t in tickets if t.parent_id)
        gates = {t.gate for t in tickets}
        plan.gate_count = len(gates) if gates else 0
    except Exception as e:
        plan.errors.append(f"LLM decomposition failed: {e}")

    return plan


def _build_system_prompt(project_slug: str, tech_stack: str) -> str:
    slug_upper = project_slug.upper().replace("-", "")
    return f"""You are a senior software architect writing DETAILED build tickets for an automated coding agent (Forge).

Forge is a local LLM (7-30B params). It reliably COPIES code from ticket descriptions but CANNOT invent APIs, guess project structure, or figure out how files connect. Every ticket description must contain the COMPLETE implementation code for Forge to reproduce.

Tech stack: {tech_stack or "Determine from PRD/Q&A summary"}

## CRITICAL: TICKETS MUST CONTAIN COMPLETE CODE

Forge copies code from ticket descriptions. If the description says "implement CRUD", Forge will hallucinate wrong APIs. If the description contains the exact code, Forge copies it correctly.

Every ticket description MUST follow this format:
```
## Objective
One sentence summary.

## Files to write

### path/to/file.ext
```lang
<complete file content — every line, every import, every function>
```
```

For config files (package.json, tsconfig, vite.config): include the COMPLETE file verbatim.
For code files: include the COMPLETE implementation with all imports, all functions, all exports.

## TICKET STRUCTURE

```json
{{{{
  "id": "{slug_upper}-P<gate>-<seq>",
  "gate": <int>,
  "description": "## Objective\\nOne sentence.\\n\\n## Files to write\\n\\n### path/to/file.ext\\n```lang\\n<complete code>\\n```",
  "required_output_files": ["path/to/file.ext"],
  "depends_on": ["{slug_upper}-P0-001"],
  "context_files": ["path/to/dep-file.ext"],
  "constraints": ["exact pattern to follow"],
  "worker_done_criteria": "file exists and exports X",
  "qa_done_criteria": "verify X",
6. **qa_cmd**: Include a build or import check command.
  "requires_live_review": false
}}}}
```

## ARCHITECTURE RULES (decide these FIRST, apply to ALL tickets)

1. **Directory structure**: `frontend/` for React app, `backend/` for API. Never mix.
2. **Frontend dirs**: `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/types/`, `frontend/src/hooks/`, `frontend/src/context/`
3. **Backend dirs**: `backend/main.py`, `backend/database.py`, `backend/schemas.py`, `backend/routers/<resource>.py`
4. **API responses**: ALL endpoints return arrays or single objects directly. `GET /api/items` returns `[{{}}, {{}}]` NOT `{{{{"items": [...]}}}}`.
5. **Backend main.py**: Import and `include_router()` for ALL routers. Use `redirect_slashes=False` on the FastAPI app. Add CORS middleware for localhost origins.
6. **Database**: Sync `sqlite3` only (NOT aiosqlite). `get_db()` returns connection with `row_factory = sqlite3.Row`. All routers call `get_db()` directly — do NOT use FastAPI `Depends()`.
7. **Frontend fetch**: Use `fetch()` with relative URLs (`/api/categories`). Always parse as `await res.json()` which returns the array/object directly.
8. **Shared types**: TypeScript interfaces in `frontend/src/types/index.ts`, Pydantic models in `backend/schemas.py`. These MUST match field-for-field.
9. **Styling**: Use Tailwind CSS utility classes when the tech stack includes Tailwind. Gate 0 MUST include tailwind.config.js, postcss.config.js, and frontend/src/index.css with `@tailwind base; @tailwind components; @tailwind utilities;`. If Tailwind is NOT in the tech stack, use inline styles. NEVER import component-specific .css files — use only Tailwind classes or inline styles.
10. **Routing**: `react-router-dom` v6. `frontend/src/App.tsx` uses `<BrowserRouter>` + `<Routes>` + `<Route>` for every page.

## GATE STRUCTURE

**Gate 0 — Foundation** (every project needs these):
- Ticket for `frontend/package.json` with ALL dependencies (react, react-dom, react-router-dom, typescript, vite, @vitejs/plugin-react, type packages)
- Ticket for `frontend/vite.config.ts` with proxy config: `/api` -> backend port
- Ticket for `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`
- Ticket for `frontend/src/types/index.ts` with ALL TypeScript interfaces
- Ticket for `backend/schemas.py` with ALL Pydantic models (must match TS types)
- Ticket for `backend/database.py` + `backend/seed.py` with schema SQL + seed data
- Each of these tickets contains the VERBATIM file content.

**Gate 1 — Backend API routers** (one ticket per router file):
- Each ticket writes one `backend/routers/<resource>.py` with COMPLETE code
- Every route handler includes exact SQL, exact response shape, exact error handling
- `context_files` includes `database.py` and `schemas.py`

**Gate 2 — Frontend pages** (one ticket per page):
- Each ticket writes one `frontend/src/pages/<Page>.tsx` with COMPLETE JSX
- Includes state management, fetch calls to exact API URLs from Gate 1, all event handlers
- `context_files` includes `types/index.ts` and relevant backend router (to verify API contract)

**Gate 3 — Wiring** (final gate, connects everything):
- `backend/main.py` ticket: imports ALL routers from Gate 1, adds CORS, health check, `redirect_slashes=False`
- `frontend/src/App.tsx` ticket: imports ALL pages from Gate 2, sets up ALL routes
- These tickets list ALL previous output files as `context_files`

## RULES

1. **IDs**: `{slug_upper}-P<gate>-<3-digit-seq>`
2. **1 file per ticket** (max 2). More small tickets > fewer large ones.
3. **Under 150 lines per file**. Split large components into sub-components.
4. **depends_on**: Every gate 1+ ticket depends on relevant gate 0 tickets.
5. **context_files**: Files Forge should read for consistency. CRITICAL for Gate 2+ tickets.
6. **qa_cmd**: Include a verification command. Example: `["cd backend && python -c \\"from routers.orders import router; print('ok')\\""]\`
7. **25-40 tickets** typical. Each completes in 1-2 minutes.
8. **The description IS the implementation**. Forge reads the description and writes what it sees. Vague descriptions = broken code.

## OUTPUT

Return ONLY a JSON array of ticket objects. No markdown, no explanation, no wrapping."""


def _build_user_prompt(prd_text: str, architecture_text: str, mvp_text: str, slug: str) -> str:
    parts = [f"## PRD\n{prd_text[:12000]}"]
    if architecture_text:
        parts.append(f"\n## Technical Summary / Q&A Decisions\n{architecture_text[:8000]}")
    if mvp_text:
        parts.append(f"\n## MVP Scope\n{mvp_text[:4000]}")
    parts.append(f"\nProject slug: {slug}")
    parts.append("\nDecompose this into Forge tickets. REMEMBER: every ticket description must contain the COMPLETE code for each file, not just a description of what to build. Forge copies code from descriptions — vague descriptions produce broken code.")
    parts.append("\nReturn ONLY the JSON array.")
    return "\n".join(parts)


def _parse_decomp_response(response: str, slug: str) -> list[TicketSpec]:
    """Parse LLM response into ticket specs. Handles various JSON formats."""
    # Try to extract JSON from response
    text = response.strip()
    
    # Find JSON array
    start = text.find("[")
    end = text.rfind("]") + 1
    if start < 0 or end <= start:
        raise ValueError("No JSON array found in LLM response")
    
    raw = json.loads(text[start:end])
    tickets = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        tickets.append(TicketSpec(
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
        ))
    return tickets


# ---------------------------------------------------------------------------
# Commit plan to DB
# ---------------------------------------------------------------------------

def commit_plan(
    plan: DecompPlan,
    conn: sqlite3.Connection,
    owner_lane: str = "default",
) -> DecompResult:
    """
    Write a decomposition plan to the database.
    
    This is called AFTER human review. The dashboard would call this
    when the human clicks "Approve" on the plan.
    """
    result = DecompResult(success=False)

    if plan.errors and not plan.tickets:
        result.errors = plan.errors
        return result

    now = now_iso()
    for ticket in plan.tickets:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO tickets 
                   (id, owner, gate, status, depends_on, parent_ticket_id, updated_at)
                   VALUES (?,?,?,'todo',?,?,?)""",
                (ticket.id, owner_lane, ticket.gate,
                 json.dumps(ticket.depends_on), ticket.parent_id, now),
            )
            conn.execute(
                """INSERT OR REPLACE INTO ticket_requirements (
                    ticket_id, ticket_description, required_output_files_json,
                    worker_done_criteria, qa_done_criteria,
                    qa_cmd_json, interaction_spec, constraints_json,
                    context_files_json, requires_live_review,
                    worker_evidence_json, qa_evidence_json,
                    enforce, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
                (
                    ticket.id, ticket.description,
                    json.dumps(ticket.required_output_files),
                    ticket.worker_done_criteria, ticket.qa_done_criteria,
                    json.dumps(ticket.qa_cmd),
                    ticket.interaction_spec,
                    json.dumps(ticket.constraints),
                    json.dumps(ticket.context_files),
                    1 if ticket.requires_live_review else 0,
                    json.dumps([f"artifacts/{ticket.id}.worker.json"]),
                    json.dumps([f"benchmark-qa/reports/{ticket.id}.qa.json"]),
                    now,
                ),
            )
            result.tickets_created += 1
            result.requirements_created += 1
        except Exception as e:
            result.errors.append(f"Failed to insert {ticket.id}: {e}")

    conn.commit()
    result.success = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# CLI wrapper
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Decompose a project into tickets")
    parser.add_argument("--config", required=True, help="Path to project-config.json")
    parser.add_argument("--dry-run", action="store_true", help="Generate plan only, don't commit")
    parser.add_argument("--plan-file", help="Save plan JSON to file for review")
    args = parser.parse_args()

    config = load_config(args.config)

    # Read inputs
    prd_text = ""
    if config.prd_path:
        prd_path = Path(config.prd_path)
        if not prd_path.is_absolute():
            prd_path = config.workspace_root / prd_path
        if prd_path.exists():
            prd_text = prd_path.read_text(encoding="utf-8-sig")

    arch_text = ""
    if config.architecture_path:
        arch_path = Path(config.architecture_path)
        if arch_path.exists():
            arch_text = arch_path.read_text(encoding="utf-8-sig")

    mvp_text = ""
    if config.mvp_path:
        mvp_path = Path(config.mvp_path)
        if not mvp_path.is_absolute():
            mvp_path = config.workspace_root / mvp_path
        if mvp_path.exists():
            mvp_text = mvp_path.read_text(encoding="utf-8-sig")

    # Generate plan (no LLM in CLI yet — manual or provide llm_fn)
    plan = generate_decomp_plan(
        prd_text=prd_text,
        architecture_text=arch_text,
        mvp_text=mvp_text,
        visual_ref_path=config.visual_ref or None,
        project_slug=config.project_root.name,
        tech_stack=config.tech_stack,
        llm_fn=None,  # CLI doesn't call LLM directly — use plan-file workflow
    )

    plan_dict = plan.to_dict()
    print(json.dumps(plan_dict, indent=2))

    if args.plan_file:
        Path(args.plan_file).write_text(json.dumps(plan_dict, indent=2), encoding="utf-8")
        print(f"Plan saved to {args.plan_file}")

    if not args.dry_run and plan.tickets:
        conn = sqlite3.connect(str(config.db_path))
        conn.row_factory = sqlite3.Row
        result = commit_plan(plan, conn)
        conn.close()
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.success else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
