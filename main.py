import asyncio, aiohttp, logging, os, nest_asyncio
from datetime import datetime, timezone, timedelta
from telegram import Bot

# ----------------- LOGGING -----------------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-8s | %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ----------------- CONFIG -----------------
from dotenv import load_dotenv
import os

load_dotenv()  # .env dosyasını oku

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@stakedrip")
THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY")
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"

MAX_LIVE_PICKS = 3
MIN_ODDS = 1.2

def utcnow(): return datetime.now(timezone.utc)

# ----------------- AI -----------------
def ai_for_match(match):
    from random import uniform
    prob = uniform(0.5, 0.95)
    odds = max(match.get("odds",1.5),1.2)
    return {"id": match.get("id"), "prob": prob, "odds": odds, "confidence": prob, "sport": match.get("sport")}

# ----------------- FETCH -----------------
async def fetch_live_matches():
    async with aiohttp.ClientSession() as session:
        url = f"{TSDB_BASE}/eventslive.php"
        try:
            async with session.get(url, timeout=10) as r:
                if "application/json" not in r.headers.get("Content-Type", ""):
                    log.warning(f"fetch_live_matches: unexpected Content-Type {r.headers.get('Content-Type')}")
                    return []
                data = await r.json()
                events = data.get("events", [])
                matches = []
                for e in events:
                    matches.append({
                        "id": e.get("idEvent"),
                        "sport": (e.get("strSport") or "futbol").lower(),
                        "home": e.get("strHomeTeam"),
                        "away": e.get("strAwayTeam"),
                        "odds": 1.5,
                        "confidence": 0.7,
                        "live": True,
                        "start_time": utcnow()
                    })
                return matches
        except Exception as e:
            log.error(f"fetch_live_matches error: {e}")
            return []

# ----------------- PREDICTIONS -----------------
async def hourly_live(bot: Bot):
    matches = await fetch_live_matches()
    live_matches = [m for m in matches if m.get("live")][:MAX_LIVE_PICKS]
    predictions = [ai_for_match(m) for m in live_matches if m.get("odds",0)>=MIN_ODDS]
    if predictions:
        text = "🔥 Hourly Live Predictions 🔥\n"
        for p in predictions:
            text += f"{p['sport'].upper()} | Odds: {p['odds']} | Confidence: {p['confidence']:.2f}\n"
        await bot.send_message(CHANNEL_ID, text)
    log.info(f"Sent {len(predictions)} hourly live predictions")

# ----------------- MAIN LOOP -----------------
async def main():
    nest_asyncio.apply()
    bot = Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            await hourly_live(bot)
            await asyncio.sleep(3600)
        except Exception as e:
            log.error(f"Error in main loop: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
