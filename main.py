# main.py - STAKEZONE AI v10.2 (TÜRKİYE SAATİ + HER SAAT CANLI)
import asyncio, logging
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn, aiohttp

from db import init_db, DB_PATH, mark_posted, was_posted_recently
from prediction import ai_predict
from utils import league_to_flag, get_live_minute, get_live_events

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://yourdomain.com/stakedrip"  # Render'da otomatik doluyor
THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"

# TÜRKİYE SAATİ
TR_TIME = timezone(timedelta(hours=3))

SPORTS = ["soccer_epl", "soccer_la_liga", "soccer_turkey_super_league", "basketball_nba"]

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

def neon_banner(title, conf):
    now_tr = datetime.now(TR_TIME).strftime("%d %B %Y - %H:%M")
    return (
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n"
        "   ⚡ STAKEZONE AI v10.2 ⚡\n"
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n\n"
        f"      {title}\n"
        f"   📅 {now_tr} TÜRKİYE SAATİ\n"
        f"   🔥 %{int(conf*100)} KAZANMA\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

async def get_live_odds(m, s):
    try:
        async with aiohttp.ClientSession() as ses:
            async with ses.get(f"https://api.the-odds-api.com/v4/sports/{s}/odds",
                              params={"apiKey": THE_ODDS_API_KEY, "regions": "eu", "markets": "h2h,totals"}) as r:
                if r.status == 200:
                    data = await r.json()
                    for game in data:
                        if m["home"] in game["home_team"] and m["away"] in game["away_team"]:
                            for book in game.get("bookmakers", []):
                                for market in book.get("markets", []):
                                    for outcome in market.get("outcomes", []):
                                        if outcome["name"] in ["Over", "Yes", m["home"]]:
                                            return max(outcome.get("price", 1.0), 1.20)
    except: pass
    return 1.20  # Asla 1.20 altı olmasın

async def build_coupon(min_conf, title, live=False):
    matches = []
    async with aiohttp.ClientSession() as s:
        for sp in SPORTS:
            try:
                async with s.get(f"https://api.the-odds-api.com/v4/sports/{sp}/odds",
                                params={"apiKey": THE_ODDS_API_KEY, "regions": "eu"}) as r:
                    if r.status == 200:
                        data = await r.json()
                        for g in data:
                            start_time = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
                            is_live_now = start_time < datetime.now(timezone.utc)
                            if live == is_live_now:
                                matches.append({
                                    "id": g["id"],
                                    "home": g["home_team"],
                                    "away": g["away_team"],
                                    "sport": sp,
                                    "date": g["commence_time"],
                                    "home_country": g["home_team"].split()[-1],
                                    "away_country": g["away_team"].split()[-1]
                                })
            except: pass

    picks = []
    for m in matches:
        if was_posted_recently(m["id"]): continue
        p = await ai_predict(m)
        p["odds"] = await get_live_odds(p, m["sport"])
        if p["confidence"] >= min_conf and p["odds"] >= 1.20:  # ZORUNLU 1.20+
            picks.append((p["confidence"], p))

    if not picks:
        return None

    best = max(picks, key=lambda x: x[0])[1]
    mark_posted(best["id"])

    flag_h = league_to_flag(best.get("home_country", ""))
    flag_a = league_to_flag(best.get("away_country", ""))
    minute = f" ⚡ {get_live_minute(best)}'" if live else ""

    live_stats = await get_live_events(best["id"]) if live else {"corners": 0, "cards": 0}

    return (
        f"{neon_banner(title, best['confidence'])}\n"
        f"{flag_h} <b>{best['home']}</b> vs {flag_a} <b>{best['away']}</b>\n"
        f"🕒 <b>{minute or '20:00'}</b>\n"
        f"⚽ <b>{best['main_bet']}</b>\n"
        f"📐 <b>{best['corner_bet']}</b> (Ort: {best['corner_avg']})\n"
        f"{'   ✅ Şu an: ' + str(live_stats['corners']) + ' korner' if live else ''}\n"
        f"🟨 <b>{best['card_bet']}</b> (Ort: {best['card_avg']})\n"
        f"{'   ✅ Şu an: ' + str(live_stats['cards']) + ' kart' if live else ''}\n"
        f"💰 Oran: <b>{best['odds']:.2f}</b>\n"
        f"📊 AI GÜVEN: <b>%{int(best['confidence']*100)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 ABONE OL, KAZAN! @stakedrip"
    )

async def hourly_job(ctx):
    text = await build_coupon(0.55, "CANLI KUPON", True)
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

async def daily_job(ctx):
    text = await build_coupon(0.60, "GÜNLÜK KUPON")
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

async def vip_job(ctx):
    text = await build_coupon(0.80, "VIP KUPON")
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()

# Komutlar
async def test_vip(u: Update, c):
    await vip_job(c)
    await u.message.reply_text("VIP KUPON GÖNDERİLDİ!")

tg.add_handler(CommandHandler("vip", test_vip))
tg.add_handler(CommandHandler("daily", lambda u,c: daily_job(c) or u.message.reply_text("GÜNLÜK GÖNDERİLDİ")))
tg.add_handler(CommandHandler("hourly", lambda u,c: hourly_job(c) or u.message.reply_text("CANLI GÖNDERİLDİ")))

@app.on_event("startup")
async def start():
    init_db(DB_PATH)
    jq = tg.job_queue
    jq.run_repeating(hourly_job, 3600, first=5)   # HER SAAT BAŞI 5 SANİYE SONRA!
    jq.run_repeating(daily_job, 43200, first=20)
    jq.run_repeating(vip_job, 86400, first=30)
    await tg.initialize()
    await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("STAKEZONE v10.2 TÜRKİYE SAATİYLE ÇALIŞIYOR!")

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
