# main.py
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from telegram import Bot
from utils import utcnow, banner
from prediction import ai_for_match
from fetch_matches import fetch_football_matches, fetch_nba_matches, fetch_tennis_matches

# ----------------- LOGGING -----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ----------------- CONFIG -----------------
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
MAX_LIVE_PICKS = 3
MIN_ODDS = 1.2

# ----------------- FETCH ALL -----------------
async def fetch_all():
    football = await fetch_football_matches()
    nba = await fetch_nba_matches()
    tennis = await fetch_tennis_matches()
    return football + nba + tennis

# ----------------- SEND PREDICTIONS -----------------
async def send_predictions(bot: Bot, title, matches, max_picks=3):
    live_matches = [m for m in matches if m.get("live")][:max_picks]
    predictions = [ai_for_match(m) for m in live_matches if m.get("odds",0) >= MIN_ODDS]

    if not predictions:
        log.info(f"No {title} matches found")
        return

    text = banner(title) + "\n"
    for p in predictions:
        text += f"{p['sport'].upper()} | {p.get('home','')} vs {p.get('away','')} | Tahmin: {p.get('bet_text','1X2')} | Oran: {p.get('odds')} | Conf: {p.get('confidence'):.2f}\n"

    try:
        await bot.send_message(CHANNEL_ID, text)
        log.info(f"Sent {len(predictions)} {title} predictions")
    except Exception as e:
        log.error(f"Error sending Telegram message: {e}")

# ----------------- MAIN LOOP -----------------
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            matches = await fetch_all()
            # Canlı maçlar
            await send_predictions(bot, "CANLI", matches, MAX_LIVE_PICKS)
            # Günlük kupon
            await send_predictions(bot, "GÜNLÜK", matches, max_picks=5)
            # Haftalık kupon
            await send_predictions(bot, "HAFTALIK", matches, max_picks=7)
            # Kasa kupon (en yüksek confidence)
            top_conf = sorted([ai_for_match(m) for m in matches], key=lambda x: x["confidence"], reverse=True)
            if top_conf:
                text = banner("KASA") + "\n"
                for p in top_conf[:3]:
                    text += f"{p['sport'].upper()} | {p.get('home','')} vs {p.get('away','')} | Tahmin: {p.get('bet_text','1X2')} | Oran: {p.get('odds')} | Conf: {p.get('confidence'):.2f}\n"
                try:
                    await bot.send_message(CHANNEL_ID, text)
                    log.info("Sent KASA predictions")
                except Exception as e:
                    log.error(f"Error sending KASA: {e}")

            await asyncio.sleep(3600)  # 1 saat bekle
        except Exception as e:
            log.error(f"Error in main loop: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
