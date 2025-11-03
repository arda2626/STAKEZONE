# ================== main_webhook_free_full.py — STAKEDRIP AI ULTRA v6.0 ==================
import asyncio, logging
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler, JobQueue, ContextTypes
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn

from db import init_db, DB_PATH, mark_posted, was_posted_recently
from fetch_matches_free import fetch_all_matches  # Ücretsiz API'lerden veri çeken modül
from prediction import ai_predict
from messages import create_daily_banner, create_live_banner, create_vip_banner

# ================= CONFIG =================
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
DB_FILE = DB_PATH
MIN_CONFIDENCE = 0.60
MIN_ODDS = 1.20
MAX_LIVE_PICKS = 3

WEBHOOK_PATH = "/stakedrip"
WEBHOOK_URL = "https://yourdomain.com" + WEBHOOK_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("stakedrip")

# ================= JOB FUNCTIONS =================
async def daily_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        now = datetime.now(timezone.utc)
        upcoming = [m for m in matches if not m.get("live")]

        # 24 saat içindeki maçlar
        picks = []
        for m in upcoming:
            match_time_str = m.get("date")
            if not match_time_str:
                continue
            match_time = datetime.fromisoformat(match_time_str)
            if now <= match_time <= now + timedelta(hours=24):
                if was_posted_recently(m["id"], hours=24, path=DB_FILE):
                    continue
                p = ai_predict(m)
                p.setdefault("home", m.get("home"))
                p.setdefault("away", m.get("away"))
                p.setdefault("odds", m.get("odds",1.5))
                p.setdefault("confidence", p.get("confidence",0.5))
                if p["confidence"] >= MIN_CONFIDENCE and p["odds"] >= MIN_ODDS:
                    picks.append((m["id"], p))

        chosen = sorted([p for mid, p in picks], key=lambda x: x["confidence"], reverse=True)

        if chosen:
            text = create_daily_banner(chosen)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            for mid, _ in picks:
                mark_posted(mid, path=DB_FILE)
            log.info(f"daily_coupon: {len(chosen)} tahmin gönderildi.")
        else:
            log.info("daily_coupon: uygun maç yok")
    except Exception:
        log.exception("daily_coupon hata:")

async def live_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        live_matches = [m for m in matches if m.get("live")]
        chosen = []
        for m in live_matches:
            if len(chosen) >= MAX_LIVE_PICKS:
                break
            if was_posted_recently(m["id"], hours=24, path=DB_FILE):
                continue
            p = ai_predict(m)
            p.setdefault("home", m.get("home"))
            p.setdefault("away", m.get("away"))
            p.setdefault("odds", m.get("odds",1.5))
            p.setdefault("confidence", p.get("confidence",0.5))
            if p["confidence"] >= MIN_CONFIDENCE and p["odds"] >= MIN_ODDS:
                chosen.append((m["id"], p))

        if chosen:
            text = create_live_banner([p for mid, p in chosen])
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            for mid, _ in chosen:
                mark_posted(mid, path=DB_FILE)
            log.info(f"live_coupon: {len(chosen)} tahmin gönderildi.")
        else:
            log.info("live_coupon: uygun canlı maç yok")
    except Exception:
        log.exception("live_coupon hata:")

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
            if p["confidence"] >= MIN_CONFIDENCE and p["odds"] >= MIN_ODDS:
                picks.append(p)

        vip = sorted(picks, key=lambda x: x["confidence"], reverse=True)[:3]
        if vip:
            text = create_vip_banner(vip)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info("vip_coupon: gönderildi")
        else:
            log.info("vip_coupon: uygun maç yok")
    except Exception:
        log.exception("vip_coupon hata:")

# ================= ADMIN COMMANDS =================
async def test_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await daily_coupon_job(context)
        await update.message.reply_text("Test: Günlük kupon çalıştırıldı.")
    except Exception:
        log.exception("test_daily hata:")
        await update.message.reply_text("Test sırasında hata oluştu.")

async def test_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await live_coupon_job(context)
        await update.message.reply_text("Test: Canlı kupon çalıştırıldı.")
    except Exception:
        log.exception("test_live hata:")
        await update.message.reply_text("Test sırasında hata oluştu.")

async def test_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await vip_coupon_job(context)
        await update.message.reply_text("Test: VIP kupon çalıştırıldı.")
    except Exception:
        log.exception("test_vip hata:")
        await update.message.reply_text("Test sırasında hata oluştu.")

# ================= FASTAPI + TELEGRAM =================
fastapi_app = FastAPI()
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

# Admin komutları
telegram_app.add_handler(CommandHandler("test_daily", test_daily))
telegram_app.add_handler(CommandHandler("test_live", test_live))
telegram_app.add_handler(CommandHandler("test_vip", test_vip))

@fastapi_app.on_event("startup")
async def startup():
    init_db(DB_FILE)
    log.info("✅ Database initialized")

    jq: JobQueue = telegram_app.job_queue
    jq.run_repeating(daily_coupon_job, interval=3600*12, first=10, name="daily_coupon")
    jq.run_repeating(live_coupon_job, interval=3600, first=30, name="live_coupon")
    jq.run_repeating(vip_coupon_job, interval=86400, first=60, name="vip_coupon")

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    log.info(f"Webhook set to {WEBHOOK_URL}")
    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA Free APIs")

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
