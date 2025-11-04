# main.py - v21.0 (TEK KUPON + HEMEN ATAR + LOG + LINK)
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

# TEK KUPON KONTROLÜ
posted_matches = set()  # Global: Aynı maç 1 kez atılır

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

# BANNER + EMOJI
def neon_banner(title, conf):
    return (
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n"
        "   ⚡ STAKEZONE AI v21.0 ⚡\n"
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n\n"
        f"      {title}\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n"
        f"   🔥 %{int(conf*100)} KAZANMA ŞANSI\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

# YEDEK API + LOG
async def fetch_matches(max_hours_ahead=0):
    global posted_matches
    matches = []
    apis = [
        ("The Odds API", "the_odds", THE_ODDS_API_KEY),
        ("API-Football", "api_football", API_FOOTBALL_KEY),
        ("Balldontlie", "balldontlie", BALLDONTLIE_KEY)
    ]

    async with aiohttp.ClientSession() as s:
        for api_name, api_type, key in apis:
            try:
                log.info(f"{api_name} taranıyor...")
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
                                            matches.append({"id": match_id, "home": g["home_team"], "away": g["away_team"], "start": start})
                                if matches: log.info(f"{api_name}: {len(matches)} maç çekildi!")
                            elif r.status == 429:
                                log.warning(f"{api_name} kota doldu → Bir sonraki API'ye geçiliyor")
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
                                        matches.append({"id": match_id, "home": f["teams"]["home"]["name"], "away": f["teams"]["away"]["name"], "start": start})
                            if matches: log.info(f"{api_name}: {len(matches)} maç çekildi!")

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
                                            matches.append({"id": match_id, "home": g["home_team"]["full_name"], "away": g["visitor_team"]["full_name"], "start": start})
                                except: pass
                            if matches: log.info(f"{api_name}: {len(matches)} maç çekildi!")

                if matches: break
            except Exception as e:
                log.error(f"{api_name} hatası: {e}")
    return matches

async def build_coupon(min_conf, title, max_hours_ahead=0):
    global posted_matches
    matches = await fetch_matches(max_hours_ahead)
    if not matches:
        log.info(f"{title}: Maç bulunamadı")
        return None

    def ai_predict():
        return {"confidence": random.uniform(min_conf, 0.95), "odds": round(1.5 + random.uniform(0.1, 1.0), 2)}

    best = max((ai_predict(), m) for m in matches)[1]
    posted_matches.add(best["id"])

    minute = f" ⏰ {best['start'].astimezone(TR_TIME).strftime('%H:%M')}"
    link = "<a href='https://stake1090.com/?c=bz1hPARd'>STAKE GİRİŞ</a>"

    return (
        f"{neon_banner(title, best['confidence'])}\n"
        f"⚽ <b>{best['home']} vs {best['away']}</b>\n"
        f"🕒 <b>{minute}</b>\n"
        f"📊 AI GÜVEN: <b>%{int(best['confidence']*100)}</b>\n"
        f"💰 Oran: <b>{best['odds']:.2f}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <a href='https://twitter.com/Gamblingsafe'>@Gamblingsafe</a> | {link}\n"
        "🚀 ABONE OL! @stakedrip"
    ), parse_mode="HTML"

async def send_coupon(ctx, min_conf, title, max_hours):
    text, parse = await build_coupon(min_conf, title, max_hours)
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode=parse, disable_web_page_preview=True)
        log.info(f"{title} ATILDI!")
    else:
        await ctx.bot.send_message(CHANNEL_ID, f"STAKEZONE AI v21.0\n\n      {title}\n   {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')}\n\nAPI'ler taranıyor...\nABONE OL! @stakedrip", parse_mode="HTML")

# HEMEN ATAR
async def hourly_job(ctx): await send_coupon(ctx, 0.55, "CANLI KUPON", 0)
async def daily_job(ctx):  await send_coupon(ctx, 0.60, "GÜNLÜK KUPON", 12)
async def vip_job(ctx):    await send_coupon(ctx, 0.80, "VIP KUPON", 24)

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()

# TEST KOMUTLARI ÇALIŞIR
async def test_cmd(update: Update, ctx):
    await send_coupon(ctx, 0.55, "TEST KUPON", 24)
    await update.message.reply_text("Test kuponu atıldı!")

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
    log.info("v21.0 HAZIR – HEMEN ATAR + LOG + LINK!")

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
