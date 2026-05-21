"""
Bumblebee Manual Smoke Test
===========================

Run after a Forge dispatch (or at phase boundaries) to validate the app
renders without errors. This is Tier 2 QA — it goes beyond the static file
check and build check that run automatically.

Usage:
    python bumblebee/scripts/smoke_test.py --project dashboard
    python bumblebee/scripts/smoke_test.py --project remy --url http://127.0.0.1:4177

What it does:
    1. Reads the project config to find the UI check settings
    2. Kills anything on the configured port
    3. Launches the dev server
    4. Waits for startup
    5. Hits the root URL and checks HTTP status
    6. Checks page body is non-trivial (not a blank/crash page)
    7. Takes a screenshot (saved to project artifacts dir)
    8. Kills the dev server
    9. Reports pass/fail with screenshot path

When to run:
    - After a multi-ticket phase completes (all qa_verified) before human review
    - Before Phase 4 Stage B sign-off
    - After any dispatch that touches +page.svelte or shared layout files
    - Whenever you want confidence the app actually renders

When NOT to run automatically (per-ticket):
    - Too slow (~15s per ticket including dev server startup/teardown)
    - Port conflict risk if dev server already running
    - Process cleanup messier on Windows than Linux
    - A flaky smoke test would block valid tickets

This script is intentionally separate from the executor loop.
"""
import argparse
import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from engine.config import load_config
from engine.qa import functional_probe
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run functional smoke test for a Bumblebee project")
    parser.add_argument("--project", required=True, help="Project slug (e.g. dashboard, remy)")
    parser.add_argument("--url", help="Override the URL to test (default: from project config)")
    parser.add_argument("--ticket", default="manual-smoke-test", help="Ticket ID for screenshot naming")
    args = parser.parse_args()

    repo_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    config_path = repo_root / "projects" / args.project / "project-config.json"

    if not config_path.exists():
        log.error(f"Project config not found: {config_path}")
        sys.exit(1)

    config = load_config(str(config_path))

    if not config.ui_check:
        log.error(f"No ui_check configured in project-config.json for '{args.project}'")
        log.error("Add a ui_check block: { launch_cmd, cwd, url, ui_port, startup_wait_seconds }")
        sys.exit(1)

    log.info(f"Running smoke test for project: {args.project}")
    log.info(f"Launch command: {config.ui_check.launch_cmd}")
    log.info(f"URL: {args.url or config.ui_check.url}")

    requirements = {"required_output_files_json": "[]"}  # not needed for functional probe

    result = functional_probe(
        ticket_id=args.ticket,
        requirements=requirements,
        config=config,
    )

    print()
    if result.passed:
        print(f"✓ SMOKE TEST PASSED — {result.note}")
        if result.screenshot_path:
            print(f"  Screenshot: {result.screenshot_path}")
        sys.exit(0)
    else:
        print(f"✗ SMOKE TEST FAILED — {result.note}")
        if result.screenshot_path:
            print(f"  Screenshot: {result.screenshot_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
