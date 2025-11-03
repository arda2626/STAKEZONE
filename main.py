# main.py — STAKEDRIP AI ULTRA v5.1 (Main entry)
import asyncio
import logging
import inspect
from datetime import datetime, timezone
from telegram import Bot

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("stakedrip")

# --- CONFIG (not env-based by user request; replace with your keys) ---
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"   # replace if needed
CHANNEL_ID = "@stakedrip"                                         # or channel id like -100....
API_FOOTBALL_KEY = "3838237ec41218c2572ce541708edcfd"             # replace with your API-Football key

# Limits
MAX_LIVE_PICKS = 3
MIN_CONFIDENCE = 0.65

# --- Try to import project modules (be tolerant if names differ) ---
# Expected modules (you already have these in repo): fetch_matches, prediction, messages, scheduler, results
fetch_all_matches = None
ai_predict = None
create_live_banner = None
create_daily_banner = None
create_vip_banner = None
schedule_jobs = None
check_results = None

# fetch_all_matches
try:
    from fetch_matches import fetch_all_matches as _fetch_all_matches
    fetch_all_matches = _fetch_all_matches
    log.debug("Imported fetch_all_matches from fetch_matches.py")
except Exception as e:
    log.warning(f"fetch_matches module not found or import error: {e}")

# prediction: try ai_predict then ai_for_match
try:
    from prediction import ai_predict as _ai_predict
    ai_predict = _ai_predict
    log.debug("Imported ai_predict from prediction.py")
except Exception:
    try:
        from prediction import ai_for_match as _ai_for_match
        ai_predict = _ai_for_match
        log.debug("Imported ai_for_match as ai_predict from prediction.py")
    except Exception as e:
        log.warning(f"prediction module import error: {e}")

# messages: banner creators
try:
    from messages import create_live_banner, create_daily_banner, create_vip_banner
    log.debug("Imported banners from messages.py")
except Exception as e:
    log.warning(f"messages module not found or import error: {e}")

# scheduler (optional)
try:
    from scheduler import schedule_jobs
    log.debug("Imported schedule_jobs from scheduler.py")
except Exception:
    schedule_jobs = None

# results checker
try:
    from results import check_results as _check_results
    check_results = _check_results
except Exception:
    check_results = None

# --- Safe fallback implementations if missing (keeps original behavior where possible) ---
async def _fallback_fetch_all_matches(api_key=None):
    """
    Minimal fallback — returns empty list so main won't crash.
    You should replace this by implementing fetch_matches.fetch_all_matches.
    """
    log.warning("Using fallback fetch_all_matches (returns empty). Implement fetch_matches.fetch_all_matches for full functionality.")
    return []

def _fallback_ai_predict(match):
    """
    Minimal AI fallback producing required keys: confidence, sport, odds, home, away, id
    """
    from random import uniform
    prob = round(uniform(0.55, 0.85), 2)
    return {
        "id": match.get("id"),
        "home": match.get("home"),
        "away": match.get("away"),
        "sport": match.get("sport", "futbol"),
        "confidence": prob,
        "odds": max(match.get("odds", 1.5), 1.2),
        "meta": {}
    }

def _fallback_create_live_banner(predictions):
    header = "\n".join(["═"*38, "💎 STAKEDRIP LIVE PICKS 💎", "🔥 AI CANLI TAHMİN (LIVE) 🔥", "═"*38, ""])
    lines = [header]
    for i,p in enumerate(predictions, 1):
        flag = p.get("league_flag","🏟️")
        minute = p.get("minute") or ""
        lines.append(f"{i}. {flag} {p.get('league','')} {minute}")
        lines.append(f"   {p.get('home','-')} vs {p.get('away','-')}")
        lines.append(f"   Tahmin: {p.get('bet', p.get('prediction','-'))} • Oran: {p.get('odds')} • AI: %{int(p.get('confidence',0)*100)}")
        lines.append("")
    lines.append(f"🔔 Minimum oran: 1.20 • Maks: 3 maç")
    return "\n".join(lines)

def _fallback_create_daily_banner(predictions):
    header = "\n".join(["═"*38, "💰 GÜNLÜK KUPON (24 SAAT) 💰", " AI Tahminleri ", "═"*38, ""])
    lines = [header]
    total = 1.0
    for p in predictions:
        lines.append(f"{p.get('home','-')} vs {p.get('away','-')} • {p.get('bet',p.get('prediction','-'))} @ {p.get('odds')}")
        total *= p.get('odds',1.0)
    lines.append(f"TOPLAM ORAN: {round(total,2)}")
    return "\n".join(lines)

def _fallback_create_vip_banner(predictions):
    header = "\n".join(["═"*38, "💼 KASA KUPONU (VIP) 💼", " Güvenli Kombine ", "═"*38, ""])
    lines = [header]
    total = 1.0
    for p in predictions:
        lines.append(f"{p.get('home','-')} vs {p.get('away','-')} • {p.get('bet',p.get('prediction','-'))} @ {p.get('odds')}")
        total *= p.get('odds',1.0)
    lines.append(f"POTANSİYEL: {round(total,2)}")
    return "\n".join(lines)

# Assign fallbacks where needed
if fetch_all_matches is None:
    fetch_all_matches = _fallback_fetch_all_matches
if ai_predict is None:
    ai_predict = _fallback_ai_predict
if create_live_banner is None:
    create_live_banner = _fallback_create_live_banner
if create_daily_banner is None:
    create_daily_banner = _fallback_create_daily_banner
if create_vip_banner is None:
    create_vip_banner = _fallback_create_vip_banner

# --- Helper to call fetch_all_matches whether it expects an api_key param or not ---
async def _call_fetch_all_matches():
    try:
        if inspect.iscoroutinefunction(fetch_all_matches):
            # detect if function accepts an api key
            if fetch_all_matches.__code__.co_argcount >= 1:
                return await fetch_all_matches(API_FOOTBALL_KEY)
            else:
                return await fetch_all_matches()
        else:
            # synchronous function
            if fetch_all_matches.__code__.co_argcount >= 1:
                return fetch_all_matches(API_FOOTBALL_KEY)
            else:
                return fetch_all_matches()
    except Exception as e:
        log.exception(f"Error calling fetch_all_matches: {e}")
        return []

# --- Core sending functions (designed to accept Bot and use module functions) ---
async def send_hourly_predictions(bot: Bot):
    try:
        matches = await _call_fetch_all_matches()
        if not matches:
            log.info("No matches returned by fetch_all_matches.")
            return
        # prefer live matches first
        live_matches = [m for m in matches if m.get("live") or m.get("is_live")]  # tolerate different key names
        if not live_matches:
            # also allow upcoming matches whose start_time <= now
            live_matches = [m for m in matches if (m.get("start_time") and m.get("start_time") <= datetime.now(timezone.utc))]
        top_live = live_matches[:MAX_LIVE_PICKS]

        predictions = []
        for m in top_live:
            p = ai_predict(m)
            # ensure confidence key exists
            conf = p.get("confidence", p.get("prob", 0.5))
            p["confidence"] = conf
            # optional: fill home/away/odds if missing
            p.setdefault("home", m.get("home"))
            p.setdefault("away", m.get("away"))
            p.setdefault("odds", m.get("odds", 1.5))
            p.setdefault("league", m.get("league"))
            if p["confidence"] >= MIN_CONFIDENCE and p.get("odds",1.2) >= 1.2:
                predictions.append(p)

        if not predictions:
            log.info("No live predictions meeting confidence/odds thresholds.")
            return

        banner = create_live_banner(predictions)
        await bot.send_message(chat_id=CHANNEL_ID, text=banner, parse_mode="HTML")
        log.info(f"✅ Sent {len(predictions)} live AI predictions.")
    except Exception as e:
        log.exception(f"send_hourly_predictions error: {e}")

async def send_daily_coupon(bot: Bot):
    try:
        matches = await _call_fetch_all_matches()
        if not matches:
            log.info("No matches returned for daily.")
            return
        upcoming = [m for m in matches if not m.get("live")]
        picks = []
        for m in upcoming:
            p = ai_predict(m)
            p.setdefault("odds", m.get("odds",1.5))
            p.setdefault("home", m.get("home"))
            p.setdefault("away", m.get("away"))
            picks.append(p)
        chosen = sorted(picks, key=lambda x: x.get("confidence",0), reverse=True)[:3]
        text = create_daily_banner(chosen)
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        log.info("📅 Daily coupon sent.")
    except Exception as e:
        log.exception(f"send_daily_coupon error: {e}")

async def send_vip_coupon(bot: Bot):
    try:
        matches = await _call_fetch_all_matches()
        if not matches:
            log.info("No matches returned for vip.")
            return
        picks = [ai_predict(m) for m in matches]
        vip = sorted(picks, key=lambda x: x.get("confidence",0), reverse=True)[:3]
        text = create_vip_banner(vip)
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        log.info("💰 VIP (kasa) coupon sent.")
    except Exception as e:
        log.exception(f"send_vip_coupon error: {e}")

# --- Helper: schedule fallback using telegram.ext.Application job queue if schedule_jobs not provided ---
async def _fallback_schedule_with_app(bot: Bot, hourly_fn, daily_fn, vip_fn, results_fn=None):
    """
    If user didn't supply scheduler.schedule_jobs, use the Telegram Application job queue to schedule repeating tasks.
    """
    try:
        from telegram.ext import Application
    except Exception as e:
        log.warning(f"telegram.ext not available for fallback scheduling: {e}")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    jq = app.job_queue

    # wrap coroutine functions to pass Bot object as ctx.bot
    async def _hourly_job(ctx):
        await hourly_fn(bot)

    async def _daily_job(ctx):
        await daily_fn(bot)

    async def _vip_job(ctx):
        await vip_fn(bot)

    # Schedule: hourly live, daily coupon every 12 hours, vip once per day, results check every 5 minutes
    jq.run_repeating(_hourly_job, interval=3600, first=10, name="hourly_live")
    jq.run_repeating(_daily_job, interval=3600*12, first=30, name="daily_coupon")
    jq.run_repeating(_vip_job, interval=86400, first=60, name="vip_coupon")
    if results_fn:
        async def _results_job(ctx):
            try:
                await results_fn(bot)
            except Exception as e:
                log.debug(f"results job error: {e}")
        jq.run_repeating(_results_job, interval=300, first=45, name="results_check")

    # start polling in background (non-blocking)
    log.info("Starting Application (job queue) for scheduling fallback jobs.")
    await app.initialize()
    await app.start()
    # app will run until program exit; we don't call app.run_polling() here because main handles loop
    return app

# --- MAIN ---
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    log.info("🚀 STAKEDRIP AI ULTRA v5.1 started.")

    # 1) run one immediate hourly job (startup)
    await send_hourly_predictions(bot)

    # 2) schedule jobs: prefer schedule_jobs from scheduler.py if present
    if schedule_jobs:
        try:
            if inspect.iscoroutinefunction(schedule_jobs):
                await schedule_jobs(bot, send_hourly_predictions, send_daily_coupon, send_vip_coupon, check_results)
            else:
                schedule_jobs(bot, send_hourly_predictions, send_daily_coupon, send_vip_coupon, check_results)
            log.info("Jobs scheduled via scheduler.schedule_jobs")
        except Exception as e:
            log.exception(f"Error running schedule_jobs: {e}")
            # fallback to application-based scheduling
            await _fallback_schedule_with_app(bot, send_hourly_predictions, send_daily_coupon, send_vip_coupon, check_results)
    else:
        # fallback: use telegram.ext.Application job queue to schedule repeating jobs
        await _fallback_schedule_with_app(bot, send_hourly_predictions, send_daily_coupon, send_vip_coupon, check_results)

    # keep process alive
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.warning("Bot stopped manually.")
