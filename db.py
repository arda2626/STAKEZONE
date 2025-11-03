# db.py — küçük DB yardımcıları (SQLite)
import sqlite3
from datetime import datetime, timezone

DB_PATH = "stakedrip.db"

def init_db(path=None):
    p = path or DB_PATH
    con = sqlite3.connect(p, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT,
        sport TEXT,
        league TEXT,
        home TEXT,
        away TEXT,
        bet TEXT,
        odds REAL,
        confidence REAL,
        created_at TEXT,
        msg_id INTEGER,
        status TEXT DEFAULT 'pending',
        note TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posted_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT UNIQUE,
        posted_at TEXT
    )""")
    con.commit()
    con.close()
    return p

def mark_posted(event_id, path=None):
    p = path or DB_PATH
    con = sqlite3.connect(p)
    cur = con.cursor()
    cur.execute("INSERT OR REPLACE INTO posted_events (event_id, posted_at) VALUES (?, ?)", (str(event_id), datetime.now(timezone.utc).isoformat()))
    con.commit()
    con.close()

def was_posted_recently(event_id, hours=24, path=None):
    p = path or DB_PATH
    con = sqlite3.connect(p)
    cur = con.cursor()
    cur.execute("SELECT posted_at FROM posted_events WHERE event_id = ?", (str(event_id),))
    row = cur.fetchone()
    con.close()
    if not row:
        return False
    posted = datetime.fromisoformat(row[0])
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) - posted) < timedelta(hours=hours)
