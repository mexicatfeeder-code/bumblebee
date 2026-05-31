# PRD: Pomodoro Task Planner

**Version:** 1.0
**Date:** 2026-05-31
**Status:** Draft

---

## Overview

A personal productivity web app that combines a task list with an AI-powered pomodoro timer. You dump in your tasks for the day, a local LLM analyzes them and suggests an optimal schedule (order, pomodoro count per task, break placement), then you work through the plan with a visually rich animated timer. As you complete or skip tasks, the AI reshuffles the remaining schedule and explains its reasoning.

Three-panel layout: task list (left), animated timer (center), LLM chat (right).

---

## Target User

**Engineers and knowledge workers** who use the pomodoro technique but want something smarter than a dumb countdown. The AI adds value by reasoning about task ordering, estimating effort, and adapting the plan as the day unfolds.

---

## Core Concept

### The Timer — Liquid Fill Animation

The centerpiece is a large rounded container with an animated liquid fill effect:
- SVG/CSS wave surface that ripples gently as it fills
- Liquid rises from bottom to top as the pomodoro progresses (empty at start, full at completion)
- Color shifts as it fills: cool blue at start, warm amber midway, deep red near the end
- The wave motion is subtle and continuous — gives the UI a sense of life even when idle
- Time digits overlaid on top of the liquid with contrast effect at the water line
- Pomodoro / Short Break / Long Break modes with different fill colors

### The AI — Schedule Planner

The local LLM (via Lemonade) acts as a productivity coach:
- Reads the full task list with any notes/context
- Suggests an ordering based on cognitive load, dependencies, and time of day
- Estimates pomodoro count per task (1-4 pomodoros each)
- Places short breaks (5 min) between pomodoros and long breaks (15 min) every 4th cycle
- Explains its reasoning conversationally: "I put the code review first because it's a quick win to build momentum, then the DB migration because it needs deep focus while you're fresh"
- When you complete early, skip, or add tasks mid-day — reshuffles and explains the new plan

---

## Core User Flows

### Planning Flow
1. Open app — see empty task list on left, timer in center, chat on right
2. Add tasks: type task name, optional description/estimate, press Enter or click Add
3. Click "Plan My Day" in the chat panel
4. LLM streams a response: suggested order, pomodoro estimates, reasoning
5. Task list reorders to match the AI's suggestion, each task shows estimated pomodoros
6. Click "Start" on the timer to begin the first task

### Working Flow
1. Timer starts — liquid begins filling the container, current task name shown above timer
2. Wave animation ripples continuously, color shifts as time passes
3. When pomodoro completes (liquid full): chime sound, transition to break
4. Break timer runs (different color — cool green/blue)
5. After break: next task begins automatically, or pause for manual advance
6. Task list updates: completed tasks get subtle strikethrough + fade

### Adjustment Flow
1. Mid-session: "I finished the code review early" in chat
2. LLM responds: "Nice! Moving the API docs up since you have momentum. Pushing the meeting prep to after lunch."
3. Task list reorders, timer loads next task
4. Or: skip current task, add a new urgent task, ask to extend a pomodoro

---

## Pages & Layout

### Single Page — Three Panel Layout

| Panel | Position | Width | Content |
|---|---|---|---|
| Task List | Left | ~25% | Add/edit/delete tasks, drag reorder, completion checkboxes, pomodoro estimates per task |
| Timer | Center | ~40% | Liquid fill animation, time display, current task name, Start/Pause/Skip controls, session stats |
| LLM Chat | Right | ~35% | Streaming chat with local model, "Plan My Day" button, conversation history |

### Task List Panel (Left)
- Input field at top: "Add a task..." with Enter to submit
- Each task shows: checkbox, task name, estimated pomodoros (pill badge), optional description
- Completed tasks: strikethrough + opacity fade, stay in list (don't remove)
- Drag handle for manual reorder
- Delete button (X) on hover
- Category/tag support: small colored dot or label (optional, user-assigned)

### Timer Panel (Center)
- **Current task name** displayed above the timer
- **Liquid fill container**: large rounded rectangle (~300x400px), SVG wave animation inside
  - Wave: sine curve with gentle amplitude oscillation, 2-3 layered waves for depth
  - Fill level: 0% at pomodoro start, 100% at completion
  - Color gradient: `hsl(210, 80%, 55%)` (blue) → `hsl(35, 90%, 55%)` (amber) → `hsl(0, 75%, 50%)` (red)
  - Break mode: `hsl(150, 60%, 50%)` (green) for short, `hsl(200, 70%, 50%)` (teal) for long
- **Time display**: large digits centered on the container, white text with subtle shadow for readability over the liquid
- **Mode tabs**: Pomodoro (25 min) | Short Break (5 min) | Long Break (15 min)
- **Controls**: Start / Pause / Skip buttons below the timer
- **Session stats bar**: pomodoros completed, total focus time, current streak — small text below controls

### LLM Chat Panel (Right)
- Chat messages: user bubbles (right-aligned, colored) and AI bubbles (left-aligned, light gray)
- AI responses stream token-by-token (visible typing effect)
- "Plan My Day" prominent button at top when no plan exists
- Input field at bottom: "Ask anything..." with Send button
- Suggested prompts as chips: "Plan my day", "I finished early", "Add a task", "Reshuffle"

---

## Data Model

### Tasks
- `id` (UUID), `title`, `description` (optional), `estimated_pomodoros` (int, 1-4), `completed` (bool), `sort_order` (int), `created_at`, `category` (optional string)

### Pomodoro Sessions
- `id`, `task_id`, `started_at`, `ended_at`, `duration_seconds`, `type` ('focus' | 'short_break' | 'long_break'), `completed` (bool)

### Chat History
- `id`, `role` ('user' | 'assistant'), `content`, `timestamp`

### Settings (in-memory, localStorage)
- `pomodoro_minutes` (default 25), `short_break_minutes` (default 5), `long_break_minutes` (default 15), `auto_start_breaks` (bool), `auto_start_pomodoros` (bool)

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite | Consistent with swarm; animation-friendly |
| Styling | Tailwind CSS + inline SVG | Tailwind for layout, SVG for liquid animation |
| Timer Animation | SVG + CSS animations | No canvas/WebGL needed — pure SVG path + CSS transitions |
| Backend | FastAPI (Python) | Simple API for LLM proxy + task persistence |
| Database | SQLite | Task list and session history |
| LLM | Lemonade (local) | Chat completions API for schedule planning |
| Real-time | Server-Sent Events (SSE) | Stream LLM responses to frontend |

---

## Phases

### Phase 1 — Foundation
Project scaffold, DB schema, shared types, base layout.

Tickets:
- P1-001: Project scaffold (Vite + React + TS + Tailwind, FastAPI backend, SQLite init)
- P1-002: Shared types (TypeScript interfaces + Pydantic schemas)
- P1-003: Three-panel layout shell (responsive, placeholder content in each panel)
- P1-004: Task CRUD API (POST/GET/PATCH/DELETE /api/tasks)

### Phase 2 — Task List & Timer
Core UI components — task management and the liquid fill timer.

Tickets:
- P2-001: Task list component — add/edit/delete/complete/reorder tasks
- P2-002: Timer state machine — pomodoro/break cycle logic, countdown, auto-transitions
- P2-003: Liquid fill SVG component — wave animation, color interpolation, fill level
- P2-004: Timer panel integration — wire timer state to liquid fill, controls, current task display
- P2-005: Session stats — pomodoro counter, focus time, streak tracking

### Phase 3 — LLM Chat & Planning
AI-powered scheduling via local LLM.

Tickets:
- P3-001: LLM proxy API — POST /api/chat with SSE streaming from Lemonade
- P3-002: Chat panel UI — message list, streaming display, input field
- P3-003: Planning prompt — system prompt for task scheduling, JSON output format for reordering
- P3-004: Schedule application — parse LLM response, reorder task list, update pomodoro estimates
- P3-005: Suggested actions — "Plan My Day", "Reshuffle", "I finished early" chip buttons

### Phase 4 — Polish & Persistence
Local storage, settings, visual refinement.

Tickets:
- P4-001: LocalStorage persistence — save tasks, chat history, timer state across refresh
- P4-002: Settings panel — pomodoro/break durations, auto-start toggles
- P4-003: Sound notifications — chime on pomodoro complete, gentle tone on break end
- P4-004: Visual polish — transitions, hover states, empty states, loading states

---

## Scope Boundaries (MVP)

**In scope:**
- Three-panel layout: task list, liquid fill timer, LLM chat
- Task CRUD with manual and AI-driven reordering
- Animated liquid fill timer with wave effect and color transitions
- LLM-powered daily schedule planning via local Lemonade
- Streaming chat responses
- Pomodoro/break cycle management
- Session statistics (pomodoros completed, focus time)
- LocalStorage persistence

**Explicitly out of scope:**
- User accounts / authentication
- Multi-day planning or calendar integration
- Mobile-specific layout (desktop-first for this demo)
- Cloud LLM fallback
- Team/shared task lists
- Integrations (Jira, GitHub, etc.)
- Keyboard shortcuts (v2)

---

## Demo Story

> "This is a smart pomodoro planner — you add your tasks, the local AI figures out the best order to tackle them, then coaches you through the day with an animated timer. The AI runs entirely on your machine via Lemonade. No cloud. No subscription. $0.00."

The liquid fill animation is the visual hook — it catches the eye from across the room. When someone walks up, the AI is visibly streaming its reasoning about task scheduling. That's the "oh, that's cool" moment.

---

## Design Direction

- **Clean, minimal** — inspired by Notion's aesthetic. Lots of whitespace, subtle borders, rounded corners
- **The timer is the hero** — large, centered, visually dominant with the liquid animation
- **Color palette**: neutral grays for UI chrome, the timer provides all the color (blue → amber → red gradient)
- **Typography**: system fonts, clear hierarchy. Task names are readable, timer digits are large
- **Dark mode**: Not in v1, but the color scheme should work against a dark background later

---

## Decisions

| Question | Decision | Notes |
|---|---|---|
| Timer style | Liquid fill with wave animation | SVG sine wave + clip path, no canvas needed |
| LLM model | Whatever's loaded in Lemonade | Use `/v1/models` to detect, chat completions for interaction |
| Persistence | LocalStorage + SQLite | Tasks in SQLite via API, timer state in localStorage |
| Timer durations | 25/5/15 default | Configurable in settings |
| Sound | Web Audio API | Simple sine tone chime, no external audio files needed |
| Layout | Fixed three-panel | Desktop-optimized, not responsive for mobile in v1 |
| Task estimates | 1-4 pomodoros | LLM suggests, user can override |
