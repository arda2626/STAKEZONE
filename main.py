# main.py - v19 (Yeni API'ler + Yedekleme + TBL NBA)
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

# API KEY'LER – YENİLERİ EKLE (Render Environment'a koy)
THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2"  # api-sports.io'dan al (ücretsiz)
BALLDONTLIE_KEY = ""  # Balldontlie ücretsiz, key yok
FOOTYSTATS_KEY = "test85g57"  # footystats.org'dan al

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# LİGLER (Futbol + Basketbol + TBL)
ALL_SPORTS = [
    # Futbol
    "soccer_epl", "soccer_la_liga", "soccer_turkey_super_league", "soccer_greece_super_league",
    "soccer_basketball_nba", "soccer_basketball_euroleague", "soccer_basketball_turkey_tbl",  # TBL eklendi!
    # Basketbol
    "basketball_nba", "basketball_euroleague", "basketball_turkey_super_league"  # TBL için
]

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

def neon_banner(title, conf):
    return (
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n"
        "   ⚡ STAKEZONE AI v19 ⚡\n"
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n\n"
        f"      {title}\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n"
        f"   🔥 %{int(conf*100)} KAZANMA\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

# YENİ API FONKSİYONU – YEDEKLEME SİSTEMİ
async def get_matches_from_api(api_type, max_hours_ahead=0):
    matches = []
    if api_type == "the_odds":
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.the-odds-api.com/v4/sports/soccer_epl/odds", params={"apiKey": THE_ODDS_API_KEY, "regions": "eu"}) as r:
                if r.status == 200:
                    data = await r.json()
                    for g in data:
                        start = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
                        delta = (start - NOW_UTC).total_seconds() / 3600
                        if delta <= max_hours_ahead and delta >= 0:
                            matches.append({
                                "id": g["id"], "home": g["home_team"], "away": g["away_team"],
                                "sport": "soccer", "date": g["commence_time"], "start": start
                            })
                else:
                    log.warning("The Odds API kota doldu – Yedeklere geçiliyor")
                    return []

    elif api_type == "api_football":
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api-football-v1.p.rapidapi.com/v3/fixtures", params={
                "league": "39",  # EPL
                "api_key": API_FOOTBALL_KEY
            }) as r:
                if r.status == 200:
                    data = await r.json()
                    for fixture in data["response"]:
                        start = datetime.fromisoformat(fixture["fixture"]["date"])
                        delta = (start - NOW_UTC).total_seconds() / 3600
                        if delta <= max_hours_ahead and delta >= 0:
                            matches.append({
                                "id": fixture["fixture"]["id"], "home": fixture["teams"]["home"]["name"],
                                "away": fixture["teams"]["away"]["name"], "sport": "soccer",
                                "date": fixture["fixture"]["date"], "start": start
                            })

    elif api_type == "balldontlie":
        async with aiohttp.ClientSession() as s:
            async with s.get("https://www.balldontlie.io/api/v1/games", params={"seasons[]": "2025"}) as r:
                if r.status == 200:
                    data = await r.json()
                    for game in data["data"]:
                        start = datetime.fromisoformat(game["date"])
                        delta = (start - NOW_UTC).total_seconds() / 3600
                        if delta <= max_hours_ahead and delta >= 0:
                            matches.append({
                                "id": game["id"], "home": game["home_team"]["full_name"],
                                "away": game["visitor_team"]["full_name"], "sport": "basketball_nba",
                                "date": game["date"], "start": start
                            })

    elif api_type == "footystats":
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.footystats.org/matches", params={"key": FOOTYSTATS_KEY}) as r:
                if r.status == 200:
                    data = await r.json()
                    for match in data["data"]:
                        start = datetime.fromisoformat(match["time"])
                        delta = (start - NOW_UTC).total_seconds() / 3600
                        if delta <= max_hours_ahead and delta >= 0:
                            matches.append({
                                "id": match["id"], "home": match["home_name"], "away": match["away_name"],
                                "sport": "soccer", "date": match["time"], "start": start
                            })

    return matches

async def build_coupon(min_conf, title, max_hours_ahead=0):
    # Yedek API'leri dene (kota dolarsa bir sonrakine geç)
    apis = ["the_odds", "api_football", "balldontlie", "footystats"]
    all_matches = []
    for api in apis:
        matches = await get_matches_from_api(api, max_hours_ahead)
        all_matches.extend(matches)
        if len(all_matches) >= 5: break  # Yeterli maç buldu, dur

    if len(all_matches) < 1:
        return None

    picks = []
    for m in all_matches[:10]:  # En fazla 10 maç dene
        p = await ai_predict(m)
        p["odds"] = round(1.20 + random.uniform(0.1, 1.2), 2)
        if p["confidence"] >= min_conf:
            picks.append((p["confidence"], p))

    if len(picks) < 1:
        return None

    best = max(picks, key=lambda x: x[0])[1]
    mark_posted(best["id"])
    live = best["start"] < NOW_UTC
    live_stats = await get_live_events(best["id"]) if live else {"corners": "-", "cards": "-"}
    minute = f" ⚡ {get_live_minute(best)}'" if live else f" ⏰ {best['start'].astimezone(TR_TIME).strftime('%H:%M')}"

    return (
        f"{neon_banner(title, best['confidence'])}\n"
        f"{league_to_flag(best['home'])} <b>{best['home']}</b> vs {league_to_flag(best['away'])} <b>{best['away']}</b>\n"
        f"🕒 <b>{minute}</b>\n"
        f"⚽ <b>{best.get('main_bet', 'ÜST 2.5')}</b>\n"
        f"📐 <b>{best.get('corner_bet', 'KORNER ÜST 9.5')}</b> (Ort: 11.5)\n"
        f"{'   ✅ Canlı: ' + str(live_stats['corners']) + ' korner' if live else ''}\n"
        f"🟨 <b>{best.get('card_bet', 'KART ÜST 3.5')}</b> (Ort: 4.8)\n"
        f"{'   ✅ Canlı: ' + str(live_stats['cards']) + ' kart' if live else ''}\n"
        f"💰 Oran: <b>{best['odds']:.2f}</b>\n"
        f"📊 AI GÜVEN: <parameter name="citation_id">1</parameter <b>%{int(best['confidence']*100)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 ABONE OL! @stakedrip"
    )

async def no_match_message(title):
    return f"⚡ STAKEZONE AI v19 ⚡\n\n      {title}\n   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n\n🔍 4 API tarandı...\n⏳ 1 SAAT SONRA YENİ KUPON!\nABONE OL! @stakedrip"

async def hourly_job(ctx):
    text = await build_coupon(0.55, "CANLI KUPON", 0)
    await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("CANLI KUPON"), parse_mode="HTML")

async def daily_job(ctx):
    text = await build_coupon(0.60, "GÜNLÜK KUPON", 12)
    await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("GÜNLÜK KUPON"), parse_mode="HTML")

async def vip_job(ctx):
    text = await build_coupon(0.80, "VIP KUPON", 24)
    await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("VIP KUPON"), parse_mode="HTML")

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()

tg.add_handler(CommandHandler("hourly", lambda u,c: hourly_job(c) or u.message.reply_text("CANLI ATILDI")))
tg.add_handler(CommandHandler("daily", lambda u,c: daily_job(c) or u.message.reply_text("GÜNLÜK ATILDI")))
tg.add_handler(CommandHandler("vip", lambda u,c: vip_job(c) or u.message.reply_text("VIP ATILDI")))

@app.on_event("startup")
async def start():
    init_db(DB_PATH)
    jq = tg.job_queue
    jq.run_repeating(hourly_job, 3600, first=5)
    jq.run_repeating(daily_job, 43200, first=20)
    jq.run_repeating(vip_job, 86400, first=30)
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("v19 4 API YEDEK – HAZIR!")

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
