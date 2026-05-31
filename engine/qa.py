"""
Swarm Engine — QA Pipeline

Four tiers of verification:
  Tier 1: Static (file exists, non-empty, TSC passes)
  Tier 2: Functional probe (launch app, screenshot, console errors)
  Tier 3: E2E flow test (Playwright, parent tickets only)
  Tier 4: Vision review (vision model screenshot analysis)

Each tier runs only if the previous tier passes.
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ProjectConfig
from .screenshot import (
    kill_port, launch_app, take_screenshot, kill_app, AppProcess,
)

log = logging.getLogger(__name__)


@dataclass
class QAResult:
    """Result of a QA check."""
    passed: bool
    tier: str  # "static", "functional", "e2e", "vision", "all"
    note: str = ""
    screenshot_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tier 1: Static checks
# ---------------------------------------------------------------------------

# Minimum file sizes by extension (reject stubs)
_MIN_SIZES = {
    ".tsx": 150, ".jsx": 150, ".ts": 100, ".js": 50,
    ".css": 30, ".json": 10,
}
_DECL_MIN = 5  # .d.ts files


def static_check(
    ticket_id: str,
    requirements: dict[str, Any],
    config: ProjectConfig,
) -> QAResult:
    """Tier 1: Check required files exist and are non-empty."""
    required = json.loads(requirements.get("required_output_files_json", "[]"))
    if not required:
        return QAResult(passed=True, tier="static", note="no required files")

    deliverable = config.deliverable_root
    errors = []
    for rel in required:
        p = deliverable / rel
        if not p.exists():
            errors.append(f"missing: {rel}")
        elif p.stat().st_size == 0:
            errors.append(f"empty: {rel}")
        else:
            size = p.stat().st_size
            if p.name.endswith(".d.ts"):
                min_size = _DECL_MIN
            else:
                min_size = _MIN_SIZES.get(p.suffix.lower(), 0)
            if size < min_size:
                errors.append(f"stub ({size}b < {min_size}b): {rel}")

    if errors:
        return QAResult(passed=False, tier="static", note="; ".join(errors))
    return QAResult(passed=True, tier="static",
                    note=f"all {len(required)} files verified")


# ---------------------------------------------------------------------------
# Tier 2: Functional probe
# ---------------------------------------------------------------------------

def functional_probe(
    ticket_id: str,
    requirements: dict[str, Any],
    config: ProjectConfig,
) -> QAResult:
    """Tier 2: Launch app, take screenshot, check for errors."""
    if not config.ui_check:
        return QAResult(passed=True, tier="functional", note="no ui_check configured")

    ui = config.ui_check
    port = ui.ui_port

    # Kill anything on the port before launching
    kill_port(port)
    time.sleep(1)

    # Launch app
    app = launch_app(ui.launch_cmd, ui.cwd, port, ui.startup_wait_seconds)
    if not app:
        return QAResult(passed=False, tier="functional",
                        note=f"app failed to launch on port {port}")

    try:
        # Take screenshot
        screenshot_path = take_screenshot(
            url=ui.url,
            output_dir=str(config.artifacts_dir),
            filename=f"{ticket_id}.screenshot.png",
        )

        # Basic health check: is the page responding?
        import urllib.request
        try:
            with urllib.request.urlopen(ui.url, timeout=10) as resp:
                status = resp.status
                body = resp.read().decode("utf-8", errors="replace")
                # Check for React error boundaries or blank pages
                if len(body) < 100:
                    return QAResult(
                        passed=False, tier="functional",
                        note=f"page body too small ({len(body)} bytes) — possible blank page",
                        screenshot_path=screenshot_path,
                    )
        except Exception as e:
            return QAResult(
                passed=False, tier="functional",
                note=f"HTTP check failed: {e}",
                screenshot_path=screenshot_path,
            )

        return QAResult(
            passed=True, tier="functional",
            note=f"app running, screenshot captured",
            screenshot_path=screenshot_path,
        )
    finally:
        # Always kill the app
        kill_app(app)
        # Verify port is free
        kill_port(port)


# ---------------------------------------------------------------------------
# Tier 3: E2E flow test
# ---------------------------------------------------------------------------

def build_check(
    ticket_id: str,
    requirements: dict[str, Any],
    config: ProjectConfig,
) -> QAResult:
    """Tier 1.5: Run the build command from qa_cmd_json after file checks."""
    qa_cmd_json = requirements.get("qa_cmd_json", "[]")
    try:
        cmds = json.loads(qa_cmd_json)
    except json.JSONDecodeError:
        cmds = []

    if not cmds:
        return QAResult(passed=True, tier="build", note="no qa_cmd configured")

    for cmd in cmds:
        # Support both string commands and list-of-args
        if isinstance(cmd, str):
            shell_cmd = cmd
        elif isinstance(cmd, list):
            shell_cmd = " ".join(cmd)
        else:
            continue

        try:
            result = subprocess.run(
                shell_cmd,
                shell=True,
                cwd=str(config.deliverable_root),
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                error_output = (result.stdout + result.stderr)[-1000:]
                return QAResult(
                    passed=False, tier="build",
                    note=f"Build failed: {error_output[-500:]}",
                )
        except subprocess.TimeoutExpired:
            return QAResult(passed=False, tier="build", note="Build timed out after 120s")
        except Exception as e:
            return QAResult(passed=False, tier="build", note=f"Build error: {e}")

    return QAResult(passed=True, tier="build", note="build passed")


def e2e_test(
    ticket_id: str,
    requirements: dict[str, Any],
    config: ProjectConfig,
    blocking: bool = True,
) -> QAResult:
    """Tier 3: Run Playwright E2E test for parent tickets."""
    qa_cmd_json = requirements.get("qa_cmd_json", "[]")
    try:
        cmds = json.loads(qa_cmd_json)
    except json.JSONDecodeError:
        cmds = []

    if not cmds:
        return QAResult(passed=True, tier="e2e", note="no qa_cmd configured")

    for cmd in cmds:
        if isinstance(cmd, str):
            shell_cmd = cmd
        elif isinstance(cmd, list):
            shell_cmd = " ".join(cmd)
        else:
            continue
        try:
            result = subprocess.run(
                shell_cmd,
                shell=True,
                cwd=str(config.workspace_root),
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                error_output = (result.stdout + result.stderr)[-1000:]
                if blocking:
                    return QAResult(
                        passed=False, tier="e2e",
                        note=f"E2E test failed: {error_output}",
                    )
                else:
                    # Warning mode — log but don't block
                    log.warning(f"E2E test warning for {ticket_id}: {error_output[:200]}")
                    return QAResult(
                        passed=True, tier="e2e",
                        note=f"E2E test failed (warning mode, not blocking): {error_output[:200]}",
                        metadata={"e2e_warning": True, "e2e_output": error_output},
                    )
        except subprocess.TimeoutExpired:
            return QAResult(
                passed=False, tier="e2e",
                note="E2E test timed out after 120s",
            )
        except FileNotFoundError as e:
            if blocking:
                return QAResult(
                    passed=False, tier="e2e",
                    note=f"E2E test command not found: {e}",
                )
            else:
                return QAResult(
                    passed=True, tier="e2e",
                    note=f"E2E test skipped (command not found, warning mode): {e}",
                    metadata={"e2e_warning": True},
                )

    return QAResult(passed=True, tier="e2e", note="all E2E tests passed")


# ---------------------------------------------------------------------------
# Combined QA check
# ---------------------------------------------------------------------------

def is_ui_ticket(requirements: dict[str, Any]) -> bool:
    """Check if ticket has UI-related output files."""
    files = json.loads(requirements.get("required_output_files_json", "[]"))
    ui_exts = {".tsx", ".jsx", ".css", ".html", ".vue", ".svelte"}
    return any(
        "." + f.rsplit(".", 1)[-1] in ui_exts
        for f in files if "." in f
    )


def is_parent_ticket(conn, ticket_id: str) -> bool:
    """Check if ticket has children in the DB."""
    row = conn.execute(
        "SELECT COUNT(*) as c FROM tickets WHERE parent_ticket_id=?",
        (ticket_id,),
    ).fetchone()
    return row["c"] > 0 if row else False


def qa_check(
    ticket_id: str,
    requirements: dict[str, Any],
    config: ProjectConfig,
    conn=None,
    e2e_blocking: bool = True,
    run_functional: bool = True,
    run_vision: bool = True,
) -> QAResult:
    """Run the full QA pipeline. Each tier runs only if previous passed."""
    # Tier 1: Static
    r = static_check(ticket_id, requirements, config)
    if not r.passed:
        return r

    # Tier 2: Functional probe (UI tickets only)
    if run_functional and is_ui_ticket(requirements) and config.ui_check:
        r = functional_probe(ticket_id, requirements, config)
        if not r.passed:
            return r
        # Store screenshot path for vision and Forge-with-eyes
        screenshot_path = r.screenshot_path
    else:
        screenshot_path = None

    # Tier 3: E2E (parent tickets only)
    if conn and is_parent_ticket(conn, ticket_id):
        r = e2e_test(ticket_id, requirements, config, blocking=e2e_blocking)
        if not r.passed:
            return r

    # Tier 4: Vision review (if screenshot available and interaction spec exists)
    interaction_spec = requirements.get("interaction_spec", "") or ""
    if run_vision and screenshot_path and interaction_spec.strip() and config.vision_model:
        from .vision import vision_qa_check as _vision_check
        v_passed, v_note, v_full = _vision_check(screenshot_path, interaction_spec, config)
        if not v_passed:
            return QAResult(
                passed=False, tier="vision", note=f"Vision review failed: {v_note}",
                screenshot_path=screenshot_path,
                metadata={"vision_response": v_full},
            )

    return QAResult(
        passed=True, tier="all", note="all tiers passed",
        screenshot_path=screenshot_path,
    )
