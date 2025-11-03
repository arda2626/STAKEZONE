import asyncio, aiohttp, logging, os
from datetime import datetime, timezone
from telegram import Bot

# ----------------- LOGGING -----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ----------------- CONFIG -----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@stakedrip")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "3838237ec41218c2572ce541708edcfd")

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
        "home": match.get("home"),
        "away": match.get("away"),
        "odds": odds,
        "confidence": prob
    }

# ----------------- FETCH LIVE MATCHES -----------------
async def fetch_live_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    matches = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as r:
                if r.status != 200:
                    log.warning(f"fetch_live_matches: status {r.status}")
                    return []
                data = await r.json()
                for f in data.get("response", []):
                    fixture = f.get("fixture", {})
                    teams = f.get("teams", {})
                    matches.append({
                        "id": fixture.get("id"),
                        "sport": "futbol",
                        "home": teams.get("home", {}).get("name"),
                        "away": teams.get("away", {}).get("name"),
                        "odds": 1.5,
                        "confidence": 0.7,
                        "live": fixture.get("status", {}).get("short") in ["1H","2H"],
                        "start_time": utcnow()
                    })
    except Exception as e:
        log.error(f"fetch_live_matches error: {e}")
    return matches

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
            await asyncio.sleep(3600)
        except Exception as e:
            log.error(f"Error in main loop: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
