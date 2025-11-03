# ================== main.py — STAKEZONE AI ULTRA v10.0 ==================
import asyncio, logging
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn
import aiohttp

from db import init_db, DB_PATH, mark_posted, was_posted_recently
from prediction import ai_predict
from utils import league_to_flag, get_live_minute, get_live_events

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://yourdomain.com/stakedrip"
THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"
ODDS_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

SPORTS = [
    "soccer_epl", "soccer_la_liga", "soccer_bundesliga", "soccer_serie_a", "soccer_turkey_super_league",
    "soccer_uefa_champs_league", "soccer_brazil_serie_a", "soccer_japan_j_league", "soccer_usa_mls",
    "basketball_nba", "basketball_euroleague", "basketball_turkey_tbl"
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("stakezone")

def neon_banner(title, conf):
    return (
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n"
        "   ⚡ STAKEZONE AI ULTRA v10 ⚡\n"
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n\n"
        f"      {title}\n"
        f"   📅 {datetime.now(timezone(timedelta(hours=3))).strftime('%d %B %Y')}\n"
        f"   🔥 %{int(conf*100)} KAZANMA ŞANSI\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

async def get_live_odds(match, sport):
    params = {"apiKey": THE_ODDS_API_KEY, "regions": "eu", "markets": "h2h,totals,team_totals,player_props"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(ODDS_URL.format(sport=sport), params=params) as r:
                if r.status != 200: return 1.50
                data = await r.json()
                for game in data:
                    if match["home"] in game["home_team"] and match["away"] in game["away_team"]:
                        markets = game["bookmakers"][0]["markets"]
                        for m in markets:
                            if "totals" in m["key"] or "corners" in m["key"] or "cards" in m["key"]:
                                return max([o["price"] for o in m["outcomes"]], default=1.50)
    except: pass
    return 1.50

async def build_coupon(min_conf, title, is_live=False):
    matches = []
    async with aiohttp.ClientSession() as s:
        for sport in SPORTS:
            try:
                async with s.get(f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
                                params={"apiKey": THE_ODDS_API_KEY, "regions": "eu"}) as r:
                    if r.status == 200:
                        data = await r.json()
                        for g in data:
                            commence = g["commence_time"]
                            live_now = datetime.fromisoformat(commence.replace("Z","+00:00")) < datetime.now(timezone.utc)
                            if live_now == is_live:
                                matches.append({
                                    "id": g["id"],
                                    "home": g["home_team"],
                                    "away": g["away_team"],
                                    "date": commence,
                                    "sport": sport,
                                    "live": live_now,
                                    "home_country": g["home_team"].split()[-1],
                                    "away_country": g["away_team"].split()[-1]
                                })
            except: pass

    picks = []
    for m in matches:
        if was_posted_recently(m["id"], 24): continue
        p = await ai_predict(m)
picks.append((p["confidence"], p))   # ← confidence’e göre sırala!
        p["odds"] = await get_live_odds(p, m["sport"])
        if p["confidence"] >= min_conf and p["odds"] >= 1.20:
            picks.append((p["confidence"], p))
    if not picks: return None

    best = max(picks, key=lambda x: x[0])[1]   # ← EN YÜKSEK GÜVENİ SEÇ!
    mark_posted(best["id"])
    flag_h = league_to_flag(best.get("home_country"))
    flag_a = league_to_flag(best.get("away_country"))
    minute = f" ⚡ {get_live_minute(best)}'" if is_live else ""
    live = await get_live_events(best["id"]) if is_live else {"corners": 0, "cards": 0}

    text = (
        f"{neon_banner(title, best['confidence'])}\n"
        f"{flag_h} <b>{best['home']}</b> vs {flag_a} <b>{best['away']}</b>\n"
        f"🕒 <b>{minute or 'Bugün 20:00'}</b>\n"
        f"⚽ <b>{best['main_bet']}</b>\n"
        f"📐 <b>{best['corner_bet']}</b> (Ort: {best['corner_avg']})\n"
        f"{'' if not is_live else f'   ✅ Şu an: {live['corners']} korner'}\n"
        f"🟨 <b>{best['card_bet']}</b> (Ort: {best['card_avg']})\n"
        f"{'' if not is_live else f'   ✅ Şu an: {live['cards']} kart'}\n"
        f"💰 Oran: <b>{best['odds']:.2f}</b>\n"
        f"📊 AI GÜVEN: <b>%{int(best['confidence']*100)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 <i>TEK SITE STAKE! @stakedrip</i>"
    )
    return text

async def hourly_job(ctx): 
    text = await build_coupon(0.55, "CANLI KUPON", True)
    if text: await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

async def daily_job(ctx): 
    text = await build_coupon(0.60, "GÜNLÜK KUPON")
    if text: await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

async def vip_job(ctx): 
    text = await build_coupon(0.80, "VIP KUPON")
    if text: await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

async def test_hourly(u: Update, c): await hourly_job(c); await u.message.reply_text("⚡ CANLI TEST")
async def test_daily(u: Update, c): await daily_job(c); await u.message.reply_text("🏆 GÜNLÜK TEST")
async def test_vip(u: Update, c): await vip_job(c); await u.message.reply_text("🔥 VIP TEST")

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()
tg.add_handler(CommandHandler("hourly", test_hourly))
tg.add_handler(CommandHandler("daily", test_daily))
tg.add_handler(CommandHandler("vip", test_vip))

@app.on_event("startup")
async def start():
    init_db(DB_PATH)
    jq = tg.job_queue
    jq.run_repeating(hourly_job, 3600, first=10)
    jq.run_repeating(daily_job, 43200, first=20)
    jq.run_repeating(vip_job, 86400, first=30)
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("v10.0 – KORNER + KART CANLI ÇALIŞIYOR!")

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
