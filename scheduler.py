# ================== scheduler.py — STAKEDRIP AI ULTRA v5.0+ ==================
import asyncio
import logging
from telegram import Bot
from fetch_matches import fetch_all_matches
from prediction import generate_prediction
from messages import create_live_banner, create_daily_banner, create_vip_banner

log = logging.getLogger("scheduler")

async def send_live_predictions(bot, channel, api_key):
    matches = await fetch_all_matches(api_key)
    selected = [generate_prediction(m) for m in matches[:3]]
    if selected:
        text = create_live_banner(selected)
        await bot.send_message(channel, text, parse_mode="HTML")
        log.info(f"Sent {len(selected)} live predictions.")
    else:
        log.info("No live matches found this hour.")

async def send_daily_coupon(bot, channel, api_key):
    matches = await fetch_all_matches(api_key)
    picks = [generate_prediction(m) for m in matches[:3]]
    text = create_daily_banner(picks)
    await bot.send_message(channel, text, parse_mode="HTML")

async def send_vip_coupon(bot, channel, api_key):
    matches = await fetch_all_matches(api_key)
    picks = [generate_prediction(m) for m in matches[:2]]
    text = create_vip_banner(picks)
    await bot.send_message(channel, text, parse_mode="HTML")

async def scheduler_main(bot_token, channel_id, api_key):
    bot = Bot(token=bot_token)
    while True:
        now = asyncio.get_event_loop().time()
        try:
            await send_live_predictions(bot, channel_id, api_key)
            if int(now) % 86400 < 3600:
                await send_daily_coupon(bot, channel_id, api_key)
            if int(now) % (7*86400) < 3600:
                await send_vip_coupon(bot, channel_id, api_key)
        except Exception as e:
            log.error(f"Scheduler error: {e}")
        await asyncio.sleep(3600)
