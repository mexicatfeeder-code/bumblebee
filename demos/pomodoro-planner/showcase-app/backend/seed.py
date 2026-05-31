import uuid
from database import get_db, init_db

DEMO_TASKS = [
    ('Review pull requests', 'Quick win to build momentum.', 1, 'Code'),
    ('Design database migration', 'Requires deep focus and careful validation.', 3, 'Backend'),
    ('Write API documentation', 'Document endpoints and examples.', 2, 'Docs'),
]

def seed() -> None:
    init_db()
    with get_db() as conn:
        conn.execute('DELETE FROM pomodoro_sessions')
        conn.execute('DELETE FROM chat_history')
        conn.execute('DELETE FROM tasks')
        for index, (title, description, estimate, category) in enumerate(DEMO_TASKS):
            conn.execute(
                '''INSERT INTO tasks (id, title, description, estimated_pomodoros, completed, sort_order, category)
                   VALUES (?, ?, ?, ?, 0, ?, ?)''',
                (str(uuid.uuid4()), title, description, estimate, index, category),
            )
        conn.commit()

if __name__ == '__main__':
    seed()
    print('Seeded pomodoro planner database.')
