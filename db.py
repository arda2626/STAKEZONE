# db.py
import sqlite3
from datetime import datetime, timezone
from config import DB_PATH

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
    con.commit()
    con.close()

def save_prediction(entry):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    INSERT INTO predictions (event_id, source, sport, league, home, away, bet, odds, prob, created_at, msg_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (entry.get("event_id"), entry.get("source"), entry.get("sport"), entry.get("league"),
          entry.get("home"), entry.get("away"), entry.get("bet"), entry.get("odds"), entry.get("prob"),
          entry.get("created_at"), entry.get("msg_id")))
    con.commit(); con.close()

def get_pending_predictions():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id,event_id,source,sport,league,home,away,bet,odds FROM predictions WHERE status='pending'")
    rows = cur.fetchall(); con.close(); return rows

def mark_prediction(id_, status, note=""):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("UPDATE predictions SET status=?, resolved_at=?, note=? WHERE id=?", (status, datetime.now(timezone.utc).isoformat(), note, id_))
    con.commit(); con.close()

def day_summary_between(start_iso, end_iso):
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    cur.execute("SELECT status, COUNT(*) FROM predictions WHERE created_at BETWEEN ? AND ? GROUP BY status", (start_iso, end_iso))
    rows = cur.fetchall(); con.close(); return rows
