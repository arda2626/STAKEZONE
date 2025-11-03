# main.py
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
WEBHOOK_URL = "https://yourdomain.com/stakedrip"
THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"

SPORTS = ["soccer_epl", "soccer_la_liga", "soccer_turkey_super_league", "basketball_nba"]

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

def neon_banner(title, conf):
    return f"⚡ STAKEZONE AI v10.1 ⚡\n{title}\n%{int(conf*100)} KAZANMA\n━━━━━━━━━━━━━━"

async def get_live_odds(m, s):
    async with aiohttp.ClientSession() as ses:
        async with ses.get(f"https://api.the-odds-api.com/v4/sports/{s}/odds", params={"apiKey": THE_ODDS_API_KEY, "regions": "eu"}) as r:
            if r.status == 200:
                data = await r.json()
                for g in data:
                    if m["home"] in g["home_team"] and m["away"] in g["away_team"]:
                        return 1.85
    return 1.5

async def build_coupon(min_conf, title, live=False):
    matches = []
    async with aiohttp.ClientSession() as s:
        for sp in SPORTS:
            async with s.get(f"https://api.the-odds-api.com/v4/sports/{sp}/odds", params={"apiKey": THE_ODDS_API_KEY, "regions": "eu"}) as r:
                if r.status == 200:
                    data = await r.json()
                    for g in data:
                        if (live == (datetime.fromisoformat(g["commence_time"].replace("Z","+00:00")) < datetime.now(timezone.utc))):
                            matches.append({"id": g["id"], "home": g["home_team"], "away": g["away_team"], "sport": sp, "date": g["commence_time"]})

    picks = []
    for m in matches:
        if was_posted_recently(m["id"]): continue
        p = await ai_predict(m)
        p["odds"] = await get_live_odds(p, m["sport"])
        if p["confidence"] >= min_conf and p["odds"] >= 1.2:
            picks.append((p["confidence"], p))

    if not picks: return None
    best = max(picks, key=lambda x: x[0])[1]
    mark_posted(best["id"])

    flag_h = league_to_flag(best["home"].split()[-1])
    flag_a = league_to_flag(best["away"].split()[-1])
    minute = f" ⚡ {get_live_minute(best)}'" if live else ""

    return (
        f"{neon_banner(title, best['confidence'])}\n"
        f"{flag_h} <b>{best['home']}</b> vs {flag_a} <b>{best['away']}</b>\n"
        f"🕒 <b>{minute or '20:00'}</b>\n"
        f"⚽ <b>{best['main_bet']}</b>\n"
        f"📐 <b>{best['corner_bet']}</b>\n"
        f"🟨 <b>{best['card_bet']}</b>\n"
        f"💰 <b>{best['odds']:.2f}</b> │ AI: <b>%{int(best['confidence']*100)}</b>\n"
        "ABONE OL! @stakedrip"
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
tg.add_handler(CommandHandler("vip", lambda u,c: vip_job(c) or u.message.reply_text("VIP GÖNDERİLDİ")))

@app.on_event("startup")
async def go():
    init_db(DB_PATH)
    jq = tg.job_queue
    jq.run_repeating(hourly_job, 3600, first=10)
    jq.run_repeating(daily_job, 43200, first=20)
    jq.run_repeating(vip_job, 86400, first=30)
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("BOT ÇALIŞIYOR!")

@app.post("/stakedrip")
async def wh(r: Request):
    up = Update.de_json(await r.json(), tg.bot)
    await tg.update_queue.put(up)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
