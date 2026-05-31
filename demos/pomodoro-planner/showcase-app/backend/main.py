from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from database import init_db
from routers import chat, sessions, tasks

init_db()

app = FastAPI(title='Pomodoro Task Planner', redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(tasks.router)
app.include_router(sessions.router)
app.include_router(chat.router)

@app.get('/api/health')
def health() -> dict:
    return {'status': 'ok'}

# --- Serve built frontend ---
_frontend = Path(__file__).resolve().parent.parent / 'frontend'
if _frontend.exists():
    _assets = _frontend / 'assets'
    if _assets.exists():
        app.mount('/assets', StaticFiles(directory=str(_assets)), name='frontend-assets')

    @app.get('/{full_path:path}')
    async def serve_frontend(full_path: str):
        if full_path.startswith('api/'):
            return
        file = _frontend / full_path
        if file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_frontend / 'index.html'))
