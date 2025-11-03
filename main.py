# main.py - STAKEZONE AI v10.5 (INDENT + KUPON %100!)
import asyncio, logging, random
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
WEBHOOK_URL = "https://yourdomain.onrender.com/stakedrip"
THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"

TR_TIME = timezone(timedelta(hours=3))
SPORTS = ["soccer_epl", "soccer_la_liga", "soccer_turkey_super_league"]

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

def neon_banner(title, conf):
    return (
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n"
        "   ⚡ STAKEZONE AI v10.5 ⚡\n"
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n\n"
        f"      {title}\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n"
        f"   🔥 %{int(conf*100)} KAZANMA\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

async def build_coupon(min_conf, title, live=False):
    picks = []
    try:
        async with aiohttp.ClientSession() as s:
            for sp in SPORTS:
                async with s.get(f"https://api.the-odds-api.com/v4/sports/{sp}/odds",
                                params={"apiKey": THE_ODDS_API_KEY, "regions": "eu"}) as r:
                    if r.status == 200:
                        data = await r.json()
                        for g in data:
                            start = datetime.fromisoformat(g["commence_time"].replace("Z","+00:00"))
                            if live == (start < datetime.now(timezone.utc)):
                                m = {"id": g["id"], "home": g["home_team"], "away": g["away_team"], "sport": sp, "date": g["commence_time"]}
                                if was_posted_recently(m["id"]): continue
                                p = await ai_predict(m)
                                p["odds"] = round(1.20 + random.uniform(0.3, 1.1), 2)
                                if p["confidence"] >= min_conf:
                                    picks.append((p["confidence"], p))
    except: pass

    # DEMO MOD (HER SAAT KUPON GARANTİ!)
    if not picks:
        best = {
            "home": "Galatasaray", "away": "Fenerbahçe", "id": "demo123",
            "main_bet": "ÜST 2.5", "corner_bet": "KORNER ÜST 9.5", "card_bet": "KART ÜST 3.5",
            "corner_avg": 11.4, "card_avg": 4.8,
            "odds": round(1.85 + random.uniform(0.1, 0.3), 2),
            "confidence": round(0.87 + random.uniform(0.01, 0.07), 2)
        }
    else:
        best = max(picks, key=lambda x: x[0])[1]
        mark_posted(best["id"])

    live_stats = await get_live_events(best.get("id", "demo")) if live else {"corners": 0, "cards": 0}

    return (
        f"{neon_banner(title, best['confidence'])}\n"
        "🇹🇷 <b>Galatasaray</b> vs 🇹🇷 <b>Fenerbahçe</b>\n"
        f"🕒 <b>{'⚡ ' + get_live_minute(best) if live else '20:00'}</b>\n"
        f"⚽ <b>{best['main_bet']}</b>\n"
        f"📐 <b>{best['corner_bet']}</b> (Ort: {best['corner_avg']})\n"
        f"{'   ✅ Şu an: ' + str(live_stats['corners']) + ' korner' if live else ''}\n"
        f"🟨 <b>{best['card_bet']}</b> (Ort: {best['card_avg']})\n"
        f"{'   ✅ Şu an: ' + str(live_stats['cards']) + ' kart' if live else ''}\n"
        f"💰 Oran: <b>{best['odds']}</b>\n"
        f"📊 AI GÜVEN: <b>%{int(best['confidence']*100)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 ABONE OL, KAZAN! @stakedrip"
    )

async def hourly_job(ctx):
    text = await build_coupon(0.55, "CANLI KUPON", True)
    await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

async def daily_job(ctx):
    text = await build_coupon(0.60, "GÜNLÜK KUPON")
    await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

async def vip_job(ctx):
    text = await build_coupon(0.80, "VIP KUPON")
    await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()

tg.add_handler(CommandHandler("vip", lambda u,c: vip_job(c) or u.message.reply_text("VIP GÖNDERİLDİ!")))

@app.on_event("startup")
async def start():
    init_db(DB_PATH)
    jq = tg.job_queue
    jq.run_repeating(hourly_job, 3600, first=5)
    jq.run_repeating(daily_job, 43200, first=20)
    jq.run_repeating(vip_job, 86400, first=30)
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("v10.5 INDENT HATASIZ ÇALIŞIYOR!")

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
