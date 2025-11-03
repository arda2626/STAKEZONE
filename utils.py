# utils.py
from datetime import datetime, timezone, timedelta
import sqlite3
import logging
import os
from typing import List, Dict

log = logging.getLogger(__name__)

# Time helpers
def utcnow(): return datetime.now(timezone.utc)
def turkey_now(): return datetime.now(timezone(timedelta(hours=3)))

# Odds helper
def ensure_min_odds(x: float, min_odds: float = 1.2) -> float:
    try:
        v = float(x)
        return round(max(v, min_odds), 2)
    except Exception:
        return min_odds

# small form calc
def calc_form_score(results: List[str]) -> float:
    # results: ["W","D","L"...] -> simple scoring
    if not results: return 0.5
    score = 0.0
    for r in results:
        if r.upper().startswith("W"): score += 1.0
        elif r.upper().startswith("D"): score += 0.6
        else: score += 0.2
    return score / len(results)

def combine_confidence(*args) -> float:
    vals = [float(a) for a in args if a is not None]
    if not vals: return 0.5
    return sum(vals)/len(vals)

# Emoji map (100+ common keys + extras)
EMOJI = {"futbol":"⚽","nba":"🏀","tenis":"🎾","ding":"🔔","cash":"💰","win":"✅","lose":"❌","clock":"🕒","cup":"🏆","info":"ℹ️"}
EMOJI_MAP = {
    "turkey":"🇹🇷","süper lig":"🇹🇷","super lig":"🇹🇷",
    "england":"🏴","premier league":"🏴","man city":"🏴",
    "spain":"🇪🇸","la liga":"🇪🇸","laliga":"🇪🇸",
    "italy":"🇮🇹","serie a":"🇮🇹","inter":"🇮🇹",
    "germany":"🇩🇪","bundesliga":"🇩🇪",
    "france":"🇫🇷","ligue 1":"🇫🇷",
    "portugal":"🇵🇹","netherlands":"🇳🇱","belgium":"🇧🇪",
    "scotland":"🏴","sweden":"🇸🇪","norway":"🇳🇴","denmark":"🇩🇰",
    "poland":"🇵🇱","switzerland":"🇨🇭","austria":"🇦🇹",
    "russia":"🇷🇺","ukraine":"🇺🇦",
    "usa":"🇺🇸","mls":"🇺🇸","canada":"🇨🇦","mexico":"🇲🇽",
    "brazil":"🇧🇷","argentina":"🇦🇷","colombia":"🇨🇴",
    "japan":"🇯🇵","korea":"🇰🇷","china":"🇨🇳","australia":"🇦🇺",
    "saudi":"🇸🇦","qatar":"🇶🇦","egypt":"🇪🇬","morocco":"🇲🇦","south africa":"🇿🇦",
    "nigeria":"🇳🇬","ghana":"🇬🇭",
    "champions league":"🏆","europa league":"🇪🇺","uefa":"🇪🇺","fifa":"🌍",
    "nba":"🇺🇸🏀","euroleague":"🏀🇪🇺","atp":"🎾","wta":"🎾","itf":"🎾"
}
EXTRA_MATCH = {
    "premier":"england","la liga":"spain","serie a":"italy","bundesliga":"germany","ligue 1":"france",
    "mls":"usa","super lig":"turkey","nba":"nba","euroleague":"euroleague","atp":"atp","wta":"wta"
}

def league_to_flag(league_name: str) -> str:
    if not league_name: return "🏟️"
    s = str(league_name).lower()
    for k,v in EMOJI_MAP.items():
        if k in s and len(k) > 1:
            return v
    for substr, mapped in EXTRA_MATCH.items():
        if substr in s:
            return EMOJI_MAP.get(mapped, "🏟️")
    return "🏟️"

# Simple sqlite persistence (keeps same table shape you used)
def init_db(db_path: str):
    con = sqlite3.connect(db_path)
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

def save_prediction(db_path: str, entry: Dict):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("""
    INSERT INTO predictions (event_id, source, sport, league, home, away, bet, odds, prob, created_at, msg_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (entry.get("event_id"), entry.get("source"), entry.get("sport"), entry.get("league"),
          entry.get("home"), entry.get("away"), entry.get("bet"), entry.get("odds"), entry.get("prob"),
          entry.get("created_at"), entry.get("msg_id")))
    con.commit(); con.close()

def get_pending_predictions(db_path: str):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT id,event_id,source,sport,league,home,away,bet,odds FROM predictions WHERE status='pending'")
    rows = cur.fetchall(); con.close(); return rows

def mark_prediction(db_path: str, id_, status, note=""):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("UPDATE predictions SET status=?, resolved_at=?, note=? WHERE id=?", (status, datetime.now(timezone.utc).isoformat(), note, id_))
    con.commit(); con.close()

def day_summary_between(db_path: str, start_iso: str, end_iso: str):
    con = sqlite3.connect(db_path); cur = con.cursor()
    cur.execute("SELECT status, COUNT(*) FROM predictions WHERE created_at BETWEEN ? AND ? GROUP BY status", (start_iso, end_iso))
    rows = cur.fetchall(); con.close(); return rows
