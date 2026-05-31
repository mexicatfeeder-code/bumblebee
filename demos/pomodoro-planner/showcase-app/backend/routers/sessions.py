import uuid
from fastapi import APIRouter, HTTPException
from database import get_db, row_to_session
from schemas import PomodoroSessionCreate, PomodoroSessionUpdate

router = APIRouter(prefix='/api/sessions', tags=['sessions'])

@router.get('')
def list_sessions() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM pomodoro_sessions ORDER BY started_at DESC').fetchall()
        return [row_to_session(row) for row in rows]

@router.post('', status_code=201)
def create_session(payload: PomodoroSessionCreate) -> dict:
    session_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            '''INSERT INTO pomodoro_sessions (id, task_id, duration_seconds, type, completed)
               VALUES (?, ?, ?, ?, ?)''',
            (session_id, payload.task_id, payload.duration_seconds, payload.type, int(payload.completed)),
        )
        conn.commit()
        row = conn.execute('SELECT * FROM pomodoro_sessions WHERE id = ?', (session_id,)).fetchone()
        return row_to_session(row)

@router.patch('/{session_id}')
def update_session(session_id: str, payload: PomodoroSessionUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail='No session fields supplied')
    assignments = []
    values = []
    if 'ended_at' in updates:
        assignments.append('ended_at = ?')
        values.append(updates['ended_at'])
    if 'completed' in updates:
        assignments.append('completed = ?')
        values.append(int(updates['completed']))
    values.append(session_id)
    with get_db() as conn:
        found = conn.execute('SELECT id FROM pomodoro_sessions WHERE id = ?', (session_id,)).fetchone()
        if not found:
            raise HTTPException(status_code=404, detail='Session not found')
        conn.execute(f'UPDATE pomodoro_sessions SET {", ".join(assignments)} WHERE id = ?', values)
        conn.commit()
        row = conn.execute('SELECT * FROM pomodoro_sessions WHERE id = ?', (session_id,)).fetchone()
        return row_to_session(row)
