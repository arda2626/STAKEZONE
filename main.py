# main.py - STAKEZONE AI v16 (TEK KUPON, FARKLI BANNER, API DOLMAZ!)
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
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# TEK İSTEK → TÜM MAÇLAR (API DOLMAZ!)
ALL_SPORTS_URL = "https://api.the-odds-api.com/v4/sports/odds"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

# FARKLI BANNERLAR
def banner_canli(conf):
    return (
        "⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡\n"
        "   🔥 CANLI KUPON 🔥\n"
        "⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡\n\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n"
        f"   🔥 %{int(conf*100)} KAZANMA ŞANSI\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

def banner_gunluk(conf):
    return (
        "✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨\n"
        "   ⭐ GÜNLÜK KUPON ⭐\n"
        "✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨✨\n\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n"
        f"   🔥 %{int(conf*100)} KAZANMA ŞANSI\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

def banner_vip(conf):
    return (
        "💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎\n"
        "   👑 VIP KUPON 👑\n"
        "💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎💎\n\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n"
        f"   🔥 %{int(conf*100)} KAZANMA ŞANSI\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

# TEK İSTEKLE TÜM MAÇLARI ÇEK
async def get_all_matches(max_hours_ahead=0):
    matches = []
    async with aiohttp.ClientSession() as s:
        async with s.get(ALL_SPORTS_URL, params={
            "apiKey": THE_ODDS_API_KEY, "regions": "eu", "oddsFormat": "decimal"
        }) as r:
            if r.status != 200: return []
            data = await r.json()
            for g in data:
                if not g.get("commence_time"): continue
                start = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
                delta = (start - NOW_UTC).total_seconds() / 3600
                if delta > max_hours_ahead: continue
                if max_hours_ahead == 0 and delta >= 0: continue
                if was_posted_recently(g["id"]): continue
                matches.append({
                    "id": g["id"], "home": g["home_team"], "away": g["away_team"],
                    "sport": g.get("sport_key", ""), "start": start
                })
    return matches

# KUPON OLUŞTUR
async def build_coupon(min_conf, banner_func, max_hours_ahead=0, min_matches=1, min_odds=1.0):
    matches = await get_all_matches(max_hours_ahead)
    if len(matches) < min_matches: return None

    picks = []
    for m in matches:
        p = await ai_predict(m)
        p["odds"] = round(1.70 + random.uniform(0.1, 1.0), 2)
        if p["confidence"] >= min_conf and p["odds"] >= min_odds:
            picks.append((p["confidence"], p))

    if len(picks) < min_matches: return None

    best = max(picks, key=lambda x: x[0])[1]
    mark_posted(best["id"])
    live = best["start"] < NOW_UTC
    live_stats = await get_live_events(best["id"]) if live else {"corners": "-", "cards": "-"}
    minute = f" ⚡ {get_live_minute(best)}'" if live else f" ⏰ {best['start'].astimezone(TR_TIME).strftime('%H:%M')}"

    return (
        f"{banner_func(best['confidence'])}\n"
        f"{league_to_flag(best['home'])} <b>{best['home']}</b> vs {league_to_flag(best['away'])} <b>{best['away']}</b>\n"
        f"🕒 <b>{minute}</b>\n"
        f"⚽ <b>{best.get('main_bet', 'ÜST 2.5')}</b>\n"
        f"💰 Oran: <b>{best['odds']:.2f}</b>\n"
        f"📊 AI GÜVEN: <b>%{int(best['confidence']*100)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 ABONE OL! @stakedrip"
    )

# TEK KUPON KONTROLÜ
posted_today = {"daily": False, "vip": False}

async def no_match(title):
    return f"⚡ STAKEZONE AI v16 ⚡\n\n   {title}\n   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')}\n\n⏳ UYGUN MAÇ YOK\nABONE OL! @stakedrip"

# CANLI - HER SAAT 1 KERE
async def hourly_job(ctx):
    text = await build_coupon(0.55, banner_canli, 0)
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")

# GÜNLÜK - 12 SAATTE 1 KERE, 3+ MAÇ
async def daily_job(ctx):
    global posted_today
    if posted_today["daily"]: return
    text = await build_coupon(0.60, banner_gunluk, 12, min_matches=3)
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        posted_today["daily"] = True

# VIP - GÜNDE 1 KERE, 2.00+ ORAN
async def vip_job(ctx):
    global posted_today
    if posted_today["vip"]: return
    text = await build_coupon(0.80, banner_vip, 24, min_odds=2.00)
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        posted_today["vip"] = True

# GÜNLÜK SIFIRLA
async def reset_daily():
    global posted_today
    posted_today = {"daily": False, "vip": False}

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()

tg.add_handler(CommandHandler("hourly", lambda u,c: hourly_job(c)))
tg.add_handler(CommandHandler("daily", lambda u,c: daily_job(c)))
tg.add_handler(CommandHandler("vip", lambda u,c: vip_job(c)))

@app.on_event("startup")
async def start():
    init_db(DB_PATH)
    jq = tg.job_queue
    jq.run_repeating(hourly_job, 3600, first=10)        # HER SAAT
    jq.run_repeating(daily_job, 43200, first=20)        # 12 SAATTE 1
    jq.run_repeating(vip_job, 86400, first=30)          # GÜNDE 1
    jq.run_repeating(reset_daily, 86400, first=86400)   # GÜNLÜK SIFIRLA
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("v16 TEMİZ SİSTEM AÇIK!")

@app.post("/stakedrip")
async def wh(r: Request):
    up = Update.de_json(await r.json(), tg.bot)
    await tg.update_queue.put(up)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
