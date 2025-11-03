# ================== main.py — STAKEDRIP AI ULTRA Webhook-Free v5.19 ==================
import asyncio, logging
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn
import aiohttp

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

THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"
THE_ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("stakedrip")

# ================== UTILS =================
def turkey_time(utc_time_str):
    try:
        if not utc_time_str:
            return "—"
        dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        tr_time = dt.astimezone(timezone(timedelta(hours=3)))
        return tr_time
    except Exception:
        return "—"

def format_match_line(match):
    start_time = turkey_time(match.get("date"))
    start_time_str = start_time.strftime("%d-%m %H:%M") if isinstance(start_time, datetime) else "—"
    flag_home = league_to_flag(match.get("home_country", ""))
    flag_away = league_to_flag(match.get("away_country", ""))
    emoji_map = {
        "ÜST 2.5":"🔥", "ALT 2.5":"🧊", "KG VAR":"⚽", "Home Win":"🏠✅",
        "Away Win":"✈️✅","Draw":"🤝"
    }
    emoji = emoji_map.get(match.get("bet"), "💡")
    return (
        f"{flag_home} {match['home']} vs {flag_away} {match['away']}\n"
        f"🕒 Başlangıç: {start_time_str}\n"
        f"{emoji} Tahmin: {match.get('bet','Tahmin Yok')}\n"
        f"💰 Oran: {match.get('odds',1.5):.2f}"
    )

def create_banner(title, matches):
    if not matches:
        return f"🤖 {title}\nVeri bulunamadı ⏳"
    lines = [f"🤖 {title}", "━━━━━━━━━━━━━━━"]
    for m in matches:
        lines.append(format_match_line(m))
    return "\n\n".join(lines)

# ================= FETCH ODDS =================
async def fetch_odds(match):
    sport_map = {"futbol": "soccer_epl", "basket": "basketball_nba", "tenis": "tennis_atp"}
    sport = sport_map.get(match.get("sport", "futbol").lower(), "soccer_epl")
    params = {"apiKey": THE_ODDS_API_KEY, "regions": "eu", "markets": "h2h,spreads,totals"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(THE_ODDS_API_URL.format(sport=sport), params=params) as r:
                if r.status != 200:
                    log.warning(f"{sport} fetch failed: {r.status}")
                    match["odds"] = match.get("odds", 1.5)
                    return
                data = await r.json()
                home = match.get("home", "").lower().replace(" ", "")
                away = match.get("away", "").lower().replace(" ", "")
                for d in data:
                    h = d.get("home_team", "").lower().replace(" ", "")
                    a = d.get("away_team", "").lower().replace(" ", "")
                    if home in h or away in a or h in home or a in away:
                        books = d.get("bookmakers", [])
                        if books and books[0].get("markets"):
                            outcomes = books[0]["markets"][0].get("outcomes", [])
                            if outcomes:
                                prices = [o.get("price", 1.5) for o in outcomes if isinstance(o.get("price", 0), (int, float))]
                                if prices:
                                    match["odds"] = max(prices)
                                    return
        except Exception as e:
            log.warning(f"Odds fetch failed: {e}")

    match["odds"] = match.get("odds", 1.5)

# ================= JOBS =================
async def process_matches(matches, min_conf=0.6):
    picks = []
    now = datetime.now(timezone.utc)
    for m in matches:
        try:
            match_time = datetime.fromisoformat(m.get("date").replace("Z", "+00:00"))
            if match_time.tzinfo is None:
                match_time = match_time.replace(tzinfo=timezone.utc)
        except:
            continue
        if match_time < now or was_posted_recently(m["id"], hours=24, path=DB_FILE):
            continue
        m.setdefault("home_country", m.get("country", ""))
        m.setdefault("away_country", m.get("country", ""))
        p = ai_predict(m)
        await fetch_odds(p)
        if p.get("confidence", 0) >= min_conf and p.get("odds", 1.5) >= MIN_ODDS:
            picks.append((m["id"], p))
    return picks

async def daily_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        upcoming = [m for m in matches if not m.get("live")]
        picks = await process_matches(upcoming, MIN_CONFIDENCE)
        chosen = sorted([p for mid, p in picks], key=lambda x: x.get("confidence", 0), reverse=True)
        if chosen:
            text = create_banner("Günlük Kupon", chosen)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            for mid, _ in picks:
                mark_posted(mid, path=DB_FILE)
            log.info(f"daily_coupon: {len(chosen)} tahmin gönderildi.")
    except Exception:
        log.exception("daily_coupon hata:")

async def vip_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        upcoming = [m for m in matches if not m.get("live")]
        picks = await process_matches(upcoming, MIN_CONFIDENCE_VIP)
        chosen = sorted([p for mid, p in picks], key=lambda x: x.get("confidence", 0), reverse=True)
        if chosen:
            text = create_banner("VIP Kupon", chosen)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            for mid, _ in picks:
                mark_posted(mid, path=DB_FILE)
            log.info(f"vip_coupon: {len(chosen)} tahmin gönderildi.")
    except Exception:
        log.exception("vip_coupon hata:")

async def live_coupon_job(ctx: ContextTypes.DEFAULT_TYPE):
    """
    Canlı maçlardan en fazla 3 adet seçip gönderir.
    Seçim: confidence yüksekten düşüğe, odds >= MIN_ODDS (ai_predict+fetch_odds ile ayarlanır).
    Bu fonksiyonun dışındaki davranışlar (db, webhook, diğer joblar) bozulmaz.
    """
    bot = ctx.bot
    try:
        matches = await fetch_all_matches()
        live = [m for m in matches if m.get("live")]
        picks = []
        for m in live:
            m.setdefault("home_country", m.get("country", ""))
            m.setdefault("away_country", m.get("country", ""))
            p = ai_predict(m)
            await fetch_odds(p)
            # canlı tahminlerde confidence kontrolü istemiyorsan burayı değiştir. Şu an sadece odds filtresi uygulanıyor.
            if p.get("odds", 1.5) >= MIN_ODDS:
                picks.append(p)

        if picks:
            # confidence'a göre sırala ve en fazla 3 al
            top_picks = sorted(picks, key=lambda x: x.get("confidence", 0), reverse=True)[:3]
            text = create_banner("Canlı Maçlar (Top 3)", top_picks)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info(f"live_coupon: {len(top_picks)} canlı maç gönderildi (top 3 seçildi).")
    except Exception:
        log.exception("live_coupon hata:")

# ================= COMMANDS =================
async def test_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await daily_coupon_job(ctx)
    await update.message.reply_text("Test: Günlük kupon çalıştırıldı.")

async def test_vip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await vip_coupon_job(ctx)
    await update.message.reply_text("Test: VIP kupon çalıştırıldı.")

async def test_live(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await live_coupon_job(ctx)
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

    # Webhook kontrolü — sadece gerekirse set et
    try:
        info = await telegram_app.bot.get_webhook_info()
        if info.url and "yourdomain.com" not in info.url:
            log.info("Webhook zaten kayıtlı, atlandı.")
        else:
            await telegram_app.bot.set_webhook(WEBHOOK_URL)
            log.info(f"Webhook set edildi: {WEBHOOK_URL}")
    except Exception as e:
        log.warning(f"Webhook kontrol hatası: {e}")

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
