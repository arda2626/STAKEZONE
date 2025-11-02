# main.py
import asyncio
from datetime import datetime, timezone, timedelta
import logging
import aiohttp
import nest_asyncio
from telegram import Bot

# ----------------- LOGGING -----------------
logging.basicConfig(level=logging.INFO, format="%(H:%M:%S) | %(levelname)-8s | %(message)s")
log = logging.getLogger(__name__)

# ----------------- TELEGRAM CONFIG -----------------
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"

# ----------------- API CONFIG -----------------
THESPORTSDB_KEY = "457761c3fe3072466a8899578fefc5e4"
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"

# ----------------- UTILS -----------------
def utcnow(): return datetime.now(timezone.utc)
def ai_for_match(match):
    from random import uniform
    prob = uniform(0.5, 0.95)
    odds = max(match.get("odds",1.5),1.2)
    return {"id": match.get("id"), "prob": prob, "odds": odds, "confidence": prob, "sport": match.get("sport")}

MAX_LIVE_PICKS = 3
MIN_ODDS = 1.2

# ----------------- FETCH MATCHES -----------------
async def fetch_live_matches():
    async with aiohttp.ClientSession() as session:
        url = f"{TSDB_BASE}/eventslive.php"
        try:
            async with session.get(url, timeout=10) as r:
                data = await r.json()
                events = data.get("events", [])
                matches = []
                for e in events:
                    matches.append({
                        "id": e.get("idEvent"),
                        "sport": (e.get("strSport") or "futbol").lower(),
                        "home": e.get("strHomeTeam"),
                        "away": e.get("strAwayTeam"),
                        "odds": 1.5,  # placeholder, API üzerinden yok
                        "confidence": 0.7,  # placeholder
                        "live": True,
                        "start_time": utcnow()
                    })
                return matches
        except Exception as e:
            log.error(f"fetch_live_matches error: {e}")
            return []

async def fetch_upcoming_matches(hours=48):
    # Placeholder: for simplicity, we fetch live + next 48h as upcoming
    live = await fetch_live_matches()
    upcoming = []
    # API TheSportsDB ücretsiz sürümde global next24h yok; burayı league-specific yapabilirsiniz
    return live + upcoming

# ----------------- SCHEDULER FUNCTIONS -----------------
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
    return predictions

async def daily_coupon(bot: Bot):
    matches = await fetch_upcoming_matches(hours=24)
    predictions = [ai_for_match(m) for m in matches]
    if predictions:
        text = "📅 Daily Coupon Predictions 📅\n"
        for p in predictions:
            text += f"{p['sport'].upper()} | Odds: {p['odds']} | Confidence: {p['confidence']:.2f}\n"
        await bot.send_message(CHANNEL_ID, text)
    log.info(f"Sent {len(predictions)} daily coupon predictions")
    return predictions

async def weekly_coupon(bot: Bot):
    matches = await fetch_upcoming_matches(hours=24*7)
    predictions = [ai_for_match(m) for m in matches]
    if predictions:
        text = "🗓️ Weekly Coupon Predictions 🗓️\n"
        for p in predictions:
            text += f"{p['sport'].upper()} | Odds: {p['odds']} | Confidence: {p['confidence']:.2f}\n"
        await bot.send_message(CHANNEL_ID, text)
    log.info(f"Sent {len(predictions)} weekly coupon predictions")
    return predictions

async def kasa_coupon(bot: Bot):
    matches = await fetch_upcoming_matches(hours=48)
    sorted_matches = sorted(matches, key=lambda x: x.get("confidence",0), reverse=True)
    predictions = [ai_for_match(m) for m in sorted_matches[:3]]
    if predictions:
        text = "💰 Kasa (Most Reliable) Predictions 💰\n"
        for p in predictions:
            text += f"{p['sport'].upper()} | Odds: {p['odds']} | Confidence: {p['confidence']:.2f}\n"
        await bot.send_message(CHANNEL_ID, text)
    log.info(f"Sent {len(predictions)} kasa coupon predictions")
    return predictions

# ----------------- MAIN LOOP -----------------
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            await hourly_live(bot)
            await daily_coupon(bot)
            await weekly_coupon(bot)
            await kasa_coupon(bot)
            await asyncio.sleep(3600)  # 1 saat bekle
        except Exception as e:
            log.error(f"Error in main loop: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())
