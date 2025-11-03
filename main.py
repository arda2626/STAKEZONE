# ================== main.py — STAKEDRIP AI ULTRA Webhook Free v5.15 ==================
import asyncio, logging, random
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler, JobQueue, ContextTypes
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn
from contextlib import asynccontextmanager

from db import init_db, DB_PATH, mark_posted, was_posted_recently
from fetch_matches_free import fetch_all_matches
from prediction import ai_predict

# ================= CONFIG =================
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
DB_FILE = DB_PATH

MIN_CONFIDENCE = 0.60
MIN_CONFIDENCE_VIP = 0.80
MIN_ODDS = 1.20
WEBHOOK_PATH = "/stakedrip"
WEBHOOK_URL = "https://yourdomain.com" + WEBHOOK_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("stakedrip")

# ================== BAYRAK FONKSİYONU ==================
def country_to_flag(country_name):
    mapping = {
        "Turkey": "🇹🇷",
        "Spain": "🇪🇸",
        "Germany": "🇩🇪",
        "Italy": "🇮🇹",
        "France": "🇫🇷",
        "England": "🏴",
        "USA": "🇺🇸"
        # Buraya diğer ülke bayraklarını ekleyebilirsin
    }
    return mapping.get(country_name, "🌍")

# ================== BANNER FONKSİYONLARI ==================
def create_daily_banner(picks):
    lines = []
    for p in picks:
        home_flag = country_to_flag(p.get("home_country",""))
        away_flag = country_to_flag(p.get("away_country",""))
        match_time = p.get("date","—")
        lines.append(f"{home_flag} {p['home']} vs {away_flag} {p['away']} | {p.get('bet','Tahmin Yok')}, {p.get('odds',1.5):.2f} | Başlangıç: {match_time}")
    return "<b>Günlük Kupon</b>\n" + "\n".join(lines)

def create_vip_banner(picks):
    lines = []
    for p in picks:
        home_flag = country_to_flag(p.get("home_country",""))
        away_flag = country_to_flag(p.get("away_country",""))
        match_time = p.get("date","—")
        lines.append(f"{home_flag} {p['home']} vs {away_flag} {p['away']} | {p.get('bet','Tahmin Yok')}, {p.get('odds',1.5):.2f} | Başlangıç: {match_time}")
    return "<b>VIP Kupon</b>\n" + "\n".join(lines)

def create_live_banner(picks):
    lines = []
    for p in picks:
        home_flag = country_to_flag(p.get("home_country",""))
        away_flag = country_to_flag(p.get("away_country",""))
        lines.append(f"{home_flag} {p['home']} vs {away_flag} {p['away']} | {p.get('bet','Tahmin Yok')}, {p.get('odds',1.5):.2f}")
    return "<b>Canlı Maçlar</b>\n" + "\n".join(lines)

# ================== JOB FONKSİYONLARI ==================
async def daily_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        upcoming = [m for m in matches if not m.get("live")]
        now = datetime.now(timezone.utc)
        picks = []

        for m in upcoming:
            match_time = datetime.fromisoformat(m.get("date"))
            if match_time > now + timedelta(hours=24):
                continue
            if was_posted_recently(m["id"], hours=24, path=DB_FILE):
                continue

            m.setdefault("home", m.get("home","Unknown"))
            m.setdefault("away", m.get("away","Unknown"))
            m.setdefault("odds", 1.5)
            m.setdefault("home_country", m.get("country",""))
            m.setdefault("away_country", m.get("country",""))

            p = ai_predict(m)
            if "bet" not in p or not p["bet"]:
                p["bet"] = "Tahmin Yok"
            p.setdefault("date", m.get("date"))

            if p["confidence"] >= MIN_CONFIDENCE and p["odds"] >= MIN_ODDS:
                picks.append((m["id"], p))

        chosen = [p for mid, p in picks]
        chosen = sorted(chosen, key=lambda x: x.get("confidence",0), reverse=True)

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

async def vip_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        upcoming = [m for m in matches if not m.get("live")]
        now = datetime.now(timezone.utc)
        picks = []

        for m in upcoming:
            match_time = datetime.fromisoformat(m.get("date"))
            if match_time > now + timedelta(hours=24):
                continue
            if was_posted_recently(m["id"], hours=48, path=DB_FILE):
                continue

            m.setdefault("home", m.get("home","Unknown"))
            m.setdefault("away", m.get("away","Unknown"))
            m.setdefault("odds", 1.5)
            m.setdefault("home_country", m.get("country",""))
            m.setdefault("away_country", m.get("country",""))

            p = ai_predict(m)
            if "bet" not in p or not p["bet"]:
                p["bet"] = "Tahmin Yok"
            p.setdefault("date", m.get("date"))

            if p["confidence"] >= MIN_CONFIDENCE_VIP and p["odds"] >= MIN_ODDS:
                picks.append((m["id"], p))

        if picks:
            text = create_vip_banner([p for mid,p in picks])
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            for mid, _ in picks:
                mark_posted(mid, path=DB_FILE)
            log.info("vip_coupon: VIP kupon gönderildi.")
        else:
            log.info("vip_coupon: uygun maç yok")
    except Exception:
        log.exception("vip_coupon hata:")

async def hourly_live_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        live_matches = [m for m in matches if m.get("live")]
        picks = []

        for m in live_matches:
            m.setdefault("home", m.get("home","Unknown"))
            m.setdefault("away", m.get("away","Unknown"))
            m.setdefault("odds", 1.5)
            m.setdefault("home_country", m.get("country",""))
            m.setdefault("away_country", m.get("country",""))

            p = ai_predict(m)
            if "bet" not in p or not p["bet"]:
                p["bet"] = "Tahmin Yok"

            if p["odds"] >= MIN_ODDS:
                picks.append(p)

        if picks:
            text = create_live_banner(picks)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info(f"hourly_live: {len(picks)} canlı maç gönderildi.")
        else:
            log.info("hourly_live: uygun canlı maç yok")
    except Exception:
        log.exception("hourly_live hata:")

# ================== ADMIN COMMANDS ==================
async def test_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await daily_coupon_job(context)
    await update.message.reply_text("Test: Günlük kupon çalıştırıldı.")

async def test_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vip_coupon_job(context)
    await update.message.reply_text("Test: VIP kupon çalıştırıldı.")

async def test_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await hourly_live_job(context)
    await update.message.reply_text("Test: Canlı maç kuponu çalıştırıldı.")

# ================== TELEGRAM APP ==================
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(CommandHandler("test_daily", test_daily))
telegram_app.add_handler(CommandHandler("test_vip", test_vip))
telegram_app.add_handler(CommandHandler("test_live", test_live))

# ================== FASTAPI + LIFESPAN ==================
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(DB_FILE)
    log.info("✅ Database initialized")

    jq: JobQueue = telegram_app.job_queue
    jq.run_repeating(daily_coupon_job, interval=3600*12, first=10)
    jq.run_repeating(vip_coupon_job, interval=3600*24, first=20)
    jq.run_repeating(hourly_live_job, interval=3600, first=30)

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    log.info(f"Webhook set to {WEBHOOK_URL}")
    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA Free APIs")

    yield

    await telegram_app.bot.delete_webhook()
    await telegram_app.stop()
    log.info("Bot stopped")

fastapi_app = FastAPI(lifespan=lifespan)

@fastapi_app.post(WEBHOOK_PATH)
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return {"ok": True}

# ================== RUN SERVER ==================
if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8443)
