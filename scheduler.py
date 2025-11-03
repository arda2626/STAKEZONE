# scheduler.py
# schedules jobs using telegram.ext.Application job queue (job functions supplied by main)
import logging
from telegram.ext import Application
from config import TELEGRAM_TOKEN, LIVE_INTERVAL_SECONDS, DAILY_INTERVAL_SECONDS, RESULTS_CHECK_SECONDS
from datetime import time as dt_time, timezone

log = logging.getLogger(__name__)

def schedule_jobs(bot, hourly_fn, daily_fn, vip_fn, results_fn=None):
    """
    Synchronous function that starts Application and schedules repeating jobs.
    Called from main: schedule_jobs(bot, send_hourly_predictions, send_daily_coupon, send_vip_coupon, check_results)
    """
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    jq = app.job_queue

    async def _hourly(ctx):
        await hourly_fn(bot)

    async def _daily(ctx):
        await daily_fn(bot)

    async def _vip(ctx):
        await vip_fn(bot)

    async def _results(ctx):
        if results_fn:
            await results_fn(bot)

    # schedule
    jq.run_repeating(_hourly, interval=LIVE_INTERVAL_SECONDS, first=10, name="hourly_live")
    jq.run_repeating(_daily, interval=DAILY_INTERVAL_SECONDS, first=60, name="daily_coupon")
    jq.run_repeating(_vip, interval=86400, first=120, name="vip_coupon")
    if results_fn:
        jq.run_repeating(_results, interval=RESULTS_CHECK_SECONDS, first=30, name="results_check")

    # start background polling
    import asyncio
    async def _start_app():
        await app.initialize()
        await app.start()
        log.info("Scheduler app started (job queue running).")

    asyncio.create_task(_start_app())
    return app
