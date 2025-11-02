# main.py
import asyncio
from scheduler import hourly_live, daily_coupon, weekly_coupon, kasa_coupon, check_results, daily_summary
import datetime

matches = [
    {"id": 1, "live": True, "odds": 1.5, "confidence": 0.8, "start_time": datetime.datetime.utcnow()},
    {"id": 2, "live": True, "odds": 1.3, "confidence": 0.6, "start_time": datetime.datetime.utcnow()},
    {"id": 3, "live": False, "odds": 1.7, "confidence": 0.9, "start_time": datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
]

async def main():
    print("Hourly Live Predictions:")
    print(await hourly_live(matches))

    print("\nDaily Coupon Predictions:")
    print(await daily_coupon(matches))

    print("\nWeekly Coupon Predictions:")
    print(await weekly_coupon(matches))

    print("\nKasa Coupon Predictions:")
    print(await kasa_coupon(matches))

    print("\nFinished Matches Check:")
    print(await check_results(matches))

asyncio.run(main())
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

async def safe_delete_webhook(token):
    import aiohttp
    try:
        async with aiohttp.ClientSession() as s:
            url = f"https://api.telegram.org/bot{token}/deleteWebhook"
            async with s.post(url, timeout=10) as r:
                log.info(f"deleteWebhook -> {r.status}")
    except Exception as e:
        log.debug(f"safe_delete_webhook error: {e}")

async def main():
    init_db()
    await safe_delete_webhook(TELEGRAM_TOKEN)
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    job = app.job_queue

    # schedule jobs
    job.run_repeating(hourly_live, interval=LIVE_INTERVAL_SECONDS, first=10, name="hourly_live")  # hourly
    job.run_repeating(check_results, interval=300, first=30, name="check_results")               # every 5 minutes
    # daily coupon every 12 hours (first at next minute)
    job.run_repeating(daily_coupon, interval=3600*12, first=60, name="daily_coupon")
    # weekly and kasa placeholders; weekly run repeating daily check and internal logic handles weekday check if needed
    job.run_repeating(weekly_coupon, interval=86400, first=300, name="weekly_coupon")
    job.run_repeating(kasa_coupon, interval=86400, first=600, name="kasa_coupon")
    # daily summary at 23:00 Turkey could be added with run_daily but using repeating as placeholder
    job.run_repeating(daily_summary, interval=86400, first=30, name="daily_summary")

    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA (TSDB-only predictions)")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
