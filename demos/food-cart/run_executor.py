"""Run the Bumblebee executor for the Food Cart app."""
import sys, os
# Add bumblebee parent dir to path so 'bumblebee.engine' is importable
_this_dir = os.path.dirname(os.path.abspath(__file__))
_bumblebee_root = os.path.normpath(os.path.join(_this_dir, '..', '..'))
sys.path.insert(0, os.path.dirname(_bumblebee_root))

from bumblebee.engine.executor import Executor
from bumblebee.engine.state_machine import StateMachine
from bumblebee.engine.event_log import EventLog
from bumblebee.engine.config import load_config, ProjectConfig
from bumblebee.engine.qa import static_check
import sqlite3, logging, json, time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

config = load_config(os.path.join(os.path.dirname(__file__), 'project-config.json'))
conn = sqlite3.connect(str(config.db_path))
conn.row_factory = sqlite3.Row
sm = StateMachine()
ev = EventLog(conn)

def qa_fn(ticket_id: str, cfg: ProjectConfig) -> tuple[bool, str]:
    req_row = conn.execute(
        "SELECT required_output_files_json FROM ticket_requirements WHERE ticket_id=?",
        (ticket_id,),
    ).fetchone()
    if not req_row:
        return False, "no requirements"
    reqs = dict(req_row)
    r = static_check(ticket_id, reqs, cfg)
    return r.passed, r.note

ex = Executor(config, sm, conn, ev, qa_fn=qa_fn)

# Pre-dispatch: git snapshot
import subprocess as _sp
_deliverable = str(config.deliverable_root)
_pending = conn.execute("SELECT id FROM tickets WHERE status='todo'").fetchall()
if _pending:
    _ids = ', '.join(r['id'] for r in _pending)
    _git = _sp.run(['git', '-C', _deliverable, 'add', '-A'], capture_output=True, text=True)
    if _git.returncode == 0:
        _sp.run(
            ['git', '-C', _deliverable, 'commit', '--allow-empty', '-m', f'pre-forge: {_ids}'],
            capture_output=True, text=True
        )
        log.info(f'Git snapshot: {_ids}')
    else:
        log.warning('Git snapshot failed — continuing without rollback safety')

log.info("Starting Food Cart executor loop...")
start = time.time()
results = ex.run_loop(max_cycles=150)
elapsed = time.time() - start

print()
log.info('=== EXECUTOR COMPLETE ===')
log.info(f'Cycles: {len(results)}, Time: {elapsed:.1f}s')
total_dispatched = sum(r.tickets_dispatched for r in results)
total_verified = sum(r.tickets_verified for r in results)
total_errors = sum(len(r.errors) for r in results)
log.info(f'Dispatched: {total_dispatched}, Verified: {total_verified}, Errors: {total_errors}')

for row in conn.execute('SELECT status, count(*) as n FROM tickets GROUP BY status ORDER BY status'):
    log.info(f'  {row["status"]}: {row["n"]}')

log.info("File check:")
for row in conn.execute('SELECT ticket_id, required_output_files_json FROM ticket_requirements ORDER BY ticket_id'):
    files = json.loads(row['required_output_files_json'])
    for f in files:
        p = config.deliverable_root / f
        exists = p.exists()
        size = p.stat().st_size if exists else 0
        mark = '✓' if exists else '✗'
        log.info(f'  {mark} {f}' + (f' ({size}b)' if exists else ' MISSING'))

all_verified = all(r2['status'] == 'qa_verified' for r2 in conn.execute('SELECT status FROM tickets'))
if all_verified:
    log.info('🎉 ALL TICKETS VERIFIED')
else:
    log.info('⚠ Some tickets not yet verified — check status above')
