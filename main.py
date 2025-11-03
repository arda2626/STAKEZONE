# ================== main.py — STAKEDRIP AI ULTRA Webhook v5.7 ==================
import asyncio, logging
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler, JobQueue, ContextTypes
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn

from db import init_db, DB_PATH
from fetch_matches import fetch_all_matches
from prediction import ai_predict
from messages import create_daily_banner

# ================= CONFIG =================
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
DB_FILE = DB_PATH

WEBHOOK_PATH = "/stakedrip"
WEBHOOK_URL = "https://yourdomain.com" + WEBHOOK_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("stakedrip")

# ================= JOB FUNCTIONS =================
DAILY_COUPON_HOURS = 12
MIN_CONFIDENCE = 0.6  # Güven skoru eşiği
MIN_ODDS = 1.2

async def daily_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        upcoming = [m for m in matches if not (m.get("live") or m.get("is_live"))]
        
        # 12 saat içindeki maçlar
        upcoming_12h = []
        for m in upcoming:
            match_time = m.get("timestamp")  # fetch_matches.py'de UTC timestamp olarak olmalı
            if match_time:
                match_dt = datetime.fromtimestamp(match_time, tz=timezone.utc)
                if now <= match_dt <= now + timedelta(hours=DAILY_COUPON_HOURS):
                    upcoming_12h.append(m)
        
        picks = []
        for m in upcoming_12h:
            p = ai_predict(m)
            p.setdefault("home", m.get("home"))
            p.setdefault("away", m.get("away"))
            p.setdefault("odds", m.get("odds",1.5))
            p.setdefault("confidence", p.get("confidence",0.5))
            if p["confidence"] >= MIN_CONFIDENCE and p["odds"] >= MIN_ODDS:
                picks.append(p)
        
        # Güven skoru yüksekten düşüğe sıralama
        chosen = sorted(picks, key=lambda x: x["confidence"], reverse=True)
        
        if chosen:
            text = create_daily_banner(chosen)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info(f"daily_coupon: {len(chosen)} güvenli maç gönderildi")
        else:
            log.info("daily_coupon: uygun maç yok")
    except Exception:
        log.exception("daily_coupon hata:")

# Admin test komutu
async def test_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        matches = await fetch_all_matches()
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        upcoming = [m for m in matches if not (m.get("live") or m.get("is_live"))]
        upcoming_12h = []
        for m in upcoming:
            match_time = m.get("timestamp")
            if match_time:
                match_dt = datetime.fromtimestamp(match_time, tz=timezone.utc)
                if now <= match_dt <= now + timedelta(hours=DAILY_COUPON_HOURS):
                    upcoming_12h.append(m)
        picks = []
        for m in upcoming_12h:
            p = ai_predict(m)
            p.setdefault("home", m.get("home"))
            p.setdefault("away", m.get("away"))
            p.setdefault("odds", m.get("odds",1.5))
            p.setdefault("confidence", p.get("confidence",0.5))
            if p["confidence"] >= MIN_CONFIDENCE and p["odds"] >= MIN_ODDS:
                picks.append(p)
        chosen = sorted(picks, key=lambda x: x["confidence"], reverse=True)[:10]
        if chosen:
            text = create_daily_banner(chosen)
            await update.message.reply_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text("Test: uygun güvenli maç yok")
    except Exception:
        log.exception("test_daily hata:")
        await update.message.reply_text("Test sırasında hata oluştu.")

# ================= FASTAPI + TELEGRAM =================
fastapi_app = FastAPI()
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(CommandHandler("test_daily", test_daily))

@fastapi_app.on_event("startup")
async def startup():
    init_db(DB_FILE)
    log.info("✅ Database initialized")
    
    jq: JobQueue = telegram_app.job_queue
    jq.run_repeating(daily_coupon_job, interval=3600*12, first=60, name="daily_coupon")
    
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
