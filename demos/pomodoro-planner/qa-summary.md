# Technical Summary -- Pomodoro Task Planner

## Project Overview
A three-panel productivity web app combining a task list, an animated liquid-fill pomodoro timer, and an AI chat panel powered by a local LLM. The AI analyzes tasks and suggests an optimal work schedule, then coaches the user through the day. Runs entirely locally with no cloud dependencies.

## Tech Stack
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS (vanilla React, no component library)
- **Backend:** Python FastAPI + SQLite
- **LLM:** Lemonade (local) -- auto-detect loaded model via `/v1/models`
- **Streaming:** Server-Sent Events (SSE) for LLM response streaming
- **Timer Animation:** Pure SVG + CSS (2-3 layered sine waves, no canvas/WebGL)
- **Port:** 4200 (backend serves API + built frontend)

## Architecture Decisions
- **Single-port deployment** -- FastAPI serves the built React frontend alongside the API
- **SQLite** -- task and session persistence, no external DB needed
- **LocalStorage** -- chat history and timer state persist across refresh
- **SSE streaming** -- backend proxies Lemonade's streaming chat response to frontend
- **Auto-detect model** -- queries `/v1/models` on startup, uses first available model
- **JSON structured output** -- planning prompt asks LLM for JSON with task ordering + pomodoro estimates

## Scope (v1)
- Three-panel layout: task list (left ~25%), timer (center ~40%), chat (right ~35%)
- Task CRUD with AI-driven reordering and manual drag reorder
- Liquid fill timer with multi-layer wave animation and color gradient (blue -> amber -> red)
- Pomodoro/break cycle: 25/5/15 defaults, auto-start breaks, manual start next pomodoro
- LLM schedule planning with streaming responses
- Session stats: pomodoros completed, focus time, streak
- Sound notifications with mute toggle (default muted)
- LocalStorage persistence for chat history and timer state

## Deferred to v2
- Mobile-responsive layout
- Dark mode
- Keyboard shortcuts
- Calendar integration
- Multi-day planning
- User accounts
- Cloud LLM fallback

## Error Handling
- Lemonade offline: chat panel shows "AI offline -- start Lemonade to enable planning"
- LLM returns invalid JSON: fall back to displaying raw response, skip auto-reorder
- Task API errors: show non-blocking toast with retry
- Timer state loss: recover from localStorage on refresh

## Open Questions
- None -- all implementation decisions resolved during Q&A
