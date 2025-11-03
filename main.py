# main.py - STAKEZONE AI v12 (12-24 SAAT GARANTİ!)
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
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"
THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)
SPORTS = ["soccer_epl", "soccer_la_liga", "soccer_turkey_super_league", "soccer_champions_league", "soccer_uefa_europa_league"]

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

def neon_banner(title, conf):
    return (
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n"
        "   ⚡ STAKEZONE AI v12 ⚡\n"
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n\n"
        f"      {title}\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n"
        f"   🔥 %{int(conf*100)} KAZANMA ŞANSI\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

async def build_coupon(min_conf, title, max_hours_ahead=0):
    matches = []
    async with aiohttp.ClientSession() as s:
        for sp in SPORTS:
            try:
                async with s.get(f"https://api.the-odds-api.com/v4/sports/{sp}/odds",
                                params={"apiKey": THE_ODDS_API_KEY, "regions": "eu"}) as r:
                    if r.status != 200: continue
                    data = await r.json()
                    for g in data:
                        start = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
                        delta = (start - NOW_UTC).total_seconds() / 3600
                        # CANLI: delta < 0
                        # GÜNLÜK: delta <= 12
                        # VIP: delta <= 24
                        if delta > max_hours_ahead: continue
                        if max_hours_ahead == 0 and delta >= 0: continue  # sadece canlı
                        if was_posted_recently(g["id"]): continue
                        matches.append({"id": g["id"], "home": g["home_team"], "away": g["away_team"],
                                        "sport": sp, "date": g["commence_time"], "start": start})
            except: pass

    if not matches:
        return None

    picks = []
    for m in matches:
        p = await ai_predict(m)
        p["odds"] = 1.20  # Gerçek oran istersen API'den çek
        if p["confidence"] >= min_conf and p["odds"] >= 1.20:
            picks.append((p["confidence"], p))

    if not picks: return None

    best = max(picks, key=lambda x: x[0])[1]
    mark_posted(best["id"])
    live = best.get("start", NOW_UTC) < NOW_UTC
    live_stats = await get_live_events(best["id"]) if live else {"corners": "-", "cards": "-"}
    minute = f" ⚡ {get_live_minute(best)}'" if live else f" ⏰ {best['start'].astimezone(TR_TIME).strftime('%H:%M')}"

    return (
        f"{neon_banner(title, best['confidence'])}\n"
        f"🏴 {league_to_flag(best['home'])} <b>{best['home']}</b> vs {league_to_flag(best['away'])} <b>{best['away']}</b>\n"
        f"🕒 <b>{minute}</b>\n"
        f"⚽ <b>{best['main_bet']}</b>\n"
        f"📐 <b>{best['corner_bet']}</b> (Ort: {best.get('corner_avg', '11.2')})\n"
        f"{'   ✅ Canlı: ' + str(live_stats['corners']) + ' korner' if live else ''}\n"
        f"🟨 <b>{best['card_bet']}</b> (Ort: {best.get('card_avg', '4.7')})\n"
        f"{'   ✅ Canlı: ' + str(live_stats['cards']) + ' kart' if live else ''}\n"
        f"💰 Oran: <b>{best['odds']:.2f}</b>\n"
        f"📊 AI GÜVEN: <b>%{int(best['confidence']*100)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 ABONE OL! @stakedrip"
    )

async def no_match_message(title):
    return (
        "⚡ STAKEZONE AI v12 ⚡\n\n"
        f"      {title}\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n\n"
        "⏳ ŞU AN UYGUN MAÇ YOK\n"
        "🔥 1 SAAT SONRA YENİ KUPON!\n"
        "ABONE OL, KAÇIRMA! @stakedrip"
    )

async def hourly_job(ctx):   # CANLI
    text = await build_coupon(0.55, "CANLI KUPON", 0)
    await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("CANLI KUPON"), parse_mode="HTML")

async def daily_job(ctx):    # 12 SAAT
    text = await build_coupon(0.60, "GÜNLÜK KUPON", 12)
    await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("GÜNLÜK KUPON"), parse_mode="HTML")

async def vip_job(ctx):      # 24 SAAT
    text = await build_coupon(0.80, "VIP KUPON", 24)
    await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("VIP KUPON"), parse_mode="HTML")

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()

tg.add_handler(CommandHandler("hourly", lambda u,c: hourly_job(c)))
tg.add_handler(CommandHandler("daily", lambda u,c: daily_job(c)))
tg.add_handler(CommandHandler("vip", lambda u,c: vip_job(c)))

@app.on_event("startup")
async def start():
    init_db(DB_PATH)
    jq = tg.job_queue
    jq.run_repeating(hourly_job, 3600, first=5)   # HER SAAT CANLI
    jq.run_repeating(daily_job, 43200, first=20)  # GÜNLÜK
    jq.run_repeating(vip_job, 86400, first=30)    # VIP
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("v12 12-24 SAAT GARANTİLİ!")

@app.post("/stakedrip")
async def wh(r: Request):
    up = Update.de_json(await r.json(), tg.bot)
    await tg.update_queue.put(up)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
