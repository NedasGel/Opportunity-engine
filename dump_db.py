import sqlite3
import os

db_path = '.tmp/state/opportunity_engine.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
else:
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    cursor.execute("SELECT title, company, prefilter_reason FROM jobs WHERE status = 'REJECTED_PREFILTER';")
    rows = cursor.fetchall()
    with open('dump.txt', 'w', encoding='utf-8') as f:
        f.write(f"Total rejected jobs: {len(rows)}\n")
        for r in rows:
            f.write(f"{r[0]} | {r[1]} | {r[2]}\n")
