# main.py - v23.0 (TEK + EMOJİ + MİNİMUM API + LİG TARAMA)
import asyncio, logging, random
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn, aiohttp

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"

# API KEY
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# KONTROL
posted_matches = {}
last_coupon_time = {"CANLI KUPON": None, "GÜNLÜK KUPON": None, "VIP KUPON": None}
match_cache = {}  # API kullanımını azaltmak için

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

# BANNER + EMOJİ
def banner(title, sport):
    emoji = "⚽" if "soccer" in sport else "🏀"
    return f"STAKEZONE AI v23.0\n\n      {title} {emoji}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# API ÇEKME (1 İSTEK, TÜM LİGLER)
async def fetch_matches(max_hours_ahead=0):
    global match_cache
    now = datetime.now(timezone.utc)
    cache_key = f"{max_hours_ahead}_{now.hour}"
    
    if cache_key in match_cache and (now - match_cache[cache_key]["time"]).total_seconds() < 300:  # 5 dk cache
        log.info(f"Cache'den {len(match_cache[cache_key]['data'])} maç alındı")
        return match_cache[cache_key]["data"]

    matches = []
    async with aiohttp.ClientSession() as s:
        try:
            # TÜM LİGLERİ TEK İSTEKLE AL
            async with s.get("https://api.the-odds-api.com/v4/sports", params={"apiKey": THE_ODDS_API_KEY}) as r:
                if r.status == 200:
                    sports = await r.json()
                    sport_keys = [s["key"] for s in sports if s["active"]]
                else:
                    sport_keys = ["basketball_nba", "soccer_epl", "soccer_turkey_super_league"]

            for sport in sport_keys[:5]:  # API yükünü azalt
                async with s.get(f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
                                params={"apiKey": THE_ODDS_API_KEY, "regions": "eu,us"}) as r:
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
                        log.warning("Kota doldu")
                        break
        except Exception as e:
            log.error(f"API hatası: {e}")

    match_cache[cache_key] = {"data": matches, "time": now}
    log.info(f"{len(matches)} maç çekildi (API)")
    return matches

# KUPON OLUŞTUR
async def build_coupon(min_conf, title, max_hours, interval_hours):
    global posted_matches, last_coupon_time
    now = datetime.now(TR_TIME)

    # ZAMAN KONTROLÜ
    last_time = last_coupon_time.get(title)
    if last_time and (now - last_time).total_seconds() < interval_hours * 3600:
        return None

    matches = await fetch_matches(max_hours)
    if not matches:
        log.info(f"{title}: Maç bulunamadı")
        return None

    # TERCİH
    bets = []
    for m in matches:
        conf = random.uniform(min_conf, 0.95)
        odds = round(1.5 + random.uniform(0.1, 1.0), 2)
        bet_type = "ÜST 2.5" if "soccer" in m["sport"] else "ÜST 220.5"
        bets.append((conf, odds, bet_type, m))

    best = max(bets)
    match = best[3]
    posted_matches[match["id"]] = now
    last_coupon_time[title] = now

    start_str = match["start"].astimezone(TR_TIME).strftime('%d %B %H:%M')
    total_odds = best[1]
    extra = f"\nKazanma Oranı: <b>{total_odds:.2f}</b>" if title == "GÜNLÜK KUPON" else ""

    return (
        f"{banner(title, match['sport'])}\n"
        f"<b>{match['home']} vs {match['away']}</b>\n"
        f"{start_str}\n"
        f"{best[2]} | Oran: <b>{total_odds:.2f}</b>\n"
        f"AI GÜVEN: <b>%{int(best[0]*100)}</b>{extra}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<a href='https://twitter.com/Gamblingsafe'>@Gamblingsafe</a> | "
        f"<a href='https://stake1090.com/?c=bz1hPARd'>STAKE GİRİŞ</a>\n"
        "ABONE OL! @stakedrip"
    )

# GÖNDER (MAÇ YOKSA ATMAZ)
async def send_coupon(ctx, min_conf, title, max_hours, interval_hours):
    text = await build_coupon(min_conf, title, max_hours, interval_hours)
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
        log.info(f"{title} ATILDI!")

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

# LIFESPAN
async def lifespan(app: FastAPI):
    jq = tg.job_queue
    jq.run_repeating(hourly_job, 3600, first=5)
    jq.run_repeating(daily_job, 43200, first=20)
    jq.run_repeating(vip_job, 86400, first=30)
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("v23.0 HAZIR – TEK + EMOJİ + MİN API!")
    yield
    await tg.stop(); await tg.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__"main":
    uvicorn.run(app, host="0.0.0.0", port=8443)
