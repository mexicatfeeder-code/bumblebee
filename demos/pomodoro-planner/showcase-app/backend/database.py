import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get('POMODORO_DB_PATH', str(BASE_DIR / 'pomodoro.db'))

SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  estimated_pomodoros INTEGER NOT NULL DEFAULT 1,
  completed INTEGER NOT NULL DEFAULT 0,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  category TEXT
);
CREATE TABLE IF NOT EXISTS pomodoro_sessions (
  id TEXT PRIMARY KEY,
  task_id TEXT,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ended_at TEXT,
  duration_seconds INTEGER NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('focus','short_break','long_break')),
  completed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS chat_history (
  id TEXT PRIMARY KEY,
  role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
  content TEXT NOT NULL,
  timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
'''

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db() -> None:
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()

def row_to_task(row: sqlite3.Row) -> dict:
    return {
        'id': row['id'],
        'title': row['title'],
        'description': row['description'],
        'estimated_pomodoros': int(row['estimated_pomodoros']),
        'completed': bool(row['completed']),
        'sort_order': int(row['sort_order']),
        'created_at': row['created_at'],
        'category': row['category'],
    }

def row_to_session(row: sqlite3.Row) -> dict:
    return {
        'id': row['id'],
        'task_id': row['task_id'],
        'started_at': row['started_at'],
        'ended_at': row['ended_at'],
        'duration_seconds': int(row['duration_seconds']),
        'type': row['type'],
        'completed': bool(row['completed']),
    }

def row_to_chat(row: sqlite3.Row) -> dict:
    return {
        'id': row['id'],
        'role': row['role'],
        'content': row['content'],
        'timestamp': row['timestamp'],
    }
