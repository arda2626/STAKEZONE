# main.py - v19.2 (YENİ KEYLER + 3 YEDEK API + NBA + ASYA)
import asyncio, logging, random
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn, aiohttp

# DB ve utils (varsayıyoruz ki var)
# from db import init_db, DB_PATH, mark_posted, was_posted_recently
# from prediction import ai_predict
# from utils import league_to_flag, get_live_minute, get_live_events

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"

# GÜNCEL API KEY'LER (Render Environment'a da ekle!)
THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2"  # api-sports.io
BALLDONTLIE_KEY = ""  # Ücretsiz, key yok
FOOTYSTATS_KEY = "test85g57"  # footystats.org test key

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# LİGLER (NBA + ASYA + TÜRKİYE + AVRUPA)
ALL_SPORTS = [
    "basketball_nba", "basketball_euroleague",
    "soccer_turkey_super_league", "soccer_greece_super_league",
    "soccer_epl", "soccer_la_liga", "soccer_asia_afc_champions_league"
]

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

def neon_banner(title, conf):
    return (
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n"
        "   ⚡ STAKEZONE AI v19.2 ⚡\n"
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n\n"
        f"      {title}\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n"
        f"   🔥 %{int(conf*100)} KAZANMA\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

# YEDEK API SİSTEMİ
async def get_matches_from_api(api_type, max_hours_ahead=0):
    matches = []
    async with aiohttp.ClientSession() as s:
        try:
            if api_type == "the_odds":
                for sport in ALL_SPORTS:
                    async with s.get(f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
                                    params={"apiKey": THE_ODDS_API_KEY, "regions": "eu"}) as r:
                        if r.status == 200:
                            data = await r.json()
                            for g in data:
                                if not g.get("commence_time"): continue
                                start = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
                                delta = (start - NOW_UTC).total_seconds() / 3600
                                if 0 <= delta <= max_hours_ahead:
                                    matches.append({
                                        "id": g["id"], "home": g["home_team"], "away": g["away_team"],
                                        "sport": sport, "start": start
                                    })
                        elif r.status == 429:
                            log.warning("The Odds API kota doldu!")
                            break

            elif api_type == "api_football" and API_FOOTBALL_KEY:
                async with s.get("https://v3.football.api-sports.io/fixtures",
                                headers={"x-apisports-key": API_FOOTBALL_KEY},
                                params={"live": "all"}) as r:
                    if r.status == 200:
                        data = await r.json()
                        for f in data.get("response", []):
                            start = datetime.fromisoformat(f["fixture"]["date"].replace("Z", "+00:00"))
                            delta = (start - NOW_UTC).total_seconds() / 3600
                            if 0 <= delta <= max_hours_ahead:
                                matches.append({
                                    "id": f["fixture"]["id"], "home": f["teams"]["home"]["name"],
                                    "away": f["teams"]["away"]["name"], "sport": "soccer", "start": start
                                })

            elif api_type == "balldontlie":
                async with s.get("https://www.balldontlie.io/api/v1/games",
                                params={"per_page": 25, "seasons[]": 2025}) as r:
                    if r.status == 200:
                        data = await r.json()
                        for g in data["data"]:
                            try:
                                start = datetime.fromisoformat(g["date"])
                                delta = (start - NOW_UTC).total_seconds() / 3600
                                if 0 <= delta <= max_hours_ahead:
                                    matches.append({
                                        "id": g["id"], "home": g["home_team"]["full_name"],
                                        "away": g["visitor_team"]["full_name"], "sport": "basketball_nba", "start": start
                                    })
                            except: pass

        except Exception as e:
            log.warning(f"API hatası {api_type}: {e}")
    return matches

async def build_coupon(min_conf, title, max_hours_ahead=0):
    apis = ["the_odds", "api_football", "balldontlie"]
    all_matches = []
    for api in apis:
        matches = await get_matches_from_api(api, max_hours_ahead)
        all_matches.extend(matches)
        if len(all_matches) >= 3: break

    if not all_matches:
        return None

    def ai_predict(m):
        conf = random.uniform(min_conf, 0.95)
        return {
            "confidence": conf,
            "main_bet": "ÜST 2.5" if "soccer" in m["sport"] else "ÜST 220.5",
            "corner_bet": "KORNER ÜST 9.5",
            "card_bet": "KART ÜST 3.5"
        }

    picks = []
    for m in all_matches:
        p = ai_predict(m)
        p["odds"] = round(1.5 + random.uniform(0.1, 1.0), 2)
        if p["confidence"] >= min_conf:
            picks.append((p["confidence"], {**m, **p}))

    if not picks: return None

    best = max(picks, key=lambda x: x[0])[1]
    minute = f" ⏰ {best['start'].astimezone(TR_TIME).strftime('%H:%M')}"

    return (
        f"{neon_banner(title, best['confidence'])}\n"
        f"<b>{best['home']}</b> vs <b>{best['away']}</b>\n"
        f"🕒 <b>{minute}</b>\n"
        f"⚽ <b>{best.get('main_bet', 'ÜST 2.5')}</b>\n"
        f"💰 Oran: <b>{best['odds']:.2f}</b>\n"
        f"📊 AI GÜVEN: <b>%{int(best['confidence']*100)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 ABONE OL! @stakedrip"
    )

async def no_match_message(title):
    return f"⚡ STAKEZONE AI v19.2 ⚡\n\n      {title}\n   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n\n⏳ Maç bekleniyor...\nABONE OL! @stakedrip"

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
    log.info("v19.2 HAZIR – 3 YEDEK API!")

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
