"""
Q&A Chat — LLM-powered PRD refinement chat.

The local model reads the PRD and asks clarifying questions to fill gaps.
Conversation is stored per-project as JSON. At the end, the LLM produces
a decision summary that feeds into decomposition.

Endpoints:
  GET  /api/projects/{slug}/qa/history    — get conversation history
  POST /api/projects/{slug}/qa/message    — send a message, get LLM response
  POST /api/projects/{slug}/qa/finish     — generate summary, advance status
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.config_loader import get_config
from ..services.registry import get_project, update_project

log = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["qa"])

DEFAULT_LEMONADE_URL = "http://[::1]:13305"


# ---------------------------------------------------------------------------
# System prompt — based on DECOMPOSITION-PROCESS.md Q&A checklist
# ---------------------------------------------------------------------------

QA_SYSTEM_PROMPT = """You are a software architect helping a user refine their project requirements document (PRD).

Your job is to read the PRD and ask clarifying questions to fill in gaps. The PRD describes WHAT the user wants to build — you need to surface the HOW and WITH WHAT decisions.

Ask questions in these categories, but only ask what's relevant to THIS project. Skip anything the PRD already answers clearly.

**Runtime & Infrastructure**
- What AI model/API should the project use? (OpenAI, local model, specific provider)
- What port should the app run on? Any port conflicts?
- Where should output files live?
- Any external services needed? (databases, APIs, hardware)
- Auth or access restrictions?

**Tech Stack**
- Framework/language preference, or should you decide?
- Any existing code or libraries to integrate with?
- Any packages to avoid?
- Build system preference?

**Design & UX**
- Visual style: exact match to a reference, inspired by, or general direction?
- Target browsers or devices?
- Accessibility requirements?
- Expected number of users?

**Scope & Priorities**
- What's the simplest version that counts as done?
- Any features to defer to v2?
- How should errors be presented to users?

Guidelines:
- Ask 2-4 questions at a time, not all at once. Wait for answers before asking more.
- Be conversational and concise. No essays.
- When you have enough information, say so and offer to generate the summary.
- Focus on decisions that affect implementation — skip philosophical questions.
- If the PRD is very clear, acknowledge that and ask fewer questions."""

SUMMARY_PROMPT = """Based on the conversation so far, produce a concise technical summary document that captures all decisions made during this Q&A session.

Format it as a markdown document with these sections:
- **Project Overview** — one paragraph summary
- **Tech Stack** — languages, frameworks, dependencies
- **Architecture Decisions** — key technical choices and rationale
- **Scope** — what's in v1, what's deferred
- **Error Handling** — how errors should be presented
- **Open Questions** — anything still unresolved

Keep it factual and actionable. This document will be used to guide the ticket decomposition phase."""


# ---------------------------------------------------------------------------
# Conversation storage
# ---------------------------------------------------------------------------

def _qa_dir(slug: str) -> Path:
    """Get the Q&A directory for a project."""
    dashboard_root = Path(__file__).resolve().parent.parent.parent  # dashboard/
    # Check demos directory first (bundled demo projects)
    demos_dir = dashboard_root.parent / "demos" / slug
    if demos_dir.exists():
        return demos_dir
    # Then check workspace projects
    config = get_config()
    ws = config.get("workspaceRoot", "")
    if ws:
        return Path(ws) / "bumblebee" / "projects" / slug
    # Fallback: relative to dashboard
    return dashboard_root.parent / "projects" / slug


def _history_path(slug: str) -> Path:
    d = _qa_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    return d / "qa-chat.json"


def _load_history(slug: str) -> list[dict]:
    path = _history_path(slug)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_history(slug: str, messages: list[dict]) -> None:
    path = _history_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(messages, indent=2, ensure_ascii=False), encoding="utf-8")


def _summary_path(slug: str) -> Path:
    return _qa_dir(slug) / "qa-summary.md"


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _resolve_qa_model(project: dict | None = None) -> tuple[str, str, str]:
    """
    Resolve the Q&A model endpoint.
    Returns (base_url, model_id, api_key).
    """
    config = get_config()
    ai = config.get("ai", {})

    source = ai.get("qa_model_source", "lemonade")
    model_id = ai.get("qa_model_id", "")

    # Project-level overrides
    if project:
        proj_ai = project.get("ai_config", {})
        if proj_ai.get("qa_model_source"):
            source = proj_ai["qa_model_source"]
        if proj_ai.get("qa_model_id"):
            model_id = proj_ai["qa_model_id"]

    if source == "lemonade":
        base_url = config.get("lemonadeUrl") or ai.get("lemonade_url", DEFAULT_LEMONADE_URL)
        # Ensure /v1 suffix for OpenAI-compatible endpoint
        if not base_url.rstrip('/').endswith('/v1'):
            base_url = base_url.rstrip('/') + '/v1'
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
        base_url = (
            ai.get("custom_api_base_url", "")
            or project.get("ai_config", {}).get("custom_api_base_url", "")
            if project else ai.get("custom_api_base_url", "")
        )
        api_key = ai.get("custom_api_key", "")
        if not base_url:
            base_url = "https://api.openai.com/v1"
        return base_url, model_id, api_key


async def _call_llm(
    base_url: str,
    model_id: str,
    api_key: str,
    messages: list[dict],
    timeout: float = 120.0,
) -> str:
    """Call an OpenAI-compatible chat completion endpoint."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            detail = resp.text[:500]
            log.error("LLM call failed (%d): %s", resp.status_code, detail)
            raise HTTPException(
                status_code=502,
                detail=f"AI model returned {resp.status_code}: {detail}",
            )
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise HTTPException(status_code=502, detail="AI model returned no choices")
        return choices[0].get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# Build context from PRD
# ---------------------------------------------------------------------------

def _get_prd_text(project: dict) -> str:
    """Read the PRD file for a project."""
    prd_path = project.get("prd_path")
    if not prd_path:
        return ""
    try:
        text = Path(prd_path).read_text(encoding="utf-8", errors="replace").strip()
        if len(text) > 12000:
            text = text[:12000] + "\n\n[...truncated at 12000 chars]"
        return text
    except Exception as e:
        log.warning("Could not read PRD at %s: %s", prd_path, e)
        return ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{slug}/qa/history")
def get_qa_history(slug: str):
    """Return the Q&A conversation history for a project."""
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    messages = _load_history(slug)
    summary_file = _summary_path(slug)
    return {
        "messages": messages,
        "has_summary": summary_file.exists(),
        "summary": summary_file.read_text(encoding="utf-8") if summary_file.exists() else None,
    }


class ChatMessageRequest(BaseModel):
    message: str


@router.post("/{slug}/qa/message")
async def send_qa_message(slug: str, body: ChatMessageRequest):
    """
    Send a user message and get the LLM's response.
    Initializes the conversation with PRD context on first message.
    """
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    history = _load_history(slug)
    base_url, model_id, api_key = _resolve_qa_model(project)

    if not model_id:
        raise HTTPException(
            status_code=400,
            detail="No Q&A model configured. Set a model in AI Configuration.",
        )

    # Build the PRD context for the system prompt
    prd_text = _get_prd_text(project)
    system_content = QA_SYSTEM_PROMPT
    if prd_text:
        system_content += f"\n\n---\n\nHere is the user's PRD:\n\n{prd_text}"
    else:
        system_content += "\n\n---\n\nNo PRD has been uploaded yet. Ask the user to describe what they want to build."

    # Add user message to history
    user_msg = {
        "role": "user",
        "content": body.message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    history.append(user_msg)

    # Build messages for LLM (system + conversation history without timestamps)
    llm_messages = [{"role": "system", "content": system_content}]
    for msg in history:
        llm_messages.append({"role": msg["role"], "content": msg["content"]})

    # Call LLM
    response_text = await _call_llm(base_url, model_id, api_key, llm_messages)

    # Add assistant response to history
    assistant_msg = {
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    history.append(assistant_msg)
    _save_history(slug, history)

    # Update project status if still in intake
    if project.get("status") == "intake":
        checklist = {**project.get("checklist", {}), "prd_uploaded": True}
        update_project(slug, {"status": "qa_pending", "checklist": checklist})

    return {
        "response": response_text,
        "message_count": len(history),
    }


@router.post("/{slug}/qa/finish")
async def finish_qa(slug: str):
    """
    Generate a summary of the Q&A session and advance the project status.
    """
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    history = _load_history(slug)
    if not history:
        raise HTTPException(status_code=400, detail="No Q&A conversation to summarize")

    base_url, model_id, api_key = _resolve_qa_model(project)

    if not model_id:
        raise HTTPException(
            status_code=400,
            detail="No Q&A model configured.",
        )

    # Build summary request
    prd_text = _get_prd_text(project)
    system_content = QA_SYSTEM_PROMPT
    if prd_text:
        system_content += f"\n\n---\n\nHere is the user's PRD:\n\n{prd_text}"

    llm_messages = [{"role": "system", "content": system_content}]
    for msg in history:
        llm_messages.append({"role": msg["role"], "content": msg["content"]})
    llm_messages.append({"role": "user", "content": SUMMARY_PROMPT})

    # Generate summary
    summary_text = await _call_llm(base_url, model_id, api_key, llm_messages)

    # Save summary
    summary_file = _summary_path(slug)
    summary_file.write_text(summary_text, encoding="utf-8")
    log.info("Q&A summary saved for project '%s' at %s", slug, summary_file)

    # Update project status
    checklist = {**project.get("checklist", {}), "qa_complete": True}
    update_project(slug, {"status": "qa_complete", "checklist": checklist})

    return {
        "summary": summary_text,
        "summary_path": str(summary_file),
    }
