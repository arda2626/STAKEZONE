# main.py — entry (STAKEDRIP AI ULTRA final)
import asyncio
import logging
from datetime import datetime, timezone
from telegram import Bot
from config import TELEGRAM_TOKEN, CHANNEL_ID, DB_PATH
from fetch_matches import fetch_all_matches
from prediction import ai_predict
from messages import create_live_banner, create_daily_banner, create_vip_banner
from scheduler import schedule_jobs
from results import check_results
from db import ensure
from utils import init_db
import inspect

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("stakedrip")

MAX_LIVE_PICKS = 3
MIN_CONFIDENCE = 0.65

async def call_fetch_all():
    try:
        if inspect.iscoroutinefunction(fetch_all_matches):
            # detect if function has parameter
            if fetch_all_matches.__code__.co_argcount >= 1:
                from config import API_FOOTBALL_KEY
                return await fetch_all_matches(API_FOOTBALL_KEY)
            else:
                return await fetch_all_matches()
        else:
            if fetch_all_matches.__code__.co_argcount >= 1:
                from config import API_FOOTBALL_KEY
                return fetch_all_matches(API_FOOTBALL_KEY)
            else:
                return fetch_all_matches()
    except Exception as e:
        log.exception(f"call_fetch_all error: {e}")
        return []

async def send_hourly_predictions(bot: Bot):
    matches = await call_fetch_all()
    if not matches:
        log.info("send_hourly_predictions: no matches")
        return
    live = [m for m in matches if m.get("live") or m.get("is_live")]
    if not live:
        log.info("No live matches right now.")
        return
    top = live[:MAX_LIVE_PICKS]
    preds = []
    for m in top:
        p = ai_predict(m)
        p.setdefault("home", m.get("home"))
        p.setdefault("away", m.get("away"))
        p.setdefault("odds", m.get("odds", 1.5))
        if p.get("confidence", 0) >= MIN_CONFIDENCE and p.get("odds",1) >= 1.2:
            preds.append(p)
    if not preds:
        log.info("No predictions met thresholds.")
        return
    text = create_live_banner(preds)
    try:
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        log.info(f"Sent {len(preds)} live predictions.")
    except Exception as e:
        log.error(f"Error sending live predictions: {e}")

async def send_daily_coupon(bot: Bot):
    matches = await call_fetch_all()
    upcoming = [m for m in matches if not m.get("live")]
    picks = [ai_predict(m) for m in upcoming]
    chosen = sorted(picks, key=lambda x: x.get("confidence",0), reverse=True)[:3]
    text = create_daily_banner(chosen)
    await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    log.info("Sent daily coupon.")

async def send_vip_coupon(bot: Bot):
    matches = await call_fetch_all()
    picks = [ai_predict(m) for m in matches]
    vip = sorted(picks, key=lambda x: x.get("confidence",0), reverse=True)[:3]
    text = create_vip_banner(vip)
    await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    log.info("Sent VIP coupon.")

async def main():
    # ensure DB
    init_db(DB_PATH)
    ensure()

    bot = Bot(token=TELEGRAM_TOKEN)
    log.info("STAKEDRIP AI ULTRA starting...")

    # run one immediate hourly job
    #await send_hourly_predictions(bot)

    # schedule jobs (tries scheduler.schedule_jobs and falls back)
    try:
        schedule_jobs(bot, send_hourly_predictions, send_daily_coupon, send_vip_coupon, check_results)
        log.info("Jobs scheduled via scheduler.schedule_jobs")
    except Exception:
        # scheduler may schedule itself; otherwise scheduler.py already does fallback (in earlier versions)
        log.info("Scheduler scheduling attempted (see logs).")

    # keep alive
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.warning("Stopped manually")
