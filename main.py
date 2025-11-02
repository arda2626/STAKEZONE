# main.py
import asyncio, aiohttp, logging
from datetime import datetime, timezone
from telegram import Bot

# ----------------- LOGGING -----------------
logging.basicConfig(level=logging.INFO,
                    format="%(H:%M:%S) | %(levelname)-8s | %(message)s")
log = logging.getLogger(__name__)

# ----------------- CONFIG -----------------
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
THESPORTSDB_KEY = "457761c3fe3072466a8899578fefc5e4"
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"

MAX_LIVE_PICKS = 3
MIN_ODDS = 1.2

def utcnow():
    return datetime.now(timezone.utc)

# ----------------- AI -----------------
def ai_for_match(match):
    from random import uniform
    prob = uniform(0.5, 0.95)
    odds = max(match.get("odds",1.5),1.2)
    return {
        "id": match.get("id"),
        "sport": match.get("sport"),
        "odds": odds,
        "confidence": prob
    }

# ----------------- FETCH LIVE MATCHES -----------------
async def fetch_live_matches():
    async with aiohttp.ClientSession() as session:
        url = f"{TSDB_BASE}/eventslive.php"
        try:
            async with session.get(url, timeout=10) as r:
                content_type = r.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    log.warning(f"fetch_live_matches: unexpected Content-Type {content_type}")
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

# ----------------- SEND PREDICTIONS -----------------
async def hourly_live(bot: Bot):
    matches = await fetch_live_matches()
    live_matches = [m for m in matches if m.get("live")][:MAX_LIVE_PICKS]
    predictions = [ai_for_match(m) for m in live_matches if m.get("odds",0) >= MIN_ODDS]
    if predictions:
        text = "🔥 Hourly Live Predictions 🔥\n"
        for p in predictions:
            text += f"{p['sport'].upper()} | {p.get('home','')} vs {p.get('away','')} | Odds: {p['odds']} | Confidence: {p['confidence']:.2f}\n"
        try:
            await bot.send_message(CHANNEL_ID, text)
            log.info(f"Sent {len(predictions)} hourly live predictions")
        except Exception as e:
            log.error(f"Error sending Telegram message: {e}")
    else:
        log.info("No live matches found this hour")

# ----------------- MAIN LOOP -----------------
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            await hourly_live(bot)
            await asyncio.sleep(3600)  # 1 saat bekle
        except Exception as e:
            log.error(f"Error in main loop: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
