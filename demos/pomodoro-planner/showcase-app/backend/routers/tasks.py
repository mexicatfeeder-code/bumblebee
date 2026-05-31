import uuid
from fastapi import APIRouter, HTTPException, Response
from database import get_db, row_to_task
from schemas import TaskCreate, TaskUpdate, TaskOrderItem

router = APIRouter(prefix='/api/tasks', tags=['tasks'])

@router.get('')
def list_tasks() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM tasks ORDER BY sort_order ASC, created_at ASC').fetchall()
        return [row_to_task(row) for row in rows]

@router.post('', status_code=201)
def create_task(payload: TaskCreate) -> dict:
    task_id = str(uuid.uuid4())
    with get_db() as conn:
        row = conn.execute('SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM tasks').fetchone()
        sort_order = int(row['next_order'])
        conn.execute(
            '''INSERT INTO tasks (id, title, description, estimated_pomodoros, completed, sort_order, category)
               VALUES (?, ?, ?, ?, 0, ?, ?)''',
            (task_id, payload.title.strip(), payload.description, payload.estimated_pomodoros, sort_order, payload.category),
        )
        conn.commit()
        created = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        return row_to_task(created)

@router.patch('/{task_id}')
def update_task(task_id: str, payload: TaskUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail='No task fields supplied')
    allowed = ['title', 'description', 'estimated_pomodoros', 'completed', 'sort_order', 'category']
    assignments = []
    values = []
    for key in allowed:
        if key in updates:
            assignments.append(f'{key} = ?')
            value = updates[key]
            values.append(int(value) if key == 'completed' else value)
    values.append(task_id)
    with get_db() as conn:
        found = conn.execute('SELECT id FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not found:
            raise HTTPException(status_code=404, detail='Task not found')
        conn.execute(f'UPDATE tasks SET {", ".join(assignments)} WHERE id = ?', values)
        conn.commit()
        row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        return row_to_task(row)

@router.post('/reorder')
def reorder_tasks(items: list[TaskOrderItem]) -> list[dict]:
    with get_db() as conn:
        for item in items:
            if item.estimated_pomodoros is None:
                conn.execute('UPDATE tasks SET sort_order = ? WHERE id = ?', (item.sort_order, item.id))
            else:
                conn.execute(
                    'UPDATE tasks SET sort_order = ?, estimated_pomodoros = ? WHERE id = ?',
                    (item.sort_order, item.estimated_pomodoros, item.id),
                )
        conn.commit()
        rows = conn.execute('SELECT * FROM tasks ORDER BY sort_order ASC, created_at ASC').fetchall()
        return [row_to_task(row) for row in rows]

@router.delete('/{task_id}', status_code=204)
def delete_task(task_id: str) -> Response:
    with get_db() as conn:
        cur = conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail='Task not found')
    return Response(status_code=204)
