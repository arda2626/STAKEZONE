# main.py — STAKEDRIP AI ULTRA (tek dosya çalıştırılabilir orchestrator)
import logging
from datetime import time as dt_time, timezone
from telegram.ext import Application
from db import init_db, DB_PATH, mark_posted, was_posted_recently
from fetch_matches import fetch_all_matches
from prediction import ai_predict
from messages import create_live_banner, create_daily_banner, create_vip_banner
from results import check_results
from utils import turkey_now

# ------------- CONFIG -------------
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
API_FOOTBALL_KEY = "3838237ec41218c2572ce541708edcfd"
DB_FILE = DB_PATH
MAX_LIVE_PICKS = 3
MIN_CONFIDENCE = 0.60
MIN_ODDS = 1.20

# ------------- LOGGING -------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("stakedrip")

# ------------- JOBS -------------
async def hourly_live_job(ctx):
    bot = ctx.bot
    try:
        try:
            matches = await fetch_all_matches(API_FOOTBALL_KEY) if API_FOOTBALL_KEY else await fetch_all_matches()
        except TypeError:
            matches = await fetch_all_matches()

        live = [m for m in matches if m.get("live") or m.get("is_live")]
        if not live:
            log.info("hourly_live: canlı maç yok")
            return

        chosen = []
        for m in live:
            if len(chosen) >= MAX_LIVE_PICKS:
                break
            eid = m.get("id") or m.get("idEvent") or m.get("event_id")
            if eid and was_posted_recently(eid, hours=24, path=DB_FILE):
                continue
            p = ai_predict(m)
            p.setdefault("home", m.get("home") or m.get("strHomeTeam"))
            p.setdefault("away", m.get("away") or m.get("strAwayTeam"))
            p.setdefault("league", m.get("league") or m.get("strLeague"))
            p.setdefault("odds", m.get("odds", 1.5))
            p.setdefault("confidence", p.get("confidence", 0.5))
            p.setdefault("bet", p.get("bet", "Ev Sahibi Kazanır"))
            p["minute"] = m.get("minute") or m.get("intRound") or m.get("strTime") or m.get("time")
            if p["odds"] >= MIN_ODDS and p["confidence"] >= MIN_CONFIDENCE:
                chosen.append((eid, p))

        if not chosen:
            log.info("hourly_live: uygun tahmin yok")
            return

        preds = [p for eid,p in chosen]
        text = create_live_banner(preds)
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        for eid,_ in chosen:
            if eid:
                mark_posted(eid, path=DB_FILE)
        log.info(f"hourly_live: {len(preds)} tahmin gönderildi.")
    except Exception:
        log.exception("hourly_live hata:")

async def daily_coupon_job(ctx):
    bot = ctx.bot
    try:
        try:
            matches = await fetch_all_matches(API_FOOTBALL_KEY) if API_FOOTBALL_KEY else await fetch_all_matches()
        except TypeError:
            matches = await fetch_all_matches()
        upcoming = [m for m in matches if not (m.get("live") or m.get("is_live"))]
        picks = []
        for m in upcoming:
            p = ai_predict(m)
            p.setdefault("home", m.get("home"))
            p.setdefault("away", m.get("away"))
            p.setdefault("odds", m.get("odds",1.5))
            p.setdefault("confidence", p.get("confidence",0.5))
            picks.append(p)
        chosen = sorted(picks, key=lambda x: x.get("confidence",0), reverse=True)[:3]
        if chosen:
            text = create_daily_banner(chosen)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info("daily_coupon: gönderildi.")
    except Exception:
        log.exception("daily_coupon hata:")

async def vip_coupon_job(ctx):
    bot = ctx.bot
    try:
        try:
            matches = await fetch_all_matches(API_FOOTBALL_KEY) if API_FOOTBALL_KEY else await fetch_all_matches()
        except TypeError:
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
            log.info("vip_coupon: gönderildi.")
    except Exception:
        log.exception("vip_coupon hata:")

async def results_job(ctx):
    bot = ctx.bot
    try:
        try:
            await check_results(bot)
        except TypeError:
            pass
    except Exception:
        log.exception("results_job hata:")

# ------------- SCHEDULE -------------
def schedule(app: Application):
    jq = app.job_queue
    jq.run_repeating(hourly_live_job, interval=3600, first=10, name="hourly_live")
    jq.run_repeating(daily_coupon_job, interval=3600*12, first=60, name="daily_coupon")
    jq.run_repeating(vip_coupon_job, interval=86400, first=120, name="vip_coupon")
    jq.run_daily(results_job, time=dt_time(hour=20, minute=0, tzinfo=timezone.utc), name="results_check")

# ------------- MAIN -------------
if __name__ == "__main__":
    init_db(DB_FILE)
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    schedule(app)
    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA")
    app.run_polling()  # tek satır, async yönetimi ve polling hataları ortadan kalktı
