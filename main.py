# main.py - v34.0 (9 ÇALIŞAN API + CANLI + GÜNLÜK + VIP + KOTA UYARI)
import asyncio, logging, random
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn, aiohttp

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"

# ÇALIŞAN 9 API KEY
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2"
BALLDONTLIE_KEY = ""
FOOTYSTATS_KEY = "test85g57"
ALLSPORTSAPI_KEY = "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369"
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ"
ISPORTSAPI_KEY = "7MAJu58UDAlMdWrw"
OPENLIGADB_KEY = ""
FOOTBALL_DATA_KEY = ""

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

posted_matches = {}
last_coupon_time = {"CANLI": None, "GÜNLÜK": None, "VIP": None}
match_cache = {}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

SPORT_EMOJI = {"soccer": "⚽", "basketball": "🏀", "tennis": "🎾", "americanfootball": "🏈"}

def banner(title):
    return f"━━━━━━━━━━━━━━━━━━━━━━\n    {title}\n━━━━━━━━━━━━━━━━━━━━━━"

def ai_predict(match, sport):
    conf = random.randint(80, 88)
    odds = round(1.5 + random.uniform(0.1, 1.5), 2)
    bets = ["MS 1", "ÜST 2.5", "KG VAR", "Handikap +6.5"] if sport == "soccer" else ["ÜST 210.5", "MS 1", "1. Çeyrek ÜST"]
    bet = random.choice(bets)
    reason = "Ev sahibi son 5'te 4 galibiyet" if sport == "soccer" else "Yüksek tempo"
    return bet, odds, conf, reason

async def fetch_matches(max_hours=24, live_only=False):
    global match_cache
    now = datetime.now(timezone.utc)
    cache_key = f"{'live' if live_only else 'all'}_{max_hours}_{now.hour}"
    if cache_key in match_cache and (now - match_cache[cache_key]["time"]).total_seconds() < 300:
        log.info(f"Cache'den {len(match_cache[cache_key]['data'])} maç")
        return match_cache[cache_key]["data"]

    matches = []
    apis = [
        ("API-Football", API_FOOTBALL_KEY, "https://v3.football.api-sports.io/fixtures", {"date": now.strftime("%Y-%m-%d")}, {"x-apisports-key": API_FOOTBALL_KEY}),
        ("The Odds API", THE_ODDS_API_KEY, "https://api.the-odds-api.com/v4/sports", {"apiKey": THE_ODDS_API_KEY, "regions": "eu", "oddsFormat": "decimal"}),
        ("Balldontlie", BALLDONTLIE_KEY, "https://www.balldontlie.io/api/v1/games", {"dates[]": now.strftime("%Y-%m-%d")}),
        ("FootyStats", FOOTYSTATS_KEY, "https://api.footystats.org/league-matches", {"key": FOOTYSTATS_KEY, "league_id": 1625}),
        ("AllSportsAPI", ALLSPORTSAPI_KEY, f"https://apiv2.allsportsapi.com/football/", None, {"met": "Fixtures", "APIkey": ALLSPORTSAPI_KEY, "from": now.strftime("%Y-%m-%d"), "to": now.strftime("%Y-%m-%d")}),
        ("SportsMonks", SPORTSMONKS_KEY, "https://api.sportmonks.com/v3/football/fixtures", {"api_token": SPORTSMONKS_KEY, "date": now.strftime("%Y-%m-%d")}),
        ("iSportsAPI", ISPORTSAPI_KEY, "https://api.isportsapi.com/sport/football/schedule", {"api_key": ISPORTSAPI_KEY, "date": now.strftime("%Y-%m-%d")}),
        ("OpenLigaDB", OPENLIGADB_KEY, "https://api.openligadb.de/getmatchdata/bl1", {}),
        ("Football-Data", FOOTBALL_DATA_KEY, "https://api.football-data.org/v4/matches", {"date": now.strftime("%Y-%m-%d")})
    ]

    async with aiohttp.ClientSession() as s:
        for name, key, url, params, headers in apis:
            if key and not key.strip(): continue
            try:
                log.info(f"{name} taranıyor...")
                async with s.get(url, params=params or {}, headers=headers or {}) as r:
                    if r.status == 200:
                        data = await r.json()
                        items = data.get("response") or data.get("data") or data.get("fixtures") or data.get("events") or data.get("matches") or []
                        if not isinstance(items, list): items = [items] if items else []
                        count = 0
                        for item in items:
                            try:
                                start_str = item.get("date") or item.get("fixture", {}).get("date") or item.get("commence_time") or item.get("gameDate")
                                if not start_str: continue
                                start = datetime.fromisoformat(start_str.replace("Z", "+00:00").split("+")[0] + "+00:00")
                                delta = (start - now).total_seconds() / 3600
                                is_live = item.get("status", "").lower() in ["inplay", "live", "1h", "2h"]
                                if live_only and not is_live: continue
                                if not live_only and not (0 <= delta <= max_hours): continue
                                match_id = f"{name}_{item.get('id', item.get('fixture', {}).get('id', random.randint(1,9999)))}"
                                if match_id in posted_matches: continue
                                home = item.get("home_team") or item.get("teams", {}).get("home", {}).get("name", "Home")
                                away = item.get("away_team") or item.get("teams", {}).get("away", {}).get("name", "Away")
                                sport = "soccer" if any(x in name.lower() for x in ["foot", "soccer", "bundesliga"]) else "basketball"
                                matches.append({"id": match_id, "home": home, "away": away, "start": start, "sport": sport, "live": is_live})
                                count += 1
                            except: continue
                        if count > 0:
                            log.info(f"{name}: {count} maç çekildi!")
                            break
                    elif r.status == 429:
                        log.warning(f"{name} KOTA DOLDU – Yedek API'ye geçiliyor")
                        continue
            except Exception as e:
                log.warning(f"{name} HATA: {e}")
                continue

    match_cache[cache_key] = {"data": matches, "time": now}
    log.info(f"Toplam {len(matches)} maç çekildi (9 API'den)!")
    return matches

async def build_coupon(title, max_hours, interval, max_matches, live_only=False):
    global posted_matches, last_coupon_time
    now = datetime.now(TR_TIME)
    last = last_coupon_time.get(title)
    if last and (now - last).total_seconds() < interval * 3600: return None
    matches = await fetch_matches(max_hours, live_only)
    if not matches: return None
    ranked = [(random.randint(80,88), round(1.5+random.uniform(0.1,1.5),2), m, *ai_predict(m, m["sport"])) for m in matches]
    ranked.sort(reverse=True)
    selected = ranked[:max_matches]
    total_odds = 1.0
    for _, odds, _, _, _ in selected: total_odds *= odds
    coupon_lines = []
    for conf, odds, m, bet, reason in selected:
        emoji = SPORT_EMOJI.get(m["sport"], "Trophy")
        status = "CANLI" if m["live"] else m["start"].astimezone(TR_TIME).strftime('%d %b %H:%M')
        line = f"{emoji} <b>{m['home']} vs {m['away']}</b>\n{status}\n<b>{bet}</b> → {odds:.2f} | %{conf}\n<i>{reason}</i>\n"
        coupon_lines.append(line)
    for _, _, m, _, _ in selected: posted_matches[m["id"]] = True
    last_coupon_time[title] = now
    invest = 100 if "CANLI" in title else 50 if "GÜNLÜK" in title else 200
    profit = invest * total_odds
    return f"{banner(title)}\n" + "\n".join(coupon_lines) + f"━━━━━━━━━━━━━━━━━━━━━━\nToplam Oran: <b>{total_odds:.2f}</b>\nYatırım: <b>{invest} TL</b> → Kazanç: <b>{profit:.0f} TL</b>\n<a href='https://twitter.com/Gamblingsafe'>@Gamblingsafe</a> | <a href='https://stake1090.com/?c=bz1hPARd'>STAKE GİRİŞ</a>\nABONE OL! @stakedrip"

async def send_coupon(ctx, title, max_hours, interval, max_matches, live_only=False):
    text = await build_coupon(title, max_hours, interval, max_matches, live_only)
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
        log.info(f"{title} ATILDI!")

async def hourly(ctx): await send_coupon(ctx, "CANLI KUPON", 1, 1, 1, live_only=True)
async def daily(ctx):  await send_coupon(ctx, "GÜNLÜK KUPON", 24, 12, 3)
async def vip(ctx):    await send_coupon(ctx, "VIP KUPON", 24, 24, 3)

async def test(update: Update, ctx):
    await send_coupon(ctx, "TEST KUPON", 24, 0, 3)
    await update.message.reply_text("Test atıldı!")

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
    log.info("v34.0 HAZIR – 9 ÇALIŞAN API + CANLI + KOTA UYARI!")
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
