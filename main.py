# main.py - v24.0 (YENİ TASARIM + LİG + ÇOK TERCİH + HEM FUTBOL HEM BASKET)
import asyncio, logging, random
from datetime import datetime, timezone
from telegram.ext import Application, CommandHandler
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn, aiohttp

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"

THEAPI_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

posted_matches = {}
last_coupon_time = {"CANLI": None, "GÜNLÜK": None, "VIP": None}
match_cache = {}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

# LİG ADI DÜZELTME
LEAGUE_NAMES = {
    "basketball_nba": "NBA",
    "soccer_epl": "Premier League",
    "soccer_turkey_super_league": "Süper Lig",
    "soccer_la_liga": "La Liga",
    "basketball_euroleague": "EuroLeague"
}

# GÖZ ALICI BANNER
def banner(title):
    return (
        "⚡ STAKEZONE AI v24.0\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"       {title}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

# API ÇEKME (MİNİMUM + CACHE)
async def fetch_matches(max_hours=0):
    global match_cache
    now = datetime.now(timezone.utc)
    cache_key = f"{max_hours}_{now.hour}"

    if cache_key in match_cache and (now - match_cache[cache_key]["time"]).total_seconds() < 300:
        log.info(f"Cache: {len(match_cache[cache_key]['data'])} maç")
        return match_cache[cache_key]["data"]

    matches = []
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(f"https://api.the-odds-api.com/v4/sports", params={"apiKey": API_KEY}) as r:
                sports = await r.json() if r.status == 200 else []
                sport_keys = [s["key"] for s in sports if s["active"]] or ["basketball_nba", "soccer_epl"]

            for sport in sport_keys[:6]:
                async with s.get(f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
                                params={"apiKey": API_KEY, "regions": "eu,us"}) as r:
                    if r.status != 200: continue
                    data = await r.json()
                    for g in data:
                        start = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
                        if (start - NOW_UTC).total_seconds() / 3600 <= max_hours:
                            match_id = f"odds_{g['id']}"
                            if match_id not in posted_matches:
                                league = LEAGUE_NAMES.get(sport, sport.replace("_", " ").title())
                                matches.append({
                                    "id": match_id, "home": g["home_team"], "away": g["away_team"],
                                    "start": start, "sport": sport, "league": league
                                })
                    if matches: break
        except Exception as e:
            log.error(f"API hatası: {e}")

    match_cache[cache_key] = {"data": matches, "time": now}
    log.info(f"{len(matches)} maç çekildi")
    return matches

# KUPON OLUŞTUR
async def build_coupon(title, max_hours, interval):
    global posted_matches, last_coupon_time
    now = datetime.now(TR_TIME)

    last = last_coupon_time.get(title)
    if last and (now - last).total_seconds() < interval * 3600:
        return None

    matches = await fetch_matches(max_hours)
    if not matches:
        log.info(f"{title}: Maç yok")
        return None

    m = random.choice(matches[:3])
    posted_matches[m["id"]] = now
    last_coupon_time[title] = now

    start_str = m["start"].astimezone(TR_TIME).strftime('%d %B %H:%M')
    is_soccer = "soccer" in m["sport"]

    # TERCİHLER
    bet1 = f"Toplam Goller 0,5 ÜST - {random.uniform(1.3, 1.6):.2f}  güven %{random.randint(65,85)}"
    bet2 = f"Maç Sonucu Skoru {'1-0' if random.random() > 0.5 else '0-1'} - {random.uniform(3.5, 6.0):.2f}" if is_soccer else f"Toplam Sayı 220,5 ÜST - {random.uniform(1.7, 2.1):.2f}"
    bet3 = f"{'MS 1' if random.random() > 0.5 else 'MS 2'} - {random.uniform(1.8, 2.5):.2f}"

    return (
        f"{banner(title)}\n"
        f"[{m['league']}] <b>{m['home']} vs {m['away']}</b>\n"
        f"{start_str}\n\n"
        f"{bet1}\n"
        f"{bet2}\n"
        f"{bet3}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<a href='https://twitter.com/Gamblingsafe'>@Gamblingsafe</a> | "
        f"<a href='https://stake1090.com/?c=bz1hPARd'>STAKE GİRİŞ</a>\n"
        "ABONE OL! @stakedrip"
    )

# GÖNDER
async def send_coupon(ctx, title, max_hours, interval):
    text = await build_coupon(title, max_hours, interval)
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
        log.info(f"{title} KUPON ATILDI!")

# JOBS
async def hourly(ctx): await send_coupon(ctx, "CANLI KUPON", 0, 1)
async def daily(ctx):  await send_coupon(ctx, "GÜNLÜK KUPON", 12, 12)
async def vip(ctx):    await send_coupon(ctx, "VIP KUPON", 24, 24)

# TEST
async def test(update: Update, ctx):
    await send_coupon(ctx, "TEST KUPON", 24, 0)
    await update.message.reply_text("Test kuponu atıldı!")

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()

tg.add_handler(CommandHandler("test", test))
tg.add_handler(CommandHandler("hourly", lambda u,c: hourly(c)))
tg.add_handler(CommandHandler("daily", lambda u,c: daily(c)))
tg.add_handler(CommandHandler("vip", lambda u,c: vip(c)))

async def lifespan(app: FastAPI):
    jq = tg.job_queue
    jq.run_repeating(hourly, 3600, first=5)
    jq.run_repeating(daily, 43200, first=20)
    jq.run_repeating(vip, 86400, first=30)
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("v24.0 HAZIR – YENİ TASARIM!")
    yield
    await tg.stop(); await tg.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
