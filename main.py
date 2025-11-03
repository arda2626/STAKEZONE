# ================== main.py — STAKEDRIP AI ULTRA Webhook Free v5.15 ==================
import asyncio, logging
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn

from db import init_db, DB_PATH, mark_posted, was_posted_recently
from fetch_matches_free import fetch_all_matches
from prediction import ai_predict
from utils import league_to_flag

# ================= CONFIG =================
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHANNEL_ID = "@stakedrip"
DB_FILE = DB_PATH

MIN_CONFIDENCE = 0.60
MIN_CONFIDENCE_VIP = 0.80
MIN_ODDS = 1.20

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("stakedrip")

# ================== BANNER FONKSİYONLARI =================
def format_match_banner(p):
    # Türkiye saatine çevir
    tr_time = datetime.fromisoformat(p.get("date")).astimezone(timezone(timedelta(hours=3)))
    time_str = tr_time.strftime("%d-%m %H:%M")
    flag_home = league_to_flag(p.get("home_country", ""))
    flag_away = league_to_flag(p.get("away_country", ""))
    bet_icon = "💡"
    if "Ev Sahibi" in p.get("bet",""):
        bet_icon = "🏠✅"
    elif "Deplasman" in p.get("bet",""):
        bet_icon = "✈️✅"
    elif "Beraberlik" in p.get("bet",""):
        bet_icon = "🤝"
    elif "ÜST" in p.get("bet","") or "ALT" in p.get("bet","") or "KG" in p.get("bet",""):
        bet_icon = "⚽"

    return (f"{flag_home} {p['home']} vs {flag_away} {p['away']}\n"
            f"🕒 Başlangıç: {time_str}\n"
            f"{bet_icon} Tahmin: {p.get('bet','Tahmin Yok')}\n"
            f"💰 Oran: {p.get('odds',1.5):.2f}\n")

def create_banner(title, picks):
    lines = [f"🤖 {title}", "━━━━━━━━━━━━━━━"]
    for p in picks:
        lines.append(format_match_banner(p))
    return "\n".join(lines)

# ================= JOB FONKSİYONLARI =================
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

            m.setdefault("home_country", m.get("country",""))
            m.setdefault("away_country", m.get("country",""))

            p = ai_predict(m)
            if p["confidence"] >= MIN_CONFIDENCE and p["odds"] >= MIN_ODDS:
                picks.append(p)
                mark_posted(m["id"], path=DB_FILE)

        if picks:
            text = create_banner("Günlük Kupon", picks)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info(f"daily_coupon: {len(picks)} tahmin gönderildi.")
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

            m.setdefault("home_country", m.get("country",""))
            m.setdefault("away_country", m.get("country",""))

            p = ai_predict(m)
            if p["confidence"] >= MIN_CONFIDENCE_VIP and p["odds"] >= MIN_ODDS:
                picks.append(p)
                mark_posted(m["id"], path=DB_FILE)

        if picks:
            text = create_banner("VIP Kupon", picks)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info(f"vip_coupon: {len(picks)} VIP tahmin gönderildi.")
        else:
            log.info("vip_coupon: uygun VIP maç yok")
    except Exception:
        log.exception("vip_coupon hata:")

async def live_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        live_matches = [m for m in matches if m.get("live")]
        picks = []

        for m in live_matches:
            m.setdefault("home_country", m.get("country",""))
            m.setdefault("away_country", m.get("country",""))
            p = ai_predict(m)
            if p.get("odds",1) >= MIN_ODDS:
                picks.append(p)

        if picks:
            text = create_banner("Canlı Maçlar", picks)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info(f"live_coupon: {len(picks)} canlı maç gönderildi.")
        else:
            log.info("live_coupon: uygun canlı maç yok")
    except Exception:
        log.exception("live_coupon hata:")

# ================= ADMIN COMMAND =================
async def test_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await daily_coupon_job(context)
    await update.message.reply_text("Test: Günlük kupon çalıştırıldı.")

async def test_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vip_coupon_job(context)
    await update.message.reply_text("Test: VIP kupon çalıştırıldı.")

async def test_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await live_coupon_job(context)
    await update.message.reply_text("Test: Canlı kupon çalıştırıldı.")

# ================= FASTAPI + TELEGRAM =================
fastapi_app = FastAPI()
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

telegram_app.add_handler(CommandHandler("test_daily", test_daily))
telegram_app.add_handler(CommandHandler("test_vip", test_vip))
telegram_app.add_handler(CommandHandler("test_live", test_live))

@fastapi_app.on_event("startup")
async def startup():
    init_db(DB_FILE)
    log.info("✅ Database initialized")
    jq = telegram_app.job_queue
    jq.run_repeating(daily_coupon_job, interval=3600*12, first=10)
    jq.run_repeating(vip_coupon_job, interval=3600*24, first=20)
    jq.run_repeating(live_coupon_job, interval=3600, first=30)
    await telegram_app.initialize()
    await telegram_app.start()
    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA Free APIs")

@fastapi_app.on_event("shutdown")
async def shutdown():
    await telegram_app.stop()
    log.info("Bot stopped")

@fastapi_app.post("/stakedrip")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8443)
