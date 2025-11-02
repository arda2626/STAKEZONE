import aiohttp
from datetime import datetime, timedelta
from prediction import make_prediction
from messages import build_live_text
from db import save_prediction
from utils import utcnow
from config import MIN_ODDS, MAX_LIVE_PICKS, DAILY_INTERVAL_HOURS, WEEKLY_DAYS, KASA_HOURS, CHANNEL_ID, THESPORTSDB_KEY, TELEGRAM_TOKEN
from utils import EMOJI
import random

TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"

async def fetch_live_events(session):
    async with session.get(f"{TSDB_BASE}/eventslive.php") as r:
        return await r.json()

async def hourly_live(app):
    async with aiohttp.ClientSession() as session:
        data = await fetch_live_events(session)
        events = data.get("event",[])[:MAX_LIVE_PICKS]
        picks = []
        for e in events:
            pred = await make_prediction({
                "id": e.get("idEvent"),
                "sport": e.get("strSport").lower(),
                "league": e.get("strLeague"),
                "home": e.get("strHomeTeam"),
                "away": e.get("strAwayTeam"),
                "minute": None
            })
            if pred and pred["odds"] >= MIN_ODDS:
                picks.append(pred)
        if picks:
            text = build_live_text(picks)
            sent = await app.bot.send_message(CHANNEL_ID, text, parse_mode="Markdown")
            for p in picks:
                save_prediction({**p,"created_at":utcnow().isoformat(),"msg_id":sent.message_id})

# Günlük, haftalık ve kasa kuponları benzer şekilde modüler olarak eklenebilir
