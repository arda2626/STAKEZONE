# ================== main.py — STAKEDRIP AI ULTRA Webhook Free v5.15 ==================
import asyncio, logging
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler, JobQueue, ContextTypes
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn

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

# ================== EMOJİLER ==================
EMOJI = {
    "goal": "⚽",
    "win": "✅",
    "lose": "❌",
    "draw": "🤝",
    "clock": "🕒",
    "fire": "🔥",
    "ai": "🤖",
    "star": "⭐",
    "trend": "📈",
    "earth": "🌍",
    "light": "💡",
    "ding": "🔔",
}

EMOJI_MAP = {
    "Over 2.5": "🔥",
    "Under 2.5": "🧊",
    "BTTS": "⚽⚽",
    "Home Win": "🏠✅",
    "Away Win": "✈️✅",
    "Draw": "🤝",
    "Ev Sahibi Kazanır": "🏠✅",
    "Deplasman Kazanır": "✈️✅",
    "Beraberlik": "🤝",
    "KG VAR": "⚽",
    "Kart 3+": "🟥"
}

# ================== BAYRAK FONKSİYONU ==================
def country_to_flag(country_name):
    mapping = {
        "England": "🏴","Germany": "🇩🇪","Spain": "🇪🇸","Italy": "🇮🇹","France": "🇫🇷",
        "Turkey": "🇹🇷","Portugal": "🇵🇹","Netherlands": "🇳🇱","Belgium": "🇧🇪","Brazil": "🇧🇷",
        "Argentina": "🇦🇷","USA": "🇺🇸","Japan": "🇯🇵","Korea Republic": "🇰🇷"
    }
    return mapping.get(country_name, "🌍")

# ================== BANNER FONKSİYONLARI ==================
def format_match_line(match: dict) -> str:
    home_flag = country_to_flag(match.get("home_country",""))
    away_flag = country_to_flag(match.get("away_country",""))
    home = match.get("home","Ev Sahibi")
    away = match.get("away","Deplasman")
    prediction = match.get("bet","Tahmin Yok")
    emoji = EMOJI_MAP.get(prediction, "")
    odds = match.get("odds",1.5)

    # Başlangıç zamanı
    start_iso = match.get("date") or match.get("start_time")
    if start_iso:
        try:
            start_dt = datetime.fromisoformat(start_iso)
            start_str = start_dt.strftime("%d-%m %H:%M")
        except:
            start_str = "—"
    else:
        start_str = "—"

    lines = [
        f"{home_flag} {home} vs {away_flag} {away}",
        f"🕒 Başlangıç: {start_str}",
        f"{emoji} Tahmin: {prediction}" if emoji else f"💡 Tahmin: {prediction}",
        f"💰 Oran: {odds:.2f}"
    ]
    return "\n".join(lines)

def create_daily_banner(matches: list) -> str:
    if not matches:
        return f"{EMOJI['ai']} Günlük Kupon\nVeri bulunamadı ⏳"
    lines = [f"{EMOJI['ai']} Günlük Kupon", "━━━━━━━━━━━━━━━"]
    for match in matches:
        lines.append(format_match_line(match))
        lines.append("")
    return "\n".join(lines)

def create_vip_banner(matches: list) -> str:
    if not matches:
        return f"{EMOJI['fire']} VIP Kupon\nVeri bulunamadı ⏳"
    lines = [f"{EMOJI['fire']} VIP Kupon", "━━━━━━━━━━━━━━━"]
    for match in matches:
        lines.append(format_match_line(match))
        lines.append("")
    return "\n".join(lines)

def create_live_banner(matches: list) -> str:
    if not matches:
        return f"{EMOJI['trend']} Canlı Maçlar\nVeri bulunamadı ⏳"
    lines = [f"{EMOJI['trend']} Canlı Maçlar", "━━━━━━━━━━━━━━━"]
    for match in matches:
        lines.append(format_match_line(match))
        lines.append("")
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

            m.setdefault("home_country", m.get("country",""))
            m.setdefault("away_country", m.get("country",""))

            p = ai_predict(m)
            if p.get("confidence",0) < 0.6 or p.get("odds",1.5) < 1.2:
                continue
            p["home"] = m.get("home")
            p["away"] = m.get("away")
            p["odds"] = p.get("odds",1.5)
            p["date"] = m.get("date")
            p["home_country"] = m.get("home_country")
            p["away_country"] = m.get("away_country")
            picks.append((m["id"],p))

        chosen = [p for mid,p in picks]
        chosen = sorted(chosen, key=lambda x: x.get("confidence",0), reverse=True)
        if chosen:
            text = create_daily_banner(chosen)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            for mid,_ in picks:
                mark_posted(mid, path=DB_FILE)
            log.info(f"daily_coupon: {len(chosen)} tahmin gönderildi.")
        else:
            log.info("daily_coupon: uygun maç yok")
    except Exception:
        log.exception("daily_coupon hata:")

# VIP ve LIVE jobları da benzer şekilde güncellendi
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
            if p.get("confidence",0) < MIN_CONFIDENCE_VIP or p.get("odds",1.5) < MIN_ODDS:
                continue
            p["home"] = m.get("home")
            p["away"] = m.get("away")
            p["odds"] = p.get("odds",1.5)
            p["date"] = m.get("date")
            p["home_country"] = m.get("home_country")
            p["away_country"] = m.get("away_country")
            picks.append((m["id"],p))

        if picks:
            text = create_vip_banner([p for mid,p in picks])
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            for mid,_ in picks:
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
            m.setdefault("home_country", m.get("country",""))
            m.setdefault("away_country", m.get("country",""))

            p = ai_predict(m)
            p["home"] = m.get("home")
            p["away"] = m.get("away")
            p["odds"] = p.get("odds",1.5)
            p["date"] = m.get("date")
            p["home_country"] = m.get("home_country")
            p["away_country"] = m.get("away_country")
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

@fastapi_app.on_event("startup")
async def startup():
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
