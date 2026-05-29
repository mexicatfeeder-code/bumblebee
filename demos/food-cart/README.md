# Food Cart Demo

End-to-end demo: PRD → AI ticket decomposition → local AI builds the app → cloud AI wires it together → working app.

## Prerequisites

- **Python 3.11+** with `fastapi`, `uvicorn`, `httpx` (`pip install fastapi uvicorn httpx`)
- **Node.js 18+** with `npm`
- **Lemonade** running with `Qwen3.6-35B-A3B-GGUF` loaded (local coding model)
- **OpenAI API key** at `~/.bumblebee/cloud-api-key.txt` (for decompose + integration steps)

## Quick Start

### 1. Start the dashboard
```bash
cd bumblebee/dashboard/ui && npm install && npm run build
cd bumblebee/dashboard
export DASHBOARD_CONFIG=dashboard.config.json
python -m uvicorn api.main:app --host 127.0.0.1 --port 8765
```

### 2. Open the dashboard
Go to `http://localhost:8765`. Click the food-cart project.

### 3. Run the pipeline
Click **Decompose** → tickets stream in → auto-commits → Forge starts building → Integration wires it → done.

### 4. Launch the app
```bash
cd demos/food-cart/output/backend
python seed.py
python -m uvicorn main:app --host 127.0.0.1 --port 8080

# In another terminal:
cd demos/food-cart/output/frontend
npm install
npm install react-router-dom tailwindcss@3.4.14 autoprefixer postcss
npx vite --port 4177 --host 127.0.0.1
```

Open `http://localhost:4177` — food cart ordering app.

## What happens under the hood

| Step | Model | Cost | Time |
|------|-------|------|------|
| Decompose PRD → tickets | GPT-5.5 (cloud) | ~$3 | ~4 min |
| Build tickets → code | Qwen3.6-35B-A3B (local) | $0 | ~20 min |
| Integration wiring | GPT-4.1-mini (cloud) | ~$0.10 | ~90s |
| **Total** | | **~$3** | **~25 min** |

## Files

- `prd.md` — the product requirements document
- `qa-summary.md` — technical decisions from Q&A phase
- `output/` — generated app (frontend + backend)
- `tickets.db` — Bumblebee ticket database
