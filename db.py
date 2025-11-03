# db.py
import sqlite3, os
from datetime import datetime

DB_PATH = "stakezone.db"

def init_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS posted (id TEXT PRIMARY KEY, ts INTEGER)")
    conn.close()

def mark_posted(match_id, path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.execute("INSERT OR REPLACE INTO posted VALUES (?, ?)", (str(match_id), int(datetime.now().timestamp())))
    conn.commit(); conn.close()

def was_posted_recently(match_id, hours=24, path=DB_PATH):
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT ts FROM posted WHERE id=?", (str(match_id),)).fetchone()
    conn.close()
    if not row: return False
    return (datetime.now().timestamp() - row[0]) < hours * 3600
