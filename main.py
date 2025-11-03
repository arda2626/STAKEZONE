# ================== main.py — STAKEDRIP AI ULTRA v5.0 ==================
import asyncio
import logging
from datetime import datetime, timezone

from telegram import Bot
from fetch_matches import fetch_all_matches
from prediction import ai_predict
from messages import create_live_banner, create_daily_banner, create_vip_banner
from scheduler import schedule_jobs
from results import check_results

# ================== CONFIG ==================
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
API_FOOTBALL_KEY = "3838237ec41218c2572ce541708edcfd"

MAX_LIVE_PICKS = 3
MIN_CONFIDENCE = 0.65

# ================== LOGGING ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("stakedrip")

# ================== UTILS ==================
def utcnow():
    return datetime.now(timezone.utc)

# ================== CORE LOOP ==================
async def send_hourly_predictions(bot: Bot):
    try:
        matches = await fetch_all_matches(API_FOOTBALL_KEY)
        live_matches = [m for m in matches if m.get("live")]
        top_live = live_matches[:MAX_LIVE_PICKS]

        predictions = [ai_predict(m) for m in top_live if m["confidence"] >= MIN_CONFIDENCE]
        if not predictions:
            log.info("No live predictions found this hour.")
            return

        banner = create_live_banner(predictions)
        await bot.send_message(chat_id=CHANNEL_ID, text=banner, parse_mode="HTML")
        log.info(f"✅ Sent {len(predictions)} live AI predictions.")
    except Exception as e:
        log.error(f"send_hourly_predictions error: {e}")

# ================== DAILY & VIP JOBS ==================
async def send_daily_coupon(bot: Bot):
    matches = await fetch_all_matches(API_FOOTBALL_KEY)
    top_picks = [ai_predict(m) for m in matches[:5]]
    text = create_daily_banner(top_picks)
    await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    log.info("📅 Daily coupon sent.")

async def send_vip_coupon(bot: Bot):
    matches = await fetch_all_matches(API_FOOTBALL_KEY)
    vip_picks = [ai_predict(m) for m in matches if m["confidence"] > 0.85][:3]
    text = create_vip_banner(vip_picks)
    await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    log.info("💰 VIP (kasa) coupon sent.")

# ================== MAIN LOOP ==================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    log.info("🚀 STAKEDRIP AI ULTRA v5.0 started.")

    # Saatlik canlı tahminler
    await send_hourly_predictions(bot)

    # Günlük ve VIP planlama
    await schedule_jobs(bot, send_hourly_predictions, send_daily_coupon, send_vip_coupon, check_results)

    # Sonsuz döngü
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.warning("Bot stopped manually.")
