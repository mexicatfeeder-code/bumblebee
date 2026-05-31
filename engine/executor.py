"""
Swarm Engine — Single-Cycle Sequential Executor

One process, one loop:
1. ROUTE — advance tickets that can move
2. DISPATCH — if coding work is ready, dispatch ONE Forge run
3. VERIFY — QA check completed tickets
4. CLEANUP — kill any child processes from this cycle
5. SCREENSHOT — capture app state if a UI ticket completed

No inter-process sync. No orphan children.
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import signal
import sqlite3
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .state_machine import StateMachine, TicketState, InvalidTransition, BLOCKED_CODE_ROUTING, RETRY_LIMITS
from .event_log import EventLog, init_db, now_iso
from .config import ProjectConfig
from .postwrite import strip_boms_from_files, run_build_check
from .direct_dispatch import direct_dispatch
from .guardrails import run_guardrails, guardrails_passed, auto_inject_rules
from .templates import write_scaffold_files, REACT_SPA_TEMPLATES

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Process tracking
# ---------------------------------------------------------------------------

_tracked_pids: set[int] = set()


def track_pid(pid: int) -> None:
    _tracked_pids.add(pid)


def cleanup_child_processes() -> None:
    """Kill all tracked child processes. Process tree kill on Windows."""
    global _tracked_pids
    dead: set[int] = set()
    for pid in list(_tracked_pids):
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True, timeout=10,
                )
            else:
                os.kill(pid, signal.SIGTERM)
            dead.add(pid)
        except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
            dead.add(pid)  # already dead
    _tracked_pids -= dead


def _register_cleanup() -> None:
    """Register cleanup on exit and signals."""
    atexit.register(cleanup_child_processes)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: (cleanup_child_processes(), exit(0)))


_register_cleanup()


# ---------------------------------------------------------------------------
# Cycle result
# ---------------------------------------------------------------------------

@dataclass
class CycleResult:
    """Summary of one executor cycle."""
    cycle_number: int = 0
    tickets_routed: int = 0
    tickets_dispatched: int = 0
    tickets_verified: int = 0
    screenshots_taken: int = 0
    errors: list[str] = field(default_factory=list)
    dispatched_ticket_id: str | None = None


# ---------------------------------------------------------------------------
# Guard implementations
# ---------------------------------------------------------------------------

def _deps_satisfied(conn: sqlite3.Connection, depends_on_json: str) -> bool:
    """Check if all dependency tickets are qa_verified."""
    try:
        deps = json.loads(depends_on_json or "[]")
    except json.JSONDecodeError:
        return True
    if not deps:
        return True
    placeholders = ",".join("?" for _ in deps)
    rows = conn.execute(
        f"SELECT id, status FROM tickets WHERE id IN ({placeholders})",
        deps,
    ).fetchall()
    return all(r["status"] == "qa_verified" for r in rows)


def _has_requirements(conn: sqlite3.Connection, ticket_id: str) -> bool:
    """Check if ticket has a ticket_requirements row."""
    row = conn.execute(
        "SELECT ticket_id FROM ticket_requirements WHERE ticket_id=?",
        (ticket_id,),
    ).fetchone()
    return row is not None


def _has_pending_children(conn: sqlite3.Connection, ticket_id: str) -> bool:
    """Check if ticket has children that aren't qa_verified yet."""
    row = conn.execute(
        "SELECT COUNT(*) as c FROM tickets WHERE parent_ticket_id=? AND status != 'qa_verified'",
        (ticket_id,),
    ).fetchone()
    return row["c"] > 0


def _is_parent(conn: sqlite3.Connection, ticket_id: str) -> bool:
    """Check if ticket has any children."""
    row = conn.execute(
        "SELECT COUNT(*) as c FROM tickets WHERE parent_ticket_id=?",
        (ticket_id,),
    ).fetchone()
    return row["c"] > 0


def _all_children_qa_verified(conn: sqlite3.Connection, ticket_id: str) -> bool:
    """Check if ALL children are qa_verified."""
    children = conn.execute(
        "SELECT status FROM tickets WHERE parent_ticket_id=?",
        (ticket_id,),
    ).fetchall()
    if not children:
        return False
    return all(r["status"] == "qa_verified" for r in children)


def _retry_eligible(conn: sqlite3.Connection, ticket_id: str, blocked_code: str | None) -> bool:
    """Check if ticket can be retried based on attempt count and routing."""
    if not blocked_code:
        return False
    routing = BLOCKED_CODE_ROUTING.get(blocked_code)
    if routing not in ("retry", "retry_then_coding"):
        return False
    row = conn.execute(
        "SELECT attempt_count FROM tickets WHERE id=?", (ticket_id,),
    ).fetchone()
    attempts = row["attempt_count"] if row else 0
    limits = RETRY_LIMITS.get(routing, RETRY_LIMITS.get("retry", {}))
    return attempts < limits.get("max_attempts", 3)


# ---------------------------------------------------------------------------
# Executor core
# ---------------------------------------------------------------------------

class Executor:
    """Single-cycle sequential executor."""

    def __init__(
        self,
        config: ProjectConfig,
        state_machine: StateMachine,
        conn: sqlite3.Connection,
        event_log: EventLog,
        dispatch_fn: Callable | None = None,
        qa_fn: Callable | None = None,
        screenshot_fn: Callable | None = None,
    ):
        self.config = config
        self.sm = state_machine
        self.conn = conn
        self.event_log = event_log
        self._dispatch_fn = dispatch_fn or self._default_dispatch
        self._qa_fn = qa_fn or self._default_qa
        self._screenshot_fn = screenshot_fn or self._default_screenshot

        # Register guards with real implementations
        self._register_guards()
        self._register_side_effects()

    def _register_guards(self) -> None:
        """Register guard implementations that query the DB."""
        sm = self.sm
        conn = self.conn

        def deps_and_reqs(ticket: TicketState, ctx: dict) -> bool:
            row = conn.execute("SELECT depends_on FROM tickets WHERE id=?", (ticket.ticket_id,)).fetchone()
            deps_json = row["depends_on"] if row else "[]"
            return _deps_satisfied(conn, deps_json) and _has_requirements(conn, ticket.ticket_id)

        def worker_passed(ticket: TicketState, ctx: dict) -> bool:
            return ctx.get("worker_check_passed", False)

        def worker_failed(ticket: TicketState, ctx: dict) -> bool:
            return ctx.get("worker_check_failed", False)

        def pending_children(ticket: TicketState, ctx: dict) -> bool:
            return _has_pending_children(conn, ticket.ticket_id)

        def qa_passed(ticket: TicketState, ctx: dict) -> bool:
            return ctx.get("qa_check_passed", False)

        def qa_failed(ticket: TicketState, ctx: dict) -> bool:
            return ctx.get("qa_check_failed", False)

        def retry_ok(ticket: TicketState, ctx: dict) -> bool:
            return _retry_eligible(conn, ticket.ticket_id, ticket.blocked_reason_code)

        def coding_done(ticket: TicketState, ctx: dict) -> bool:
            return ctx.get("coding_queue_done", False)

        def manual_fix(ticket: TicketState, ctx: dict) -> bool:
            return ctx.get("manual_fix_verified", False)

        def reclass(ticket: TicketState, ctx: dict) -> bool:
            return ctx.get("reclassification_needed", False)

        def children_done(ticket: TicketState, ctx: dict) -> bool:
            return _all_children_qa_verified(conn, ticket.ticket_id)

        def human_needed(ticket: TicketState, ctx: dict) -> bool:
            return ticket.blocked_reason_code == "human_required"

        def human_input(ticket: TicketState, ctx: dict) -> bool:
            return ctx.get("human_input_received", False)

        def human_rejected(ticket: TicketState, ctx: dict) -> bool:
            return ctx.get("human_rejected_input", False)

        sm.register_guard("deps_satisfied_and_requirements_exist", deps_and_reqs)
        sm.register_guard("worker_check_passed", worker_passed)
        sm.register_guard("worker_check_failed", worker_failed)
        sm.register_guard("has_pending_children", pending_children)
        sm.register_guard("qa_check_passed", qa_passed)
        sm.register_guard("qa_check_failed", qa_failed)
        sm.register_guard("retry_eligible_and_cooldown_elapsed", retry_ok)
        sm.register_guard("coding_queue_done", coding_done)
        sm.register_guard("manual_fix_verified", manual_fix)
        sm.register_guard("reclassification_needed", reclass)
        sm.register_guard("all_children_qa_verified", children_done)
        sm.register_guard("requires_human_input", human_needed)
        sm.register_guard("human_input_received", human_input)
        sm.register_guard("human_rejected_input", human_rejected)

    def _register_side_effects(self) -> None:
        """Register side effect implementations."""
        sm = self.sm
        event_log = self.event_log
        conn = self.conn

        def log_event(ticket: TicketState, transition, ctx: dict) -> None:
            event_log.record(
                ticket_id=ticket.ticket_id,
                from_status=transition.from_state,
                to_status=transition.to_state,
                actor=transition.actor,
                note=ctx.get("note"),
                metadata=ctx.get("metadata"),
            )

        def increment_failure(ticket: TicketState, transition, ctx: dict) -> None:
            conn.execute(
                "UPDATE tickets SET failure_count=failure_count+1 WHERE id=?",
                (ticket.ticket_id,),
            )
            ticket.failure_count += 1

        def increment_attempt(ticket: TicketState, transition, ctx: dict) -> None:
            conn.execute(
                "UPDATE tickets SET attempt_count=attempt_count+1 WHERE id=?",
                (ticket.ticket_id,),
            )
            ticket.attempt_count += 1

        def capture_screenshot(ticket: TicketState, transition, ctx: dict) -> None:
            # Only for UI tickets — check if required files include UI extensions
            req = conn.execute(
                "SELECT required_output_files_json FROM ticket_requirements WHERE ticket_id=?",
                (ticket.ticket_id,),
            ).fetchone()
            if req:
                files = json.loads(req["required_output_files_json"] or "[]")
                ui_exts = {".tsx", ".jsx", ".css", ".html", ".vue", ".svelte"}
                if any(f.rsplit(".", 1)[-1] and f"." + f.rsplit(".", 1)[-1] in ui_exts for f in files):
                    ctx["should_screenshot"] = True

        def classify_failure(ticket: TicketState, transition, ctx: dict) -> None:
            # Set blocked_reason_code from context
            code = ctx.get("blocked_reason_code", "execution_failure")
            ticket.blocked_reason_code = code
            conn.execute(
                "UPDATE tickets SET blocked_reason_code=? WHERE id=?",
                (code, ticket.ticket_id),
            )

        def check_parent(ticket: TicketState, transition, ctx: dict) -> None:
            # Check if this ticket's parent can advance
            row = conn.execute(
                "SELECT parent_ticket_id FROM tickets WHERE id=?",
                (ticket.ticket_id,),
            ).fetchone()
            if row and row["parent_ticket_id"]:
                parent_id = row["parent_ticket_id"]
                if _all_children_qa_verified(conn, parent_id):
                    ctx.setdefault("parents_ready", []).append(parent_id)

        def classify_qa(ticket: TicketState, transition, ctx: dict) -> None:
            code = ctx.get("qa_blocked_reason_code", "qa_failure")
            ticket.blocked_reason_code = code
            conn.execute(
                "UPDATE tickets SET blocked_reason_code=? WHERE id=?",
                (code, ticket.ticket_id),
            )

        sm.register_side_effect("log_event", log_event)
        sm.register_side_effect("increment_failure_count", increment_failure)
        sm.register_side_effect("increment_attempt", increment_attempt)
        sm.register_side_effect("capture_screenshot_if_ui", capture_screenshot)
        sm.register_side_effect("classify_failure", classify_failure)
        sm.register_side_effect("check_parent_ready", check_parent)
        sm.register_side_effect("classify_qa_failure", classify_qa)

    # ── Default implementations (overrideable) ─────────────────────

    def _default_dispatch(self, ticket_id: str, config: ProjectConfig) -> tuple[bool, str]:
        """Default Forge dispatch — placeholder. Override with real dispatch."""
        return False, "no dispatch function configured"

    def _default_qa(self, ticket_id: str, config: ProjectConfig) -> tuple[bool, str]:
        """Default QA: static file check + build command from qa_cmd_json."""
        from .qa import static_check, build_check
        req_row = self.conn.execute(
            "SELECT required_output_files_json, qa_cmd_json FROM ticket_requirements WHERE ticket_id=?",
            (ticket_id,),
        ).fetchone()
        if not req_row:
            return False, "no requirements"
        reqs = dict(req_row)

        # Tier 1: files exist
        r = static_check(ticket_id, reqs, config)
        if not r.passed:
            return False, r.note

        # Tier 1.5: build check (qa_cmd_json)
        r = build_check(ticket_id, reqs, config)
        if not r.passed:
            # Store build error in ticket metadata for next Forge attempt
            meta_row = self.conn.execute(
                "SELECT metadata_json FROM tickets WHERE id=?", (ticket_id,),
            ).fetchone()
            try:
                meta = json.loads(meta_row["metadata_json"] or "{}") if meta_row else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}
            meta["last_build_error"] = r.note[:500]
            self.conn.execute(
                "UPDATE tickets SET metadata_json=? WHERE id=?",
                (json.dumps(meta), ticket_id),
            )
            return False, r.note

        return True, r.note

    def _default_screenshot(self, config: ProjectConfig) -> str | None:
        """Default screenshot — placeholder. Returns None."""
        return None

    # ── Cycle steps ────────────────────────────────────────────────

    def route_ready_tickets(self) -> int:
        """Advance tickets that can move. Returns count of tickets routed."""
        count = 0

        # 1. todo → in_progress (deps satisfied, has requirements)
        #    Only route ONE at a time to avoid saturating Lemonade with concurrent requests.
        already_in_progress = self.conn.execute(
            "SELECT COUNT(*) as c FROM tickets WHERE status='in_progress'"
        ).fetchone()["c"]
        if already_in_progress > 0:
            # Already have a ticket being dispatched -- don't pile on
            pass
        else:
            todos = self.conn.execute(
                "SELECT id, depends_on, blocked_reason_code, assignee, failure_count, attempt_count "
                "FROM tickets WHERE status='todo' ORDER BY gate ASC, id ASC"
            ).fetchall()
            for row in todos:
                ticket = TicketState(
                    ticket_id=row["id"], status="todo",
                    blocked_reason_code=row["blocked_reason_code"],
                    assignee=row["assignee"],
                    failure_count=row["failure_count"] or 0,
                    attempt_count=row["attempt_count"] or 0,
                )
                try:
                    self.sm.transition(ticket, "in_progress", name="claim_ticket")
                    self.conn.execute(
                        "UPDATE tickets SET status='in_progress', assignee='executor', updated_at=? WHERE id=?",
                        (now_iso(), row["id"]),
                    )
                    count += 1
                    break  # Only route ONE ticket per cycle
                except InvalidTransition:
                    pass  # deps not satisfied or no requirements -- skip

        # 2. blocked → todo (retry eligible, children complete, etc.)
        blocked = self.conn.execute(
            "SELECT id, blocked_reason_code, assignee, failure_count, attempt_count "
            "FROM tickets WHERE status='blocked' ORDER BY id ASC"
        ).fetchall()
        for row in blocked:
            ticket = TicketState(
                ticket_id=row["id"], status="blocked",
                blocked_reason_code=row["blocked_reason_code"],
                assignee=row["assignee"],
                failure_count=row["failure_count"] or 0,
                attempt_count=row["attempt_count"] or 0,
            )
            # Try children_complete first (for waiting_on_child_packets)
            if row["blocked_reason_code"] == "waiting_on_child_packets":
                try:
                    self.sm.transition(ticket, "todo", name="children_complete")
                    self.conn.execute(
                        "UPDATE tickets SET status='todo', assignee=NULL, blocked_reason_code=NULL, updated_at=? WHERE id=?",
                        (now_iso(), row["id"]),
                    )
                    count += 1
                    continue
                except InvalidTransition:
                    pass

            # Try retry
            try:
                self.sm.transition(ticket, "todo", name="retry_ticket")
                self.conn.execute(
                    "UPDATE tickets SET status='todo', assignee=NULL, blocked_reason_code=NULL, attempt_count=attempt_count+1, updated_at=? WHERE id=?",
                    (now_iso(), row["id"]),
                )
                count += 1
            except InvalidTransition:
                pass

        self.conn.commit()
        return count

    def _classify_ticket(self, ticket_id: str, requirements: dict) -> str:
        """Classify a ticket into a dispatch category.
        Returns: 'template', 'skip', 'direct', or 'agent'."""
        files = json.loads(requirements.get("required_output_files_json", "[]"))

        # Template: known scaffold files that don't exist yet
        template_files = {"package.json", "vite.config.ts", "vite.config.js",
                         "tsconfig.json", "index.html"}
        if files and all(Path(f).name in template_files for f in files):
            # Check if already written by template
            all_exist = all((self.config.deliverable_root / f).exists() for f in files)
            if all_exist:
                return "skip"  # template already wrote this
            return "template"

        # Skip: file already exists from a prior template write (e.g. main.tsx)
        # Only skip if the file was part of scaffold templates
        scaffold_names = {"main.tsx"}
        if files and all(Path(f).name in scaffold_names for f in files):
            all_exist = all((self.config.deliverable_root / f).exists() for f in files)
            if all_exist:
                return "skip"

        # Default: direct API dispatch (lean, fast, reliable)
        return "direct"

    def _dispatch_template(self, ticket_id: str, requirements: dict) -> tuple[bool, str]:
        """Write scaffold files from templates. No LLM."""
        files = json.loads(requirements.get("required_output_files_json", "[]"))
        if not files:
            return False, "no files to write"

        # Get project variables from config
        variables = {
            "slug": self.config.project_root.name,
            "port": str(self.config.ui_check.ui_port) if self.config.ui_check else "4177",
            "title": self.config.raw.get("display_name", self.config.project_root.name),
        }

        # Map each file to its template
        from .templates import REACT_SPA_TEMPLATES
        templates_to_write = {}
        for rel in files:
            filename = Path(rel).name
            # Match by filename since templates are keyed that way
            for tpl_key, tpl_content in REACT_SPA_TEMPLATES.items():
                if Path(tpl_key).name == filename:
                    templates_to_write[rel] = tpl_content
                    break

        if not templates_to_write:
            return False, f"no templates found for {files}"

        written = write_scaffold_files(self.config.deliverable_root, templates_to_write, variables)
        return True, f"Template: wrote {len(written)} file(s)"

    def _gather_context_files(self, ticket_id: str) -> dict[str, str]:
        """Gather content of files this ticket depends on.
        Reads required_output_files from dependency tickets that are already done."""
        context: dict[str, str] = {}
        # Get this ticket's depends_on
        row = self.conn.execute(
            "SELECT depends_on FROM tickets WHERE id=?", (ticket_id,),
        ).fetchone()
        if not row:
            return context
        try:
            deps = json.loads(row["depends_on"] or "[]")
        except json.JSONDecodeError:
            return context
        # For each dependency, read its output files
        for dep_id in deps:
            dep_req = self.conn.execute(
                "SELECT required_output_files_json FROM ticket_requirements WHERE ticket_id=?",
                (dep_id,),
            ).fetchone()
            if not dep_req:
                continue
            try:
                dep_files = json.loads(dep_req["required_output_files_json"] or "[]")
            except json.JSONDecodeError:
                continue
            for rel in dep_files:
                full_path = self.config.deliverable_root / rel
                if full_path.exists():
                    try:
                        content = full_path.read_text(encoding="utf-8-sig")
                        # Keep context lean — truncate large files
                        if len(content) > 2000:
                            content = content[:2000] + "\n// ... truncated"
                        context[rel] = content
                    except Exception:
                        pass
        # Also include design tokens if they exist (always useful for UI)
        tokens_path = self.config.deliverable_root / "src" / "styles" / "design-tokens.css"
        if tokens_path.exists() and "src/styles/design-tokens.css" not in context:
            try:
                context["src/styles/design-tokens.css"] = tokens_path.read_text(encoding="utf-8-sig")
            except Exception:
                pass
        return context

    def _dispatch_direct(self, ticket_id: str, requirements: dict) -> tuple[bool, str]:
        """Direct API dispatch. Lean context + tool-calling."""
        files_rel = json.loads(requirements.get("required_output_files_json", "[]"))
        files_abs = [str((self.config.deliverable_root / f).resolve()) for f in files_rel]

        # Gather context from dependency tickets
        context_files = self._gather_context_files(ticket_id)

        # Check for previous build error to include as fix guidance
        meta_row = self.conn.execute(
            "SELECT metadata_json FROM tickets WHERE id=?", (ticket_id,),
        ).fetchone()
        last_build_error = ""
        if meta_row and meta_row["metadata_json"]:
            try:
                meta = json.loads(meta_row["metadata_json"])
                last_build_error = meta.get("last_build_error", "")
            except (json.JSONDecodeError, TypeError):
                pass

        arch_rules = [
            "Use TypeScript with React 18",
            "All components use default export",
            "No Node.js built-ins (fs, path, os) in src/",
            "Use CSS custom properties from design-tokens.css (e.g. var(--bg-card)) instead of hardcoded hex values",
            "Import paths must be correct relative to the FILE BEING WRITTEN, not copied from other files",
            "Files in src/components/base/ import design-tokens as ../../styles/design-tokens.css",
            "Files in src/components/ (not base/) import design-tokens as ../styles/design-tokens.css",
            "Files in src/ import design-tokens as ./styles/design-tokens.css",
        ]
        if last_build_error:
            arch_rules.append(f"PREVIOUS BUILD ERROR (fix this): {last_build_error[:500]}")

        # Auto-inject guardrail rules based on file types
        injected = auto_inject_rules(files_abs, arch_rules)
        arch_rules = arch_rules + injected
        if injected:
            log.info(f"Auto-injected {len(injected)} rule(s) for {ticket_id}: {[r[:60] for r in injected]}")

        # Capture baselines for export integrity check
        baselines: dict[str, str] = {}
        for abs_path in files_abs:
            p = Path(abs_path)
            if p.exists():
                try:
                    baselines[str(p.resolve())] = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

        result = direct_dispatch(
            ticket_id=ticket_id,
            objective=requirements.get("ticket_description", ""),
            files_to_write=files_abs,
            architecture_rules=arch_rules,
            interaction_spec=requirements.get("interaction_spec", "") or "",
            context_files=context_files,
            config=self.config,
            timeout_seconds=self.config.forge_timeout_seconds,
        )

        if result.success:
            # Run post-write guardrails
            gr = run_guardrails(
                files_written=result.files_written,
                deliverable_root=self.config.deliverable_root,
                baselines=baselines,
            )
            ok, err = guardrails_passed(gr)
            if not ok:
                log.warning(f"Guardrails FAILED for {ticket_id}: {err}")
                return False, f"Guardrail failure: {err}"

            # Write evidence
            ev_dir = self.config.artifacts_dir
            ev_dir.mkdir(parents=True, exist_ok=True)
            import datetime as _dt
            (ev_dir / f"{ticket_id}.worker.json").write_text(json.dumps({
                "ticket": ticket_id, "status": "completed",
                "duration_s": round(result.duration_seconds, 1),
                "tool_calls": result.tool_calls,
                "files_written": [Path(f).name for f in result.files_written],
                "guardrails": [{"check": r.check, "passed": r.passed, "note": r.note} for r in gr],
            }, indent=2), encoding="utf-8")
            return True, f"Direct: {result.tool_calls} tool call(s) in {result.duration_seconds:.0f}s"
        else:
            log.warning(f"Direct dispatch FAILED for {ticket_id}: {result.error} (duration={result.duration_seconds:.1f}s, tool_calls={result.tool_calls})")
            return False, f"Direct: {result.error}"

    def dispatch_next(self) -> str | None:
        """Dispatch one ticket. Uses three categories: template, direct API, or agent."""
        row = self.conn.execute(
            """SELECT t.id FROM tickets t
               JOIN ticket_requirements tr ON tr.ticket_id = t.id
               WHERE t.status='in_progress' AND t.assignee='executor'
               ORDER BY t.gate ASC, t.id ASC LIMIT 1"""
        ).fetchone()
        if not row:
            return None

        ticket_id = row["id"]

        # Check if this is a parent with pending children — block it
        if _is_parent(self.conn, ticket_id) and _has_pending_children(self.conn, ticket_id):
            ts = TicketState(ticket_id=ticket_id, status="in_progress")
            try:
                self.sm.transition(ts, "blocked", name="parent_waiting_on_children")
                self.conn.execute(
                    "UPDATE tickets SET status='blocked', blocked_reason_code='waiting_on_child_packets', assignee=NULL, updated_at=? WHERE id=?",
                    (now_iso(), ticket_id),
                )
                self.conn.commit()
            except InvalidTransition:
                pass
            return None

        # Load requirements
        req_row = self.conn.execute(
            """SELECT ticket_description, required_output_files_json, interaction_spec,
                      worker_done_criteria, constraints_json, context_files_json
               FROM ticket_requirements WHERE ticket_id=?""",
            (ticket_id,),
        ).fetchone()
        requirements = dict(req_row) if req_row else {}

        # Dispatch: if a custom dispatch_fn was injected (mock/test), use it.
        # Otherwise use three-category dispatch (template → direct → agent).
        if self._dispatch_fn != self._default_dispatch:
            ok, result = self._dispatch_fn(ticket_id, self.config)
        else:
            category = self._classify_ticket(ticket_id, requirements)
            log.info(f"Dispatch {ticket_id} as [{category}]")
            if category == "template":
                ok, result = self._dispatch_template(ticket_id, requirements)
            elif category == "skip":
                # File already exists (written by template), just verify
                ok, result = True, "File already written by template"
            elif category == "direct":
                ok, result = self._dispatch_direct(ticket_id, requirements)
            else:
                ok, result = False, "no dispatch method available"

        # Post-write cleanup
        if ok:
            files = json.loads(requirements.get("required_output_files_json", "[]"))
            stripped = strip_boms_from_files(files, self.config.deliverable_root)
            if stripped:
                log.info(f"Stripped BOMs from {stripped} file(s) for {ticket_id}")

            build_ok, build_note = run_build_check(self.config)
            if not build_ok:
                log.warning(f"Build check failed after {ticket_id}: {build_note}")
                ok = False
                result = f"Post-dispatch build check failed: {build_note}"
                # Store the build error so retry can send it to Forge
                self.conn.execute(
                    "UPDATE tickets SET metadata_json=? WHERE id=?",
                    (json.dumps({"last_build_error": build_note[:1000]}), ticket_id),
                )

        ts = TicketState(ticket_id=ticket_id, status="in_progress")
        if ok:
            try:
                self.sm.transition(ts, "done", name="worker_check_passed",
                                   context={"worker_check_passed": True, "note": result})
                self.conn.execute(
                    "UPDATE tickets SET status='done', updated_at=? WHERE id=?",
                    (now_iso(), ticket_id),
                )
                self.conn.commit()
            except InvalidTransition as e:
                log.error(f"Transition error after dispatch success: {e}")
        else:
            try:
                self.sm.transition(ts, "blocked", name="worker_check_failed",
                                   context={"worker_check_failed": True,
                                           "blocked_reason_code": "execution_failure",
                                           "note": result})
                self.conn.execute(
                    "UPDATE tickets SET status='blocked', blocked_reason_code='execution_failure', "
                    "failure_count=failure_count+1, updated_at=? WHERE id=?",
                    (now_iso(), ticket_id),
                )
                self.conn.commit()
            except InvalidTransition as e:
                log.error(f"Transition error after dispatch failure: {e}")

        return ticket_id

    def verify_done_tickets(self) -> int:
        """Run QA on done tickets. Returns count verified."""
        count = 0
        done = self.conn.execute(
            "SELECT id, blocked_reason_code, assignee, failure_count, attempt_count "
            "FROM tickets WHERE status='done' ORDER BY gate ASC, id ASC"
        ).fetchall()

        for row in done:
            ticket_id = row["id"]
            ok, note = self._qa_fn(ticket_id, self.config)

            ts = TicketState(
                ticket_id=ticket_id, status="done",
                failure_count=row["failure_count"] or 0,
                attempt_count=row["attempt_count"] or 0,
            )

            if ok:
                try:
                    self.sm.transition(ts, "qa_verified", name="qa_passed",
                                       context={"qa_check_passed": True, "note": note})
                    self.conn.execute(
                        "UPDATE tickets SET status='qa_verified', updated_at=? WHERE id=?",
                        (now_iso(), ticket_id),
                    )
                    count += 1
                except InvalidTransition as e:
                    log.error(f"QA transition error: {e}")
            else:
                try:
                    self.sm.transition(ts, "blocked", name="qa_failed",
                                       context={"qa_check_failed": True,
                                               "qa_blocked_reason_code": "qa_failure",
                                               "note": note})
                    self.conn.execute(
                        "UPDATE tickets SET status='blocked', blocked_reason_code='qa_failure', "
                        "failure_count=failure_count+1, updated_at=? WHERE id=?",
                        (now_iso(), ticket_id),
                    )
                except InvalidTransition as e:
                    log.error(f"QA failure transition error: {e}")

        self.conn.commit()
        return count

    # ── Main cycle ─────────────────────────────────────────────────

    def run_cycle(self, cycle_number: int = 0) -> CycleResult:
        """Execute one full cycle: route → dispatch → verify → cleanup."""
        result = CycleResult(cycle_number=cycle_number)

        try:
            # 1. ROUTE
            result.tickets_routed = self.route_ready_tickets()

            # 2. DISPATCH
            dispatched = self.dispatch_next()
            if dispatched:
                result.tickets_dispatched = 1
                result.dispatched_ticket_id = dispatched

            # 3. VERIFY
            result.tickets_verified = self.verify_done_tickets()

        except Exception as e:
            result.errors.append(str(e))
            log.error(f"Cycle {cycle_number} error: {e}")
        finally:
            # 4. CLEANUP — always runs, even on error
            cleanup_child_processes()

        return result

    def run_loop(self, max_cycles: int = 0) -> list[CycleResult]:
        """Run multiple cycles. max_cycles=0 means run until all tickets terminal."""
        results = []
        cycle = 0
        while True:
            cycle += 1
            r = self.run_cycle(cycle)
            results.append(r)

            # Check if all tickets are terminal
            non_terminal = self.conn.execute(
                "SELECT COUNT(*) as c FROM tickets WHERE status NOT IN ('qa_verified')"
            ).fetchone()["c"]
            if non_terminal == 0:
                break

            # Check if nothing happened this cycle and nothing is in_progress
            if r.tickets_routed == 0 and r.tickets_dispatched == 0 and r.tickets_verified == 0:
                in_progress = self.conn.execute(
                    "SELECT COUNT(*) as c FROM tickets WHERE status='in_progress'"
                ).fetchone()["c"]
                if in_progress == 0:
                    break  # nothing to do, system is stuck

            if max_cycles and cycle >= max_cycles:
                break

            time.sleep(self.config.cycle_interval_seconds)

        # --- Integration / Wiring Pass ---
        # After all tickets are done, run a cloud model to fix cross-file connections
        qa_verified = self.conn.execute(
            "SELECT COUNT(*) as c FROM tickets WHERE status='qa_verified'"
        ).fetchone()["c"]
        total = self.conn.execute("SELECT COUNT(*) as c FROM tickets").fetchone()["c"]
        blocked = self.conn.execute(
            "SELECT COUNT(*) as c FROM tickets WHERE status='blocked'"
        ).fetchone()["c"]

        if qa_verified > 0 and (qa_verified + blocked) == total:
            log.info("All tickets processed (%d verified, %d blocked). Running integration pass...", qa_verified, blocked)
            try:
                from .integration import run_integration
                deliverable_root = Path(self.config.deliverable_root)
                ok, note, files_written = run_integration(self.config, deliverable_root)
                if ok:
                    log.info("Integration pass completed: %s", note)
                    if files_written:
                        for f in files_written:
                            log.info("  + %s", f)
                else:
                    log.warning("Integration pass failed: %s", note)
            except Exception as e:
                log.error("Integration pass error: %s", e)

        return results
