"""
Example: Seed a simple React counter app with 3 tickets across 2 phases.

Run: python seed_tickets.py
Then: python run_executor.py
"""
import json
import sqlite3
import sys
import os

# Add repo root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine.event_log import init_db

conn = sqlite3.connect("tickets.db")
conn.row_factory = sqlite3.Row
init_db(conn)

tickets = [
    {
        "id": "CTR-001",
        "gate": 0,
        "owner": "frontend",
        "description": (
            "Create a Counter component in React 18 with TypeScript.\n\n"
            "Requirements:\n"
            "- Display a number (starting at 0)\n"
            "- Two buttons: '+' to increment and '-' to decrement\n"
            "- The count cannot go below 0\n"
            "- Use a CSS file for styling (not inline styles)\n"
            "- Use `export default function Counter()`\n"
            "- Use React.useState for state management\n\n"
            "Files to write:\n"
            "- src/components/Counter.tsx\n"
            "- src/components/Counter.css\n\n"
            "Only write the files listed above. Do not modify any other files."
        ),
        "files": ["src/components/Counter.tsx", "src/components/Counter.css"],
        "depends_on": [],
    },
    {
        "id": "CTR-002",
        "gate": 0,
        "owner": "frontend",
        "description": (
            "Create a Header component in React 18 with TypeScript.\n\n"
            "Requirements:\n"
            "- Display the text 'Counter App' in an h1 tag\n"
            "- Add a subtitle paragraph: 'A simple counter built by Bumblebee'\n"
            "- Use a CSS file for styling\n"
            "- Use `export default function Header()`\n\n"
            "Files to write:\n"
            "- src/components/Header.tsx\n"
            "- src/components/Header.css\n\n"
            "Only write the files listed above. Do not modify any other files."
        ),
        "files": ["src/components/Header.tsx", "src/components/Header.css"],
        "depends_on": [],
    },
    {
        "id": "CTR-003",
        "gate": 1,
        "owner": "frontend",
        "description": (
            "Create the main App component that combines Header and Counter.\n\n"
            "Requirements:\n"
            "- Import Header from './components/Header'\n"
            "- Import Counter from './components/Counter'\n"
            "- Render Header at the top, Counter below it\n"
            "- Wrap everything in a div with className 'app'\n"
            "- Use `export default function App()`\n"
            "- Add basic layout CSS (centered, max-width 600px)\n\n"
            "Files to write:\n"
            "- src/App.tsx\n"
            "- src/App.css\n\n"
            "Only write the files listed above. Do not modify any other files."
        ),
        "files": ["src/App.tsx", "src/App.css"],
        "depends_on": ["CTR-001", "CTR-002"],
    },
]

for t in tickets:
    conn.execute(
        "INSERT OR REPLACE INTO tickets (id, owner, gate, status, depends_on) VALUES (?, ?, ?, 'todo', ?)",
        (t["id"], t["owner"], t["gate"], json.dumps(t["depends_on"])),
    )
    conn.execute(
        "INSERT OR REPLACE INTO ticket_requirements (ticket_id, ticket_description, required_output_files_json) VALUES (?, ?, ?)",
        (t["id"], t["description"], json.dumps(t["files"])),
    )

conn.commit()
conn.close()
print(f"Seeded {len(tickets)} tickets into tickets.db")
print("  Gate 0: CTR-001 (Counter), CTR-002 (Header)")
print("  Gate 1: CTR-003 (App layout) — depends on CTR-001 + CTR-002")
