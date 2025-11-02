EMOJI = {"futbol":"⚽","nba":"🏀","tenis":"🎾","ding":"🔔","cash":"💰","win":"✅","lose":"❌","clock":"🕒","cup":"🏆","info":"ℹ️"}

EMOJI_MAP = { "turkey":"🇹🇷","süper lig":"🇹🇷","england":"🏴","premier league":"🏴","spain":"🇪🇸","laliga":"🇪🇸" }  # vs. önceki

EXTRA_MATCH = { "super lig":"turkey","süper lig":"turkey","premier":"england","la liga":"spain" }

def banner(title_short):
    return "\n".join(["═"*38, "💎 STAKEDRIP LIVE PICKS 💎", f"🔥 AI CANLI TAHMİN ({title_short}) 🔥", "═"*38])

def league_to_flag(league_name):
    if not league_name: return "🏟️"
    s = str(league_name).lower()
    for k,v in EMOJI_MAP.items():
        if k in s: return v
    for substr, mapped in EXTRA_MATCH.items():
        if substr in s: return EMOJI_MAP.get(mapped, "🏟️")
    return "🏟️"

from datetime import datetime, timezone, timedelta
def utcnow(): return datetime.now(timezone.utc)
def turkey_now(): return datetime.now(timezone(timedelta(hours=3)))
