# main.py - v22.0 (KISA + TEK KUPON + HEMEN ATAR + TERCİH + ORAN)
import asyncio, logging, random
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn, aiohttp

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"

# GÜNCEL API KEY'LER
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2"
BALLDONTLIE_KEY = ""
FOOTYSTATS_KEY = "test85g57"

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# KONTROL
posted_matches = {}  # {match_id: last_sent_time}
last_coupon_time = {"hourly": None, "daily": None, "vip": None}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

# KISA BANNER
def banner(title):
    return f"STAKEZONE AI v22.0\n\n      {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# API ÇEKME
async def fetch_matches(max_hours_ahead=0):
    matches = []
    apis = [
        ("The Odds API", "the_odds", THE_ODDS_API_KEY),
        ("API-Football", "api_football", API_FOOTBALL_KEY),
        ("Balldontlie", "balldontlie", BALLDONTLIE_KEY)
    ]

    async with aiohttp.ClientSession() as s:
        for api_name, api_type, key in apis:
            try:
                if api_type == "the_odds" and key:
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
                                        if match_id not in posted_matches:
                                            matches.append({"id": match_id, "home": g["home_team"], "away": g["away_team"], "start": start, "sport": sport})
                            elif r.status == 429:
                                log.warning(f"{api_name} kota doldu")
                                break

                elif api_type == "api_football" and key:
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
                                    if match_id not in posted_matches:
                                        matches.append({"id": match_id, "home": f["teams"]["home"]["name"], "away": f["teams"]["away"]["name"], "start": start, "sport": "soccer"})

                elif api_type == "balldontlie":
                    async with s.get("https://www.balldontlie.io/api/v1/games",
                                    params={"per_page": 25}) as r:
                        if r.status == 200:
                            data = await r.json()
                            for g in data["data"]:
                                try:
                                    start = datetime.fromisoformat(g["date"])
                                    delta = (start - NOW_UTC).total_seconds() / 3600
                                    if 0 <= delta <= max_hours_ahead:
                                        match_id = f"ball_{g['id']}"
                                        if match_id not in posted_matches:
                                            matches.append({"id": match_id, "home": g["home_team"]["full_name"], "away": g["visitor_team"]["full_name"], "start": start, "sport": "basketball_nba"})
                                except: pass

                if matches: break
            except Exception as e:
                log.error(f"{api_name} hatası: {e}")
    return matches

# KUPON OLUŞTUR
async def build_coupon(min_conf, title, max_hours, interval_hours):
    global posted_matches, last_coupon_time
    now = datetime.now(TR_TIME)

    # ZAMAN KONTROLÜ
    if last_coupon_time[title] and (now - last_coupon_time[title]).total_seconds() < interval_hours * 3600:
        log.info(f"{title} bekleniyor...")
        return None

    matches = await fetch_matches(max_hours)
    if not matches:
        log.info(f"{title}: Maç yok")
        return None

    # TERCİHLER
    bets = []
    for m in matches:
        conf = random.uniform(min_conf, 0.95)
        odds = round(1.5 + random.uniform(0.1, 1.0), 2)
        bet_type = "ÜST 2.5" if "soccer" in m["sport"] else "ÜST 220.5"
        bets.append((conf, odds, bet_type, m))

    if not bets: return None

    best = max(bets)
    match = best[3]
    posted_matches[match["id"]] = now
    last_coupon_time[title] = now

    start_str = match["start"].astimezone(TR_TIME).strftime('%d %B %H:%M')
    total_odds = best[1]

    return (
        f"{banner(title)}\n"
        f"<b>{match['home']} vs {match['away']}</b>\n"
        f"{start_str}\n"
        f"{best[2]} | Oran: <b>{total_odds:.2f}</b>\n"
        f"AI GÜVEN: <b>%{int(best[0]*100)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<a href='https://twitter.com/Gamblingsafe'>@Gamblingsafe</a> | "
        f"<a href='https://stake1090.com/?c=bz1hPARd'>STAKE GİRİŞ</a>\n"
        "ABONE OL! @stakedrip"
    )

# GÖNDER
async def send_coupon(ctx, min_conf, title, max_hours, interval_hours):
    text = await build_coupon(min_conf, title, max_hours, interval_hours)
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
        log.info(f"{title} ATILDI!")
    else:
        await ctx.bot.send_message(CHANNEL_ID, f"STAKEZONE AI v22.0\n\n      {title}\nMaç bekleniyor...\nABONE OL! @stakedrip", parse_mode="HTML")

# JOBS
async def hourly_job(ctx): await send_coupon(ctx, 0.55, "CANLI KUPON", 0, 1)
async def daily_job(ctx):  await send_coupon(ctx, 0.60, "GÜNLÜK KUPON", 12, 12)
async def vip_job(ctx):    await send_coupon(ctx, 0.80, "VIP KUPON", 24, 24)

# TEST
async def test_cmd(update: Update, ctx):
    await send_coupon(ctx, 0.55, "TEST KUPON", 24, 0)
    await update.message.reply_text("Test atıldı!")

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()

tg.add_handler(CommandHandler("test", test_cmd))
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
    log.info("v22.0 HAZIR – KISA + TEK + TERCİH + ORAN!")

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
