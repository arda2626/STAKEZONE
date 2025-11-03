# ================== main_webhook_auto.py — STAKEDRIP AI ULTRA v6 ==================
import asyncio, logging
from datetime import time as dt_time, timezone
from telegram.ext import Application, JobQueue, ContextTypes
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn

from db import init_db, DB_PATH, mark_posted, was_posted_recently
from fetch_matches import fetch_all_matches
from prediction import ai_predict
from messages import create_live_banner, create_daily_banner, create_vip_banner
from results import check_results

# ================= CONFIG =================
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
DB_FILE = DB_PATH
MAX_LIVE_PICKS = 3
MIN_CONFIDENCE = 0.60
MIN_ODDS = 1.20

WEBHOOK_PATH = "/stakedrip"
WEBHOOK_URL = "https://yourdomain.com" + WEBHOOK_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("stakedrip")

# ================= JOB FUNCTIONS =================
async def hourly_live_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        live = [m for m in matches if m.get("live")]
        chosen = []
        for m in live:
            if len(chosen) >= MAX_LIVE_PICKS:
                break
            eid = m.get("id")
            if eid and was_posted_recently(eid, hours=24, path=DB_FILE):
                continue
            p = ai_predict(m)
            if p["odds"] >= MIN_ODDS and p["confidence"] >= MIN_CONFIDENCE:
                p["minute"] = m.get("minute")
                chosen.append((eid, p))
        if chosen:
            text = create_live_banner([p for eid, p in chosen])
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            for eid, _ in chosen:
                mark_posted(eid, path=DB_FILE)
            log.info(f"hourly_live: {len(chosen)} tahmin gönderildi.")
        else:
            log.info("hourly_live: uygun tahmin yok")
    except Exception:
        log.exception("hourly_live hata:")

async def daily_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        upcoming = [m for m in matches if not m.get("live")]
        picks = []
        for m in upcoming:
            p = ai_predict(m)
            p.setdefault("home", m.get("home"))
            p.setdefault("away", m.get("away"))
            p.setdefault("odds", m.get("odds", 1.5))
            p.setdefault("confidence", p.get("confidence", 0.5))
            picks.append(p)
        chosen = sorted(picks, key=lambda x: x.get("confidence",0), reverse=True)[:3]
        if chosen:
            text = create_daily_banner(chosen)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info("daily_coupon: gönderildi")
    except Exception:
        log.exception("daily_coupon hata:")

async def vip_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        picks = []
        for m in matches:
            p = ai_predict(m)
            p.setdefault("home", m.get("home"))
            p.setdefault("away", m.get("away"))
            p.setdefault("odds", m.get("odds",1.5))
            p.setdefault("confidence", p.get("confidence",0.5))
            picks.append(p)
        vip = sorted(picks, key=lambda x: x.get("confidence",0), reverse=True)[:3]
        if vip:
            text = create_vip_banner(vip)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info("vip_coupon: gönderildi")
    except Exception:
        log.exception("vip_coupon hata:")

async def results_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        await check_results(bot)
    except Exception:
        log.exception("results_job hata:")

# ================= FASTAPI + TELEGRAM =================
fastapi_app = FastAPI()
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

@fastapi_app.on_event("startup")
async def startup():
    init_db(DB_FILE)
    log.info("✅ Database initialized")
    
    jq: JobQueue = telegram_app.job_queue
    jq.run_repeating(hourly_live_job, interval=3600, first=10, name="hourly_live")  # Saat başı
    jq.run_repeating(daily_coupon_job, interval=3600*12, first=60, name="daily_coupon")  # 12 saatte bir
    jq.run_repeating(vip_coupon_job, interval=86400, first=120, name="vip_coupon")  # Günlük VIP
    jq.run_daily(results_job, time=dt_time(hour=20, minute=0, tzinfo=timezone.utc), name="results_check")  # Günlük sonuç
    
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    log.info(f"Webhook set to {WEBHOOK_URL}")
    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA")

@fastapi_app.on_event("shutdown")
async def shutdown():
    await telegram_app.bot.delete_webhook()
    await telegram_app.stop()
    log.info("Bot stopped")

@fastapi_app.post(WEBHOOK_PATH)
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8443)
