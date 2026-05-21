"""
Run the Bumblebee executor for the react-counter example.

Usage:
  1. Set BUMBLEBEE_API_KEY (or OPENAI_API_KEY) env var
  2. python seed_tickets.py     # create tickets
  3. python run_executor.py     # run the loop
"""
import logging
import os
import sqlite3
import sys

# Add repo root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine.config import load_config
from engine.event_log import EventLog, init_db
from engine.executor import Executor
from engine.qa import static_check
from engine.state_machine import StateMachine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)

config = load_config(os.path.join(os.path.dirname(__file__), "project-config.json"))
conn = sqlite3.connect(str(config.db_path))
conn.row_factory = sqlite3.Row
init_db(conn)

sm = StateMachine()
ev = EventLog(conn)


def qa_fn(ticket_id, cfg):
    req = conn.execute(
        "SELECT required_output_files_json FROM ticket_requirements WHERE ticket_id=?",
        (ticket_id,),
    ).fetchone()
    if not req:
        return False, "no requirements found"
    r = static_check(ticket_id, dict(req), cfg)
    return r.passed, r.note


ex = Executor(config, sm, conn, ev, qa_fn=qa_fn)
results = ex.run_loop(max_cycles=50)

# Summary
print("\n=== Final Status ===")
for row in conn.execute("SELECT status, count(*) as n FROM tickets GROUP BY status ORDER BY status"):
    print(f"  {row['status']}: {row['n']}")
