"""Reset all demo projects to clean state for conference demo.

Clears:
- tickets.db (re-seeds if seed_tickets.py exists, else deletes)
- artifacts/*.worker.json
- output/ deliverable files (preserves .gitignore)
- research/research.db + research/reports/

Usage:
  python reset_all_demos.py           # reset all demos
  python reset_all_demos.py food-cart  # reset one demo
"""
import os, sys, glob, shutil, sqlite3

DEMOS_DIR = os.path.dirname(os.path.abspath(__file__))


def find_demo_dirs(filter_name=None):
    """Find all demo project directories (those with project-config.json)."""
    dirs = []
    for entry in sorted(os.listdir(DEMOS_DIR)):
        full = os.path.join(DEMOS_DIR, entry)
        if not os.path.isdir(full):
            continue
        if not os.path.exists(os.path.join(full, 'project-config.json')):
            continue
        if filter_name and entry != filter_name:
            continue
        dirs.append((entry, full))
    return dirs


def reset_demo(name, project_dir):
    print(f"\n{'='*50}")
    print(f"  Resetting: {name}")
    print(f"{'='*50}")

    # 1. Clear tickets.db
    db_path = os.path.join(project_dir, 'tickets.db')
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"  Removed tickets.db")
    # Also remove WAL/SHM
    for ext in ('.db-wal', '.db-shm'):
        p = db_path + ext.replace('.db', '')
        if os.path.exists(p):
            os.remove(p)

    # 2. Clear artifacts
    artifacts_dir = os.path.join(project_dir, 'artifacts')
    if os.path.isdir(artifacts_dir):
        count = 0
        for f in glob.glob(os.path.join(artifacts_dir, '*.worker.json')):
            os.remove(f)
            count += 1
        print(f"  Cleared {count} artifact files")

    # 3. Clear output (deliverable root) but preserve .gitignore and dirs
    output_dir = os.path.join(project_dir, 'output')
    if os.path.isdir(output_dir):
        preserved = {'.gitignore', '.git'}
        removed = 0
        for item in os.listdir(output_dir):
            if item in preserved:
                continue
            full_path = os.path.join(output_dir, item)
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
                removed += 1
            else:
                os.remove(full_path)
                removed += 1
        print(f"  Cleared {removed} items from output/")

    # 4. Clear research DB + reports
    research_dir = os.path.join(project_dir, 'research')
    if os.path.isdir(research_dir):
        rdb = os.path.join(research_dir, 'research.db')
        if os.path.exists(rdb):
            os.remove(rdb)
            print(f"  Removed research.db")
        reports_dir = os.path.join(research_dir, 'reports')
        if os.path.isdir(reports_dir):
            count = 0
            for f in os.listdir(reports_dir):
                fp = os.path.join(reports_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)
                    count += 1
            print(f"  Cleared {count} research reports")

    # 5. Clear executor log
    log_path = os.path.join(project_dir, 'executor.log')
    if os.path.exists(log_path):
        os.remove(log_path)
        print(f"  Removed executor.log")

    # 6. Re-seed if seed_tickets.py exists
    seed_script = os.path.join(project_dir, 'seed_tickets.py')
    if os.path.exists(seed_script):
        print(f"  Running seed_tickets.py...")
        import subprocess
        result = subprocess.run(
            [sys.executable, seed_script],
            cwd=project_dir,
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  Seed OK: {result.stdout.strip()}")
        else:
            print(f"  Seed FAILED: {result.stderr.strip()}")
    else:
        print(f"  No seed_tickets.py -- DB will be created fresh by decomposition")

    print(f"  Done: {name}")


def main():
    filter_name = sys.argv[1] if len(sys.argv) > 1 else None
    demos = find_demo_dirs(filter_name)

    if not demos:
        if filter_name:
            print(f"No demo project found: {filter_name}")
            print(f"Available: {[d for d in os.listdir(DEMOS_DIR) if os.path.isdir(os.path.join(DEMOS_DIR, d))]}")
        else:
            print("No demo projects found in demos/")
        sys.exit(1)

    print(f"Resetting {len(demos)} demo(s): {', '.join(n for n, _ in demos)}")

    for name, path in demos:
        reset_demo(name, path)

    print(f"\n{'='*50}")
    print(f"  All demos reset. Ready for conference.")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
