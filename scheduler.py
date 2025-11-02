# scheduler.py
import aiohttp
import logging
from datetime import datetime, timedelta, timezone
from utils import utcnow, build_live_text, save_prediction
from prediction import ai_for_match

# ----------------- LOGGING -----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ----------------- CONFIG -----------------
THESPORTSDB_KEY = "YOUR_TSDB_KEY"
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"
CHANNEL_ID = "@YOUR_CHANNEL"
MAX_LIVE_PICKS = 3
MIN_ODDS = 1.2

# ----------------- FETCH MATCHES -----------------
async def fetch_live_matches():
    async with aiohttp.ClientSession() as session:
        url = f"{TSDB_BASE}/eventslive.php"
        try:
            async with session.get(url, timeout=10) as r:
                if r.content_type != "application/json":
                    log.warning(f"Unexpected content type: {r.content_type}")
                    return []
                data = await r.json()
                events = data.get("events", [])
                matches = []
                for e in events:
                    matches.append({
                        "id": e.get("idEvent"),
                        "sport": (e.get("strSport") or "soccer").lower(),
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

async def fetch_upcoming_matches(hours=48):
    # Şimdilik live maçları alıyoruz, placeholder olarak
    live = await fetch_live_matches()
    upcoming = []  # İsteğe bağlı league-specific ekleme
    return live + upcoming

# ----------------- SCHEDULER FUNCTIONS -----------------
async def hourly_live(bot, matches):
    live_matches = [m for m in matches if m.get("live")][:MAX_LIVE_PICKS]
    predictions = [ai_for_match(m) for m in live_matches if m.get("odds",0)>=MIN_ODDS]
    for pred in predictions:
        text = build_live_text([pred])
        await bot.send_message(CHANNEL_ID, text)
    log.info(f"Sent {len(predictions)} hourly live predictions")
    return predictions

async def daily_coupon(bot, matches):
    now = utcnow()
    upcoming = [m for m in matches if m.get("start_time") < now + timedelta(hours=24)]
    predictions = [ai_for_match(m) for m in upcoming]
    if predictions:
        text = "\n".join([f"{p['home']} vs {p['away']} | Odds: {p['odds']} | Confidence: {p['confidence']:.2f}" for p in predictions])
        await bot.send_message(CHANNEL_ID, f"📅 Daily Coupon 📅\n{text}")
    log.info("Daily coupon sent")
    return predictions

async def weekly_coupon(bot, matches):
    now = utcnow()
    upcoming = [m for m in matches if m.get("start_time") < now + timedelta(days=7)]
    predictions = [ai_for_match(m) for m in upcoming]
    if predictions:
        text = "\n".join([f"{p['home']} vs {p['away']} | Odds: {p['odds']} | Confidence: {p['confidence']:.2f}" for p in predictions])
        await bot.send_message(CHANNEL_ID, f"🗓️ Weekly Coupon 🗓️\n{text}")
    log.info("Weekly coupon sent")
    return predictions

async def kasa_coupon(bot, matches):
    now = utcnow()
    upcoming = [m for m in matches if m.get("start_time") < now + timedelta(hours=48)]
    sorted_matches = sorted(upcoming, key=lambda x: x.get("confidence",0), reverse=True)
    predictions = [ai_for_match(m) for m in sorted_matches[:3]]
    if predictions:
        text = "\n".join([f"{p['home']} vs {p['away']} | Odds: {p['odds']} | Confidence: {p['confidence']:.2f}" for p in predictions])
        await bot.send_message(CHANNEL_ID, f"💰 Kasa Coupon 💰\n{text}")
    log.info("Kasa coupon sent")
    return predictions
