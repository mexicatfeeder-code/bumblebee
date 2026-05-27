# Bumblebee — Conference Demo Roadmap

**Goal:** Standalone demo at conference week of 2026-06-01. Fresh Windows laptop → install → live PRD-to-working-app demo.

**Last updated:** 2026-05-26

---

## Completed

### Phase 0: AI Config UI + Lemonade Detection ✅
- AI configuration panel in dashboard (model dropdowns, API fields)
- Lemonade auto-detection (probes health endpoint, shows available models)
- Per-phase model config (Q&A, decomposition, coding)

### Phase 1: Q&A Chat Widget ✅
- Embedded chat in intake flow — LLM reads PRD and asks clarifying questions
- System prompt based on DECOMPOSITION-PROCESS.md checklist
- Finish Q&A → LLM produces decision summary → saved as qa-summary.md
- Chat transcript persisted per project

### Phase 2: Self-Service Decomposition ✅
- Dashboard calls decompose.py with real llm_fn
- **Streaming decomposition** — tickets appear live as LLM generates them (SSE)
- Live counter, pulsing LIVE badge, auto-scroll, phase grouping
- Approve/re-decompose buttons
- Commits plan to DB

### Phase 3: Executor Management ✅
- Start/stop coding from dashboard
- PID management, log capture
- Status indicators in dashboard

### Phase 4: Install + Service ✅
- `install.ps1` — one-command: checks Python/Node, clones repo, builds dashboard, registers service
- Auto-launches Lemonade if not running
- Loads **Forge model** (Qwen3.6-27B, 32k ctx) + **Sift model** (Gemma 4 E4B, 32k ctx)
- Creates config with demo project auto-discovery
- `uninstall.ps1` — clean removal (fixed PowerShell parse bug)
- `demo.ps1` — one-click demo launcher (resets DB, starts dashboard + both executors)

### Phase 5: Documentation ✅
- README rewrite — user journey focused (install, first project, how it works, troubleshooting)
- Sift research setup instructions (Brave API key)

### Phase 6: Sift Research Agent ✅ (new — 2026-05-26)
- `engine/research_executor.py` — polls research.db, calls Lemonade, writes reports
- **Brave Search API** integration — web search before LLM generation
- Dedicated model: **Gemma 4 E4B** (4.8GB) — runs parallel with Forge (no queueing)
- Dashboard UI: sidebar research list, new research intake, report viewer
- `scripts/init_research.py` — creates + seeds research DB
- Demo data: 2 pre-completed research reports bundled in food-cart demo

### Phase 7: Demo Data ✅
- `demos/food-cart/` — complete demo project (24 tickets, all qa_verified, 23 worker artifacts)
- Food Cart showcase app (FastAPI + seeded menu)
- Cost Comparison tab (cloud vs local savings)
- Research demo data (2 completed reports)
- Desktop shortcuts for dashboard + demo app

---

## In Progress

### End-to-End Testing on Chiron
- [ ] Fresh uninstall → reinstall with all new features
- [ ] Streaming decomposition with 32k context Qwen3.6-27B
- [ ] Dual-model parallel: Forge coding + Sift researching simultaneously
- [ ] Full demo flow: create project → Q&A → decompose (streaming) → approve → start coding → submit research → both agents active
- [ ] Verify demo.ps1 launches everything correctly

---

## Remaining (Nice-to-have for demo)

### Demo Polish
- [ ] Hide research sidebar section when no research DB configured (prevent 503 on systems without research)
- [ ] Demo script/talking points document for conference presenter
- [ ] Test with audience WiFi conditions (Brave search might be slow)
- [ ] Smaller/faster demo project option (fewer tickets for quicker live demo)

### Post-Conference
- [ ] Cross-platform install (Linux/Mac)
- [ ] Sift: SearXNG option for fully self-hosted search
- [ ] Multi-node execution (Forge on Chiron, Sift on Cashmere)
- [ ] Public repo (currently private)

---

## Architecture Summary

```
                    ┌──────────────────────┐
                    │   Dashboard (SvelteKit + FastAPI)   │
                    │   http://localhost:8765             │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │  Forge Agent  │  │  Sift Agent  │  │  Decomposer  │
     │  (coding)     │  │  (research)  │  │  (planning)  │
     └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
            │                 │                  │
            ▼                 ▼                  ▼
     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │ Qwen3.6-27B  │  │ Gemma 4 E4B  │  │ Qwen3.6-27B  │
     │  (18.5 GB)   │  │  (4.8 GB)    │  │  (shared)    │
     └──────────────┘  └──────────────┘  └──────────────┘
            └──────────────┬───────────────────┘
                           ▼
                    ┌──────────────┐
                    │  Lemonade    │
                    │  (2 LLMs)   │
                    │  :13305     │
                    └──────────────┘
```

**VRAM budget:** ~23 GB of 96 GB (Strix Halo unified memory)
