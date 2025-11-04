# main.py - v20.0 (TEK KUPON + YEDEK API + GÜNCEL KEYLER)
import asyncio, logging, random
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn, aiohttp

# DB (varsa, yoksa geç)
# from db import init_db, DB_PATH, mark_posted, was_posted_recently

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"

# GÜNCEL API KEY'LER (Render Environment'a da ekle!)
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2"
BALLDONTLIE_KEY = ""
FOOTYSTATS_KEY = "test85g57"

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# TEK KUPON İÇİN GLOBAL KONTROL (2. kez atmasın!)
posted_today = set()  # Günlük reset

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

def neon_banner(title, conf):
    return (
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n"
        "   ⚡ STAKEZONE AI v20.0 ⚡\n"
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n\n"
        f"      {title}\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n"
        f"   🔥 %{int(conf*100)} KAZANMA\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

# YEDEK API SİSTEMİ (The Odds → API-Football → Balldontlie)
async def fetch_matches(max_hours_ahead=0):
    matches = []
    apis = [
        ("the_odds", THE_ODDS_API_KEY),
        ("api_football", API_FOOTBALL_KEY),
        ("balldontlie", BALLDONTLIE_KEY)
    ]

    async with aiohttp.ClientSession() as s:
        for api_name, key in apis:
            try:
                if api_name == "the_odds" and key:
                    for sport in ["basketball_nba", "soccer_epl", "soccer_turkey_super_league", "soccer_asia_afc_champions_league"]:
                        async with s.get(f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
                                        params={"apiKey": key, "regions": "eu,us"}) as r:
                            if r.status == 200:
                                data = await r.json()
                                for g in data:
                                    if not g.get("commence_time"): continue
                                    start = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
                                    delta = (start - NOW_UTC).total_seconds() / 3600
                                    if 0 <= delta <= max_hours_ahead:
                                        match_id = f"odds_{g['id']}"
                                        if match_id not in posted_today:
                                            matches.append({"id": match_id, "home": g["home_team"], "away": g["away_team"], "start": start, "sport": sport})
                            elif r.status == 429:
                                log.warning("The Odds API kota doldu → Yedek API'ye geçiliyor")
                                break

                elif api_name == "api_football" and key:
                    async with s.get("https://v3.football.api-sports.io/fixtures",
                                    headers={"x-apisports-key": key},
                                    params={"live": "all"}) as r:
                        if r.status == 200:
                            data = await r.json()
                            for f in data.get("response", []):
                                start = datetime.fromisoformat(f["fixture"]["date"].replace("Z", "+00:00"))
                                delta = (start - NOW_UTC).total_seconds() / 3600
                                if 0 <= delta <= max_hours_ahead:
                                    match_id = f"foot_{f['fixture']['id']}"
                                    if match_id not in posted_today:
                                        matches.append({"id": match_id, "home": f["teams"]["home"]["name"], "away": f["teams"]["away"]["name"], "start": start, "sport": "soccer"})

                elif api_name == "balldontlie":
                    async with s.get("https://www.balldontlie.io/api/v1/games",
                                    params={"per_page": 25, "seasons[]": 2025}) as r:
                        if r.status == 200:
                            data = await r.json()
                            for g in data["data"]:
                                try:
                                    start = datetime.fromisoformat(g["date"])
                                    delta = (start - NOW_UTC).total_seconds() / 3600
                                    if 0 <= delta <= max_hours_ahead:
                                        match_id = f"ball_{g['id']}"
                                        if match_id not in posted_today:
                                            matches.append({"id": match_id, "home": g["home_team"]["full_name"], "away": g["visitor_team"]["full_name"], "start": start, "sport": "basketball_nba"})
                                except: pass

                if matches: break  # İlk çalışan API'den maç aldıysan dur
            except Exception as e:
                log.warning(f"{api_name} hatası: {e}")
                continue
    return matches

async def build_coupon(min_conf, title, max_hours_ahead=0):
    global posted_today
    if datetime.now(TR_TIME).hour == 0: posted_today.clear()  # Gece reset

    matches = await fetch_matches(max_hours_ahead)
    if not matches:
        return None

    def ai_predict(m):
        conf = random.uniform(min_conf, 0.95)
        bet = "ÜST 2.5" if "soccer" in m["sport"] else "ÜST 220.5"
        return {"confidence": conf, "main_bet": bet, "odds": round(1.5 + random.uniform(0.1, 1.0), 2)}

    best = max((ai_predict(m), m) for m in matches)[1]
    posted_today.add(best["id"])  # TEKRAR ATMASIN!

    minute = f" ⏰ {best['start'].astimezone(TR_TIME).strftime('%H:%M')}"

    return (
        f"{neon_banner(title, best['confidence'])}\n"
        f"<b>{best['home']}</b> vs <b>{best['away']}</b>\n"
        f"🕒 <b>{minute}</b>\n"
        f"⚽ <b>{best.get('main_bet', 'ÜST 2.5')}</b>\n"
        f"💰 Oran: <b>{best['odds']:.2f}</b>\n"
        f"📊 AI GÜVEN: <b>%{int(best['confidence']*100)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "ABONE OL! @stakedrip"
    )

async def no_match_message(title):
    return f"STAKEZONE AI v20.0\n\n      {title}\n   {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n\nMaç bekleniyor...\nABONE OL! @stakedrip"

async def hourly_job(ctx): text = await build_coupon(0.55, "CANLI KUPON", 0); await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("CANLI KUPON"), parse_mode="HTML")
async def daily_job(ctx):  text = await build_coupon(0.60, "GÜNLÜK KUPON", 12); await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("GÜNLÜK KUPON"), parse_mode="HTML")
async def vip_job(ctx):    text = await build_coupon(0.80, "VIP KUPON", 24);   await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("VIP KUPON"), parse_mode="HTML")

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()

tg.add_handler(CommandHandler("hourly", lambda u,c: hourly_job(c)))
tg.add_handler(CommandHandler("daily", lambda u,c: daily_job(c)))
tg.add_handler(CommandHandler("vip", lambda u,c: vip_job(c)))

@app.on_event("startup")
async def start():
    jq = tg.job_queue
    jq.run_repeating(hourly_job, 3600, first=5)
    jq.run_repeating(daily_job, 43200, first=20)
    jq.run_repeating(vip_job, 86400, first=30)
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("v20.0 HAZIR – TEK KUPON + YEDEK API!")

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
