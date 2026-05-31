"""
Swarm Engine — Integration / Wiring Pass

After Forge writes individual files, this step uses a cloud model (GPT-mini)
to read ALL generated source files and fix the integration layer:
  - Import references between files
  - Route wiring (App.tsx, router setup)
  - API endpoint URLs matching backend routes
  - Missing barrel exports / index files
  - State management connections

This is the step that turns isolated files into a functional app.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from .config import ProjectConfig

log = logging.getLogger(__name__)

# Cloud API defaults (same as decompose)
DEFAULT_CLOUD_BASE_URL = "https://api.openai.com/v1"
DEFAULT_CLOUD_MODEL = "gpt-5.5"

WRITE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write or overwrite a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "content": {"type": "string", "description": "Complete file content"},
            },
            "required": ["path", "content"],
        },
    },
}


def _load_cloud_config() -> tuple[str, str, str]:
    """Load cloud API config. Returns (base_url, model_id, api_key)."""
    bumblebee_dir = Path.home() / ".bumblebee"

    key_path = bumblebee_dir / "cloud-api-key.txt"
    api_key = ""
    if key_path.exists():
        api_key = key_path.read_text(encoding="utf-8").strip()
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY", "")

    config_path = bumblebee_dir / "cloud-config.json"
    base_url = DEFAULT_CLOUD_BASE_URL
    model_id = DEFAULT_CLOUD_MODEL
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            base_url = cfg.get("base_url", base_url)
            model_id = cfg.get("integration_model", cfg.get("model", model_id))
        except (json.JSONDecodeError, OSError):
            pass

    return base_url, model_id, api_key


def _collect_source_files(deliverable_root: Path) -> dict[str, str]:
    """Read all source files from the deliverable root. Returns {path: content}."""
    files = {}
    if not deliverable_root.exists():
        return files

    # Common source extensions
    extensions = {
        ".ts", ".tsx", ".js", ".jsx", ".py", ".css", ".html",
        ".json", ".svelte", ".vue", ".yaml", ".yml", ".toml",
        ".sql", ".sh", ".ps1", ".md",
    }
    # Skip directories
    skip_dirs = {
        "node_modules", ".git", "__pycache__", "dist", "build",
        ".svelte-kit", ".next", ".vite", "venv", ".env",
    }

    for p in sorted(deliverable_root.rglob("*")):
        if p.is_dir():
            continue
        # Skip unwanted directories
        if any(skip in p.parts for skip in skip_dirs):
            continue
        if p.suffix.lower() not in extensions:
            continue
        # Skip very large files
        try:
            if p.stat().st_size > 50_000:
                continue
            content = p.read_text(encoding="utf-8", errors="replace")
            rel = str(p.relative_to(deliverable_root)).replace("\\", "/")
            files[rel] = content
        except Exception:
            continue

    return files


def _build_integration_prompt(files: dict[str, str], tech_stack: str, project_name: str) -> tuple[str, str]:
    """Build system + user prompts for the integration pass."""

    system = f"""You are a senior integration engineer. You have been given all the source files for a {tech_stack} app called "{project_name}" that were written by separate coding agents working on individual tickets.

Your job is to make this a FUNCTIONAL app by fixing the integration layer. The individual files are well-written but may not connect to each other properly.

## What to fix:
1. **App entry point / Router** - Create or fix the main App.tsx/App.jsx to import and route to ALL pages
2. **Missing imports** - Fix import paths that reference files that don't exist or use wrong names
3. **API URL consistency** - Ensure frontend API calls match backend route paths
4. **Barrel exports** - Add index.ts files if components import from directories
5. **Missing glue files** - Create any small files needed to wire things together (e.g. api client, route config)
6. **Package.json scripts** - Ensure start/build/dev scripts are correct
7. **Environment/config** - Add any missing config files (.env, vite.config.ts, etc.)

## Rules:
- Do NOT rewrite existing files unless fixing imports or adding missing exports
- Do NOT change business logic or component behavior
- Keep changes minimal and focused on wiring
- Use the write_file tool to create or update files
- Write COMPLETE file contents (not patches)
- Only fix what's actually broken - don't refactor working code"""

    # Build file listing
    file_listing = []
    for path, content in sorted(files.items()):
        file_listing.append(f"### {path}\n```\n{content}\n```")

    user = f"""Here are all the source files for the app:\n\n{"".join(file_listing)}\n
Review these files and use the write_file tool to fix any integration issues.
Focus on making the app functional - router wiring, imports, API connections, and any missing glue code.
If everything looks properly connected already, just write a single file called INTEGRATION_OK.md with "No integration fixes needed."
"""

    return system, user


def run_integration(config: ProjectConfig, deliverable_root: Path | str) -> tuple[bool, str, list[str]]:
    """Run the cloud integration pass on all generated source files.

    Returns: (success, summary_note, files_written)
    """
    deliverable_root = Path(deliverable_root)
    base_url, model_id, api_key = _load_cloud_config()

    if not api_key:
        return False, "No cloud API key configured (~/.bumblebee/cloud-api-key.txt)", []

    # Collect all source files
    files = _collect_source_files(deliverable_root)
    if not files:
        return False, f"No source files found in {deliverable_root}", []

    log.info("Integration pass: %d source files, using %s", len(files), model_id)

    tech_stack = getattr(config, "tech_stack", "") or "web application"
    project_name = getattr(config, "display_name", "") or "App"
    system, user = _build_integration_prompt(files, tech_stack, project_name)

    # Check prompt size - truncate if too large
    total_chars = len(system) + len(user)
    if total_chars > 400_000:
        log.warning("Integration prompt very large (%d chars), may hit token limits", total_chars)

    # API call to cloud model
    payload = json.dumps({
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "tools": [WRITE_TOOL],
        "tool_choice": "auto",
        "temperature": 1.0 if model_id.startswith("gpt-5") else 0.1,
        **({"max_completion_tokens": 16384} if model_id.startswith("gpt-5") else {"max_tokens": 16384}),
    }).encode("utf-8")

    url = f"{base_url.rstrip('/')}/chat/completions"
    if not url.endswith("/chat/completions"):
        url = f"{base_url.rstrip('/')}/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        return False, f"Cloud API error {e.code}: {body}", []
    except Exception as e:
        return False, f"Cloud API request failed: {e}", []

    elapsed = time.time() - start
    log.info("Integration API call completed in %.1fs", elapsed)

    # Parse response - extract tool calls
    files_written = []
    message = data.get("choices", [{}])[0].get("message", {})
    tool_calls = message.get("tool_calls", [])

    if not tool_calls:
        # Model responded with text only - no fixes needed
        content = message.get("content", "")
        log.info("Integration: no tool calls, model says: %s", content[:200])
        return True, "Integration check passed - no fixes needed", []

    for tc in tool_calls:
        if tc.get("function", {}).get("name") != "write_file":
            continue
        try:
            args = json.loads(tc["function"]["arguments"])
            path = args.get("path", "")
            content = args.get("content", "")
            if not path or not content:
                continue

            # Write the file
            out_path = deliverable_root / path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            files_written.append(path)
            log.info("Integration wrote: %s (%d chars)", path, len(content))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Integration failed to write file from tool call: %s", e)

    summary = f"Integration pass: {len(files_written)} file(s) written in {elapsed:.1f}s"
    log.info(summary)
    return True, summary, files_written
