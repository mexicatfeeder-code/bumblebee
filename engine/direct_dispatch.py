"""
Swarm Engine — Direct LLM Dispatch

Calls any OpenAI-compatible API directly with tool-calling enabled.
Minimal context: just the task + write tool. No agent wrapper,
no skills, no conversation history.

This is for structured coding tickets where the model needs to
understand requirements and write files.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ProjectConfig
from .postwrite import strip_bom

log = logging.getLogger(__name__)

# The write tool definition — minimal, just what the model needs
WRITE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write content to a file at the given absolute path. Creates parent directories if needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute file path to write to",
                },
                "content": {
                    "type": "string",
                    "description": "The full file content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
}


@dataclass
class DirectDispatchResult:
    success: bool
    ticket_id: str
    duration_seconds: float = 0.0
    files_written: list[str] = field(default_factory=list)
    error: str = ""
    tool_calls: int = 0
    model_response: str = ""


def _get_api_url(config: ProjectConfig) -> str:
    """Get API base URL from config or environment."""
    return config.get_api_base_url()


def _get_api_key(config: ProjectConfig) -> str:
    """Get API key from config or environment."""
    return config.get_api_key()


def direct_dispatch(
    ticket_id: str,
    objective: str,
    files_to_write: list[str],  # absolute paths
    architecture_rules: list[str] | None = None,
    interaction_spec: str = "",
    context_files: dict[str, str] | None = None,  # {rel_path: content} of files to read
    config: ProjectConfig | None = None,
    model: str = "",
    timeout_seconds: int = 300,
) -> DirectDispatchResult:
    """
    Dispatch a coding task directly to an OpenAI-compatible API with tool-calling.
    
    No agent wrapper. No conversation history. No skills.
    Just: system prompt + task + write tool → model writes files.
    """
    result = DirectDispatchResult(success=False, ticket_id=ticket_id)
    
    api_url = _get_api_url(config) if config else os.environ.get("BUMBLEBEE_API_BASE_URL", "https://api.openai.com/v1")
    model_id = model or (config.forge_model if config else "")
    
    if not model_id:
        result.error = "No model specified"
        return result

    # Build minimal system prompt
    system = (
        "You are a code generator. You receive a task and write files using the write_file tool.\n"
        "RULES:\n"
        "- ALWAYS use the write_file tool to create files. NEVER just describe what to write.\n"
        "- Write complete, production-ready code. No placeholders, no TODOs.\n"
        "- Use the EXACT file paths provided. Do not change them.\n"
        "- After writing all files, respond with 'Done.'\n"
    )

    # Build task message
    parts = [f"Write the following file(s):\n"]
    for f in files_to_write:
        parts.append(f"- `{f}`")
    parts.append(f"\n**Task:** {objective}")

    if architecture_rules:
        parts.append("\n**Rules to follow:**")
        for rule in architecture_rules:
            parts.append(f"- {rule}")

    if interaction_spec:
        parts.append(f"\n**Expected behavior:** {interaction_spec}")

    # Include context files so the model knows what it's integrating with
    if context_files:
        parts.append("\n**Existing code you must integrate with:**")
        for ctx_path, ctx_content in context_files.items():
            parts.append(f"\n`{ctx_path}`:\n```\n{ctx_content}\n```")

    parts.append("\nUse the write_file tool now. Write ALL files listed above.")
    task_message = "\n".join(parts)

    # API call
    payload = json.dumps({
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": task_message},
        ],
        "tools": [WRITE_TOOL],
        "tool_choice": "required",
        "temperature": 0.2,
        "max_tokens": 8192,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode("utf-8")

    api_key = _get_api_key(config) if config else os.environ.get('BUMBLEBEE_API_KEY', os.environ.get('OPENAI_API_KEY', ''))
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        f"{api_url}/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )

    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        result.error = f"API HTTP {e.code}: {body}"
        result.duration_seconds = time.time() - started
        log.error(f"Direct dispatch {ticket_id}: HTTP {e.code} from {api_url}: {body}")
        return result
    except urllib.error.URLError as e:
        result.error = f"API unreachable: {e}"
        result.duration_seconds = time.time() - started
        return result
    except Exception as e:
        result.error = f"API call failed: {e}"
        result.duration_seconds = time.time() - started
        return result

    result.duration_seconds = time.time() - started

    # Process response
    message = data.get("choices", [{}])[0].get("message", {})
    tool_calls = message.get("tool_calls", [])
    result.model_response = message.get("content", "") or ""

    if not tool_calls:
        # Model narrated instead of calling tools — this is the failure mode
        result.error = f"Zero tool calls. Model responded with text: {result.model_response[:200]}"
        log.warning(f"Direct dispatch {ticket_id}: zero tool calls, model narrated")
        return result

    # Execute tool calls — write files
    for tc in tool_calls:
        fn = tc.get("function", {})
        if fn.get("name") != "write_file":
            continue

        try:
            args = json.loads(fn.get("arguments", "{}"))
        except json.JSONDecodeError:
            continue

        file_path = args.get("path", "")
        file_content = args.get("content", "")

        # Fix double-escaped content from some models.
        # Detect: content has literal backslash-n but no real newlines.
        if "\n" not in file_content and "\\n" in file_content:
            import re
            file_content = (file_content
                .replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace('\\"', '"'))
            # Fix unicode escapes like \uXXXX
            file_content = re.sub(
                r'\\u([0-9a-fA-F]{4})',
                lambda m: chr(int(m.group(1), 16)),
                file_content
            )

        if not file_path or not file_content:
            continue

        # ALLOWLIST ENFORCEMENT: only write files listed in the ticket spec
        resolved = str(Path(file_path).resolve())
        if resolved not in {str(Path(f).resolve()) for f in files_to_write}:
            allowed = [str(Path(f).resolve()) for f in files_to_write]
            log.warning(f"Direct dispatch BLOCKED out-of-spec write: {file_path!r} -> {resolved!r}")
            log.warning(f"  Allowed: {allowed}")
            continue

        try:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(file_content, encoding="utf-8")
            strip_bom(p)  # clean up any BOM
            result.files_written.append(str(p))
            result.tool_calls += 1
            log.info(f"Direct dispatch wrote: {p.name} ({len(file_content)} chars)")
        except Exception as e:
            log.error(f"Failed to write {file_path}: {e}")

    # Check if all required files were written
    written_set = {str(Path(f).resolve()) for f in result.files_written}
    expected_set = {str(Path(f).resolve()) for f in files_to_write}
    missing = expected_set - written_set

    if missing:
        result.error = f"Missing files: {[str(Path(m).name) for m in missing]}"
    else:
        result.success = True

    return result
