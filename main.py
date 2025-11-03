# ================== main.py — STAKEZONE AI ULTRA v6.0 ==================
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
from utils import league_to_flag, get_live_minute

# ================= CONFIG =================
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://yourdomain.com/stakedrip"

THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"
ODDS_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("stakezone")

# ================= UTILS =================
def tr_time(utc):
    try:
        dt = datetime.fromisoformat(utc.replace("Z", "+00:00"))
        tr = dt.astimezone(timezone(timedelta(hours=3)))
        today = datetime.now(timezone(timedelta(hours=3))).date()
        tomorrow = today + timedelta(days=1)
        if tr.date() == today: day = "Bugün"
        elif tr.date() == tomorrow: day = "Yarın"
        else: day = ["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][tr.weekday()]
        return f"{day} {tr.strftime('%H:%M')}", tr
    except: return "—", None

def banner(title):
    return (
        "╭───────────────╮\n"
        f"│  🤖 {title}  │\n"
        "╰───────────────╯\n"
        f"📅 {datetime.now(timezone(timedelta(hours=3))).strftime('%d %B %Y')}\n"
        "━━━━━━━━━━━━━━━━━"
    )

# ================= ORAN ÇEKME =================
async def get_live_odds(match):
    sport = {"futbol":"soccer", "basket":"basketball_nba", "tenis":"tennis"}.get(match.get("sport","futbol").lower(),"soccer")
    params = {"apiKey": THE_ODDS_API_KEY, "regions": "eu", "markets": "h2h,totals", "oddsFormat": "decimal"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(ODDS_URL.format(sport=sport), params=params) as r:
                if r.status != 200: return 1.5
                data = await r.json()
                for event in data:
                    if match["home"] in event["home_team"] or match["away"] in event["away_team"]:
                        odds = event["bookmakers"][0]["markets"][0]["outcomes"]
                        return max([o["price"] for o in odds], default=1.5)
    except: pass
    return 1.5

# ================= KUPON OLUŞTUR =================
async def build_coupon(matches, min_conf, title, is_live=False):
    picks = []
    for m in matches:
        if was_posted_recently(m["id"], 24): continue
        p = ai_predict(m)
        p["odds"] = await get_live_odds(p)
        if p.get("confidence",0) >= min_conf and p.get("odds",0) >= 1.20:
            picks.append((p["confidence"], p))
    if not picks: return None
    picks.sort(reverse=True)
    best = picks[0][1]
    mark_posted(best.get("id") or m["id"])

    flag_h = league_to_flag(best.get("home_country",""))
    flag_a = league_to_flag(best.get("away_country",""))
    bet_emoji = {"ÜST 2.5":"🔥","ALT 2.5":"🧊","KG VAR":"⚽","Home Win":"🏠","Away Win":"✈️","Draw":"🤝"}.get(best["bet"],"💡")
    minute = f" ⚡ {get_live_minute(best)}'" if is_live else ""

    text = (
        f"{banner(title)}\n\n"
        f"{flag_h} <b>{best['home']}</b> vs {flag_a} <b>{best['away']}</b>\n"
        f"🕒 <b>{tr_time(best['date'])[0]}{minute}</b>\n"
        f"{bet_emoji} <b>{best['bet']}</b>\n"
        f"💰 Oran: <b>{best['odds']:.2f}</b>\n"
        f"📊 AI Güven: <b>%{int(best['confidence']*100)}</b>\n"
        "┗━━━━━━━━━━━━━━━┛\n"
        "🚀 <i>STAKEZONE AI ULTRA</i>"
    )
    return text

# ================= JOBS =================
async def hourly_job(ctx):
    matches = await fetch_all_matches()
    live = [m for m in matches if m.get("live")]
    if live:
        text = await build_coupon(live, 0.55, "CANLI KUPON", True)
        if text: await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

async def daily_job(ctx):
    matches = await fetch_all_matches()
    upcoming = [m for m in matches if not m.get("live")]
    text = await build_coupon(upcoming, 0.60, "GÜNLÜK KUPON")
    if text: await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

async def vip_job(ctx):
    matches = await fetch_all_matches()
    upcoming = [m for m in matches if not m.get("live")]
    text = await build_coupon(upcoming, 0.80, "VIP KUPON")
    if text: await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

# ================= COMMANDS =================
async def test_hourly(u: Update, c): await hourly_job(c); await u.message.reply_text("Canlı test OK")
async def test_daily(u: Update, c): await daily_job(c); await u.message.reply_text("Günlük test OK")
async def test_vip(u: Update, c): await vip_job(c); await u.message.reply_text("VIP test OK")

# ================= APP =================
app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()
tg.add_handler(CommandHandler("hourly", test_hourly))
tg.add_handler(CommandHandler("daily", test_daily))
tg.add_handler(CommandHandler("vip", test_vip))

@app.on_event("startup")
async def start():
    init_db(DB_PATH)
    jq = tg.job_queue
    jq.run_repeating(hourly_job, interval=3600, first=30)      # her saat
    jq.run_repeating(daily_job, interval=43200, first=60)      # 12 saatte bir
    jq.run_repeating(vip_job, interval=86400, first=120)      # 24 saatte bir
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("STAKEZONE AI ULTRA v6.0 BAŞLATILDI")

@app.on_event("shutdown")
async def stop():
    await tg.bot.delete_webhook(); await tg.stop()

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
