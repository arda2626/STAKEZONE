# bot.py
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
import os
import logging
from random import uniform
from telegram import Bot
from telegram.ext import Application, ContextTypes

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY", "457761c3fe3072466a8899578fefc5e4")
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")

MIN_ODDS = 1.2
MAX_LIVE_PICKS = 3
LIVE_INTERVAL_SECONDS = 3600  # saatlik canlı tahmin

# ---------------- UTILS ----------------
def utcnow(): return datetime.now(timezone.utc)
def turkey_now(): return datetime.now(timezone(timedelta(hours=3)))

# ---------------- AI PREDICTION ----------------
def ai_for_match(match):
    home_form = sum(match.get("form_home",[0.7,0.7,0.7])) / max(len(match.get("form_home",[1])),1)
    away_form = sum(match.get("form_away",[0.7,0.7,0.7])) / max(len(match.get("form_away",[1])),1)
    base_prob = 0.5 + (home_form - away_form)/4
    base_prob = min(max(base_prob,0.05),0.95)
    odds = match.get("odds", 1.5)
    confidence = base_prob * (odds/2)
    return {
        "id": match.get("id"),
        "home": match.get("home"),
        "away": match.get("away"),
        "sport": match.get("sport"),
        "prob": round(base_prob,2),
        "confidence": round(confidence,2),
        "odds": odds,
        "start_time": match.get("start_time")
    }

# ---------------- FETCH MATCHES ----------------
async def fetch_matches(sport="Soccer", league_id=None):
    async with aiohttp.ClientSession() as session:
        url = f"{TSDB_BASE}/eventsnextleague.php?id={league_id}" if league_id else f"{TSDB_BASE}/livescore.php?s={sport}"
        try:
            resp = await session.get(url, timeout=15)
            if resp.status != 200:
                log.warning(f"fetch_matches {sport} status={resp.status}")
                return []
            data = await resp.json()
            events = data.get("events") or data.get("event") or []
            matches = []
            for e in events:
                matches.append({
                    "id": e.get("idEvent"),
                    "home": e.get("strHomeTeam"),
                    "away": e.get("strAwayTeam"),
                    "sport": sport.lower(),
                    "odds": uniform(1.2,2.0),  # dummy odds
                    "confidence": 0,
                    "live": e.get("strStatus","").lower() in ["live","in progress"],
                    "start_time": datetime.strptime(e.get("dateEvent","") + " " + (e.get("strTime","12:00:00")), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) if e.get("dateEvent") else utcnow(),
                    "form_home":[uniform(0.5,1) for _ in range(3)],
                    "form_away":[uniform(0.5,1) for _ in range(3)]
                })
            return matches
        except Exception as e:
            log.debug(f"fetch_matches error: {e}")
            return []

# ---------------- PREDICTION FUNCTIONS ----------------
async def hourly_live(ctx: ContextTypes.DEFAULT_TYPE):
    matches = await fetch_all_matches()
    live_matches = [m for m in matches if m.get("live")][:MAX_LIVE_PICKS]
    predictions = [ai_for_match(m) for m in live_matches if m.get("odds", 0) >= MIN_ODDS]
    if predictions:
        text = "\n".join([f"{p['home']} vs {p['away']} • {p['odds']} • {p['prob']*100:.0f}% olasılık" for p in predictions])
        await ctx.bot.send_message(CHANNEL_ID, f"🔥 CANLI TAHMİNLER 🔥\n{text}")
    log.info(f"{len(predictions)} canlı tahmin gönderildi")

async def daily_coupon(ctx: ContextTypes.DEFAULT_TYPE):
    matches = await fetch_all_matches()
    upcoming = [m for m in matches if m.get("start_time") < utcnow() + timedelta(hours=24)]
    predictions = [ai_for_match(m) for m in upcoming]
    if predictions:
        text = "\n".join([f"{p['home']} vs {p['away']} • {p['odds']} • {p['prob']*100:.0f}% olasılık" for p in predictions])
        await ctx.bot.send_message(CHANNEL_ID, f"📅 GÜNLÜK KUPON 🔥\n{text}")
    log.info(f"Günlük kupon tahminleri gönderildi")

async def fetch_all_matches():
    football_leagues = ["4328","4329","4335","4332","4331"]
    nba_league = ["4387"]
    tennis_sports = ["Tennis"]

    matches = []
    for lid in football_leagues:
        matches += await fetch_matches("Soccer", lid)
    for lid in nba_league:
        matches += await fetch_matches("Basketball", lid)
    for sport in tennis_sports:
        matches += await fetch_matches("Tennis")
    return matches

# ---------------- RUN BOT ----------------
async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    jq = app.job_queue
    jq.run_repeating(hourly_live, interval=LIVE_INTERVAL_SECONDS, first=10)
    jq.run_repeating(daily_coupon, interval=3600*12, first=30)
    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
