# db.py
import sqlite3
from utils import utcnow

DB_PATH = "data.db"

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT,
        source TEXT,
        sport TEXT,
        league TEXT,
        home TEXT,
        away TEXT,
        bet TEXT,
        odds REAL,
        prob INTEGER,
        created_at TEXT,
        msg_id INTEGER,
        status TEXT DEFAULT 'pending',
        resolved_at TEXT,
        note TEXT
    )""")
    con.commit(); con.close()
