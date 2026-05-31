import json
import re
import uuid
from typing import Generator
import requests
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from database import get_db, row_to_chat
from schemas import ChatRequest

router = APIRouter(prefix='/api/chat', tags=['chat'])
LEMONADE_URL = 'http://[::1]:13305/v1'

SYSTEM_PROMPT = '''You are a productivity coach. Create a concise pomodoro plan.
Return conversational reasoning and include JSON between PLAN_JSON_START and PLAN_JSON_END.
JSON format: [{"task_id":"...","sort_order":0,"estimated_pomodoros":2}].'''

def save_message(role: str, content: str) -> None:
    with get_db() as conn:
        conn.execute(
            'INSERT INTO chat_history (id, role, content) VALUES (?, ?, ?)',
            (str(uuid.uuid4()), role, content),
        )
        conn.commit()

PREFERRED_MODEL = 'gemma-4-E4B-it-GGUF'

def get_model() -> str | None:
    try:
        res = requests.get(f'{LEMONADE_URL}/models', timeout=2)
        res.raise_for_status()
        data = res.json()
        models = data.get('data', [])
        if not models:
            return None
        # Prefer Gemma, fall back to whatever's loaded
        for m in models:
            if m.get('id', '').lower().startswith('gemma'):
                return m['id']
        return models[0].get('id')
    except Exception:
        return None

def heuristic_plan(payload: ChatRequest) -> tuple[str, list[dict]]:
    remaining = [task for task in payload.tasks if not task.completed]
    ordered = sorted(remaining, key=lambda t: (t.estimated_pomodoros, t.created_at))
    plan = []
    lines = ['AI offline or busy, so I created a local heuristic plan.']
    for index, task in enumerate(ordered):
        estimate = max(1, min(4, task.estimated_pomodoros or 1))
        plan.append({'task_id': task.id, 'sort_order': index, 'estimated_pomodoros': estimate})
        lines.append(f'{index + 1}. {task.title} — {estimate} pomodoro(s).')
    lines.append('I put shorter tasks first for momentum, then deeper work after you are warmed up.')
    return '\n'.join(lines), plan

def call_lemonade(payload: ChatRequest) -> tuple[str, list[dict]] | None:
    model = get_model()
    if not model:
        return None
    task_text = '\n'.join([f'- id={t.id} title={t.title} estimate={t.estimated_pomodoros} completed={t.completed}' for t in payload.tasks])
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': f'Tasks:\n{task_text}\nPlan the day.'}]
    try:
        res = requests.post(f'{LEMONADE_URL}/chat/completions', json={'model': model, 'messages': messages, 'temperature': 0.2}, timeout=30)
        res.raise_for_status()
        content = res.json()['choices'][0]['message']['content']
        match = re.search(r'PLAN_JSON_START\s*(.*?)\s*PLAN_JSON_END', content, re.S)
        plan = json.loads(match.group(1)) if match else []
        return content, plan
    except Exception:
        return None

def sse_event(payload: dict) -> str:
    return f'data: {json.dumps(payload)}\n\n'

def stream_response(payload: ChatRequest) -> Generator[str, None, None]:
    user_text = payload.messages[-1].content if payload.messages else 'Plan my day'
    save_message('user', user_text)
    result = call_lemonade(payload)
    if result is None:
        text, plan = heuristic_plan(payload)
    else:
        text, plan = result
    save_message('assistant', text)
    for word in text.split(' '):
        yield sse_event({'delta': word + ' ', 'done': False})
    yield sse_event({'delta': '', 'done': True, 'plan_json': plan})

@router.post('/stream')
def chat_stream(payload: ChatRequest) -> StreamingResponse:
    return StreamingResponse(stream_response(payload), media_type='text/event-stream')

@router.get('/history')
def chat_history() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM chat_history ORDER BY timestamp ASC').fetchall()
        return [row_to_chat(row) for row in rows]
