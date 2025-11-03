# ================== main.py — STAKEDRIP AI ULTRA Webhook Free v5.15 ==================
import asyncio, logging
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn

from db import init_db, DB_PATH, mark_posted, was_posted_recently
from fetch_matches_free import fetch_all_matches
from prediction import ai_predict
from utils import league_to_flag

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

# ================== BANNER FONKSİYONLARI =================
EMOJI_MAP = {
    "ÜST 2.5": "🔥",
    "ALT 2.5": "🧊",
    "KG VAR": "⚽",
    "1.5 ÜST": "🔥",
    "3.5 ÜST": "🔥",
    "Korner ÜST 8.5": "⚡",
    "Kart 3+": "🟥",
    "Ev Sahibi Kazanır": "🏠✅",
    "Deplasman Kazanır": "✈️✅",
    "Beraberlik": "🤝",
    "Favori Kazanır": "⭐",
    "Tie-break Var": "🎾",
    "Toplam Sayı ÜST 212.5": "🔥",
    "Toplam Sayı ALT 212.5": "🧊",
    "Maç 3. Sete Gider": "🎾",
}

def format_match_line(p):
    home_flag = league_to_flag(p.get("home_league",""))
    away_flag = league_to_flag(p.get("away_league",""))

    bet = p.get("bet","Tahmin Yok")
    emoji = EMOJI_MAP.get(bet, "💡")

    match_time_str = p.get("date")
    if match_time_str:
        try:
            dt_utc = datetime.fromisoformat(match_time_str)
            dt_tr = dt_utc + timedelta(hours=3)
            time_display = dt_tr.strftime("%d-%m %H:%M")
        except Exception:
            time_display = match_time_str
    else:
        time_display = "—"

    odds = p.get("odds", 1.5)
    return f"{home_flag} {p['home']} vs {away_flag} {p['away']} | {emoji} {bet} | {odds:.2f} | 🕒 {time_display}"

def create_daily_banner(picks):
    if not picks:
        return "<b>Günlük Kupon</b>\nVeri bulunamadı ⏳"
    lines = ["<b>Günlük Kupon</b>", "━━━━━━━━━━━━━━━"]
    for p in picks:
        lines.append(format_match_line(p))
    return "\n".join(lines)

def create_vip_banner(picks):
    if not picks:
        return "<b>VIP Kupon</b>\nVeri bulunamadı ⏳"
    lines = ["<b>VIP Kupon</b>", "━━━━━━━━━━━━━━━"]
    for p in picks:
        lines.append(format_match_line(p))
    return "\n".join(lines)

def create_live_banner(picks):
    if not picks:
        return "<b>Canlı Maçlar</b>\nVeri bulunamadı ⏳"
    lines = ["<b>Canlı Maçlar</b>", "━━━━━━━━━━━━━━━"]
    for p in picks:
        lines.append(format_match_line(p))
    return "\n".join(lines)

# ================= JOB FUNCTIONS =================
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

            p = ai_predict(m)
            p.setdefault("home_league", m.get("league",""))
            p.setdefault("away_league", m.get("league",""))
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

            p = ai_predict(m)
            p.setdefault("home_league", m.get("league",""))
            p.setdefault("away_league", m.get("league",""))
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
            p = ai_predict(m)
            p.setdefault("home_league", m.get("league",""))
            p.setdefault("away_league", m.get("league",""))
            p.setdefault("date", m.get("date"))

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

# ================= ADMIN COMMAND =================
async def test_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await daily_coupon_job(context)
    await update.message.reply_text("Test: Günlük kupon çalıştırıldı.")

async def test_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vip_coupon_job(context)
    await update.message.reply_text("Test: VIP kupon çalıştırıldı.")

async def test_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await hourly_live_job(context)
    await update.message.reply_text("Test: Canlı maç kuponu çalıştırıldı.")

# ================= FASTAPI + TELEGRAM =================
fastapi_app = FastAPI()
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

telegram_app.add_handler(CommandHandler("test_daily", test_daily))
telegram_app.add_handler(CommandHandler("test_vip", test_vip))
telegram_app.add_handler(CommandHandler("test_live", test_live))

# Lifespan ile startup/shutdown
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(DB_FILE)
    log.info("✅ Database initialized")

    jq: JobQueue = telegram_app.job_queue
    jq.run_repeating(daily_coupon_job, interval=3600*12, first=10, name="daily_coupon")
    jq.run_repeating(vip_coupon_job, interval=3600*24, first=20, name="vip_coupon")
    jq.run_repeating(hourly_live_job, interval=3600, first=30, name="hourly_live")

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    log.info(f"Webhook set to {WEBHOOK_URL}")
    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA Free APIs")
    try:
        yield
    finally:
        await telegram_app.bot.delete_webhook()
        await telegram_app.stop()
        log.info("Bot stopped")

fastapi_app.router.lifespan_context = lifespan

@fastapi_app.post(WEBHOOK_PATH)
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8443)
