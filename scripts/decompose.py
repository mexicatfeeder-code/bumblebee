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
    return f"""You are a senior software architect decomposing a PRD into build tickets for an automated coding agent (Forge).
Forge is a local LLM that writes code from ticket specs. It is reliable at creating 1-8 files per ticket when given exact file paths, but UNRELIABLE at guessing APIs or project structure. Your job is to produce tickets detailed enough that Forge can build the entire app without human intervention.

Tech stack: {tech_stack or "Determine from PRD/Q&A summary"}

## TICKET STRUCTURE (every field matters)

```json
{{
  "id": "{slug_upper}-P<gate>-<seq>",
  "gate": <int>,
  "description": "What to build. Be specific about behavior, not vague.",
  "required_output_files": ["path/to/file.ext"],
  "depends_on": ["{slug_upper}-P0-001"],
  "context_files": ["path/to/file-from-earlier-gate.ext"],
  "interaction_spec": "For UI tickets: step-by-step user interaction.",
  "constraints": ["Use X pattern", "Import from Y"],
  "worker_done_criteria": "Specific: file exists, exports X, handles Y",
  "qa_done_criteria": "What to verify",
  "qa_cmd": [],
  "requires_live_review": false
}}
```

## RULES

1. **IDs**: `{slug_upper}-P<gate>-<3-digit-seq>` (e.g. {slug_upper}-P0-001, {slug_upper}-P1-003)
2. **Gates**: Use 3-5 gates. Gate 0 = foundation (types, DB, shared components, API skeleton). Gate 1+ = features.
3. **required_output_files**: MANDATORY for every ticket. Exact relative paths. **1-3 files per ticket maximum. NO EXCEPTIONS, including foundation/setup tickets.** Split larger work into multiple tickets. A 13-file setup must become 5-6 separate tickets. More small tickets is always better than fewer large ones.
4. **depends_on**: Reference ticket IDs from earlier gates when the ticket needs those files.
5. **context_files**: List files from earlier tickets that Forge should READ to understand the codebase. Critical for consistency.
6. **constraints**: Inline specific patterns Forge must follow (e.g. "Use `router.get()` not `app.get()`", "Import Button from '../ui/Button'"). Forge hallucinates APIs without these.
7. **worker_done_criteria**: Be specific. Not "files exist" but "file exports MenuBrowse component that fetches from /api/menu and renders items grouped by category".
8. **No orphan tickets**: Every gate 1+ ticket should depend_on at least one gate 0 ticket and list context_files.
9. **Split backend and frontend**: API endpoints and UI pages should be separate tickets with explicit deps between them.
10. **WebSocket/real-time**: If the PRD requires real-time updates, include the WebSocket server setup in gate 0 and client hooks in the relevant feature gate.
11. **Aim for 15-30 tickets** for a typical app. Each ticket is one focused task that produces 1-3 files.

## OUTPUT

Return ONLY a JSON array of ticket objects. No markdown, no explanation, no wrapping."""



def _build_user_prompt(prd_text: str, architecture_text: str, mvp_text: str, slug: str) -> str:
    parts = [f"## PRD\n{prd_text[:12000]}"]
    if architecture_text:
        parts.append(f"\n## Technical Summary / Q&A Decisions\n{architecture_text[:8000]}")
    if mvp_text:
        parts.append(f"\n## MVP Scope\n{mvp_text[:4000]}")
    parts.append(f"\nProject slug: {slug}")
    parts.append("\nDecompose this into Forge tickets. Return ONLY the JSON array.")
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
