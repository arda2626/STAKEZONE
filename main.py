# main.py - v31.0 (28 ÜCRETSİZ API + KOTA UYARI + YEDEKLEME + TÜM SPORLAR)
import asyncio, logging, random
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn, aiohttp

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"

# 28 ÜCRETSİZ API KEY'LER (Render Environment'a ekle)
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2"
BALLDONTLIE_KEY = ""  # No key
FOOTYSTATS_KEY = "test85g57"
MYSPORTSFEEDS_KEY = "c0022399-a4c8-43ba-90b0-818244"
ALLSPORTSAPI_KEY = "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369"
THESPORTSDB_KEY = ""  # thesportsdb.com'dan al
SPORTDEVS_KEY = ""  # sportdevs.com'dan al
ODDSMAGNET_KEY = ""  # oddsmagnet.com'dan al
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ"
LIVESCORE_KEY = ""  # livescore-api.com'dan al
FOOTBALL_DATA_KEY = ""  # football-data.org'dan al
ISPORTSAPI_KEY = "7MAJu58UDAlMdWrw"
OPENLIGADB_KEY = ""  # No key
SPORTSIPPY_KEY = ""  # No key
SPORTSOPEN_KEY = ""  # No key
FOOTBALLHIGHLIGHTS_KEY = ""  # No key
FOOTBALLVIDEOS_KEY = ""  # No key
FOOTBALLSTANDINGS_KEY = ""  # No key
NBA_GRAPHQL_KEY = ""  # No key
NBA_STATS_KEY = ""  # No key
SUREDBITS_KEY = ""  # No key
OPENLIGADB_KEY = ""  # No key
FOOTBALL_DATA_KEY = ""  # No key
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ"  # GÜNCEL
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ"  # GÜNCEL
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ"  # GÜNCEL

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

posted_matches = {}
last_coupon_time = {"CANLI": None, "GÜNLÜK": None, "VIP": None}
match_cache = {}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

# SPOR EMOJİLERİ
SPORT_EMOJI = {
    "soccer": "⚽", "basketball": "🏀", "americanfootball": "🏈", "tennis": "🎾",
    "baseball": "⚾", "icehockey": "🏒", "cricket": "🏏", "rugby": "🏉"
}

# LİG ADI
LEAGUE_NAMES = {
    "basketball_nba": "NBA", "soccer_epl": "Premier League", "soccer_turkey_super_league": "Süper Lig",
    "americanfootball_ncaaf": "NCAAF", "tennis_atp": "ATP", "basketball_euroleague": "EuroLeague"
}

# BANNER
def banner(title):
    return f"━━━━━━━━━━━━━━━━━━━━━━\n    {title}\n━━━━━━━━━━━━━━━━━━━━━━"

# YEDEK API LISTESI (28)
async def fetch_matches(max_hours=24):
    global match_cache
    now = datetime.now(timezone.utc)
    cache_key = f"{max_hours}_{now.hour}"

    if cache_key in match_cache and (now - match_cache[cache_key]["time"]).total_seconds() < 300:
        log.info(f"Cache'den {len(match_cache[cache_key]['data'])} maç alındı")
        return match_cache[cache_key]["data"]

    matches = []
    apis = [
        ("The Odds API", THE_ODDS_API_KEY, "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"),
        ("API-Football", API_FOOTBALL_KEY, "https://v3.football.api-sports.io/fixtures"),
        ("Balldontlie", BALLDONTLIE_KEY, "https://www.balldontlie.io/api/v1/games"),
        ("FootyStats", FOOTYSTATS_KEY, "https://api.footystats.org/matches"),
        ("MySportsFeeds", MYSPORTSFEEDS_KEY, "https://api.mysportsfeeds.com/v2.1/pull/nba/score_summary.json"),
        ("AllSportsAPI", ALLSPORTSAPI_KEY, "https://api.allsportsapi.com/api/v1/fixtures"),
        ("TheSportsDB", THESPORTSDB_KEY, "https://www.thesportsdb.com/api/v1/json/1/events.php"),
        ("SportDevs", SPORTDEVS_KEY, "https://api.sportdevs.com/v1/sports/football/fixtures"),
        ("OddsMagnet", ODDSMAGNET_KEY, "https://api.oddsmagnet.com/v1/matches"),
        ("SportsMonks", SPORTSMONKS_KEY, "https://api.sportmonks.com/v3/football/fixtures"),
        ("LiveScore", LIVESCORE_KEY, "https://livescore-api.com/api-client/fixtures.json"),
        ("Football-Data", FOOTBALL_DATA_KEY, "http://api.football-data.org/v4/matches"),
        ("OpenLigaDB", OPENLIGADB_KEY, "https://openligadb.de/api/getmatchdata/json/aktuell"),
        ("Sportsipy", SPORTSIPPY_KEY, "https://api.sportsipy.com/nba/teams"),
        ("Sports Open Data", SPORTSOPEN_KEY, "https://sportsopendata.net/api/v1/matches"),
        ("Football Highlights", FOOTBALLHIGHLIGHTS_KEY, "https://football-highlights-api.com/matches"),
        ("Football Videos", FOOTBALLVIDEOS_KEY, "https://football-videos-api.com/videos"),
        ("Football Standings", FOOTBALLSTANDINGS_KEY, "https://football-standings-api.com/standings"),
        ("NBA GraphQL", NBA_GRAPHQL_KEY, "https://nba-graphql-api.com/query"),
        ("NBA Stats", NBA_STATS_KEY, "https://stats.nba.com/api/v1/stats"),
        ("SuredBits", SUREDBITS_KEY, "https://api.suredbits.com/sports"),
        ("OpenLigaDB", OPENLIGADB_KEY, "https://openligadb.de/api/getmatchdata/json/aktuell"),
        ("Football Data", FOOTBALL_DATA_KEY, "http://api.football-data.org/v4/matches"),
        ("iSportsAPI", ISPORTSAPI_KEY, "https://api.isportsapi.com/api/v1/football/fixtures"),
        ("Sports Open Data", SPORTSOPEN_KEY, "https://sportsopendata.net/api/v1/matches"),
        ("Public APIs Sports", "", "https://api.publicapis.org/entries?category=Sports"),
        ("OpenLigaDB", OPENLIGADB_KEY, "https://openligadb.de/api/getmatchdata/json/aktuell"),
        ("Sportsipy", SPORTSIPPY_KEY, "https://api.sportsipy.com/nba/teams")
    ]

    async with aiohttp.ClientSession() as s:
        for api_name, key, base_url in apis:
            if not key and key != "": continue
            try:
                log.info(f"{api_name} taranıyor...")
                headers = {}
                params = {}
                url = base_url

                # API'ye özel parametreler
                if "allsportsapi" in api_name.lower():
                    url = f"{base_url}{key}&from=2025-11-04&to=2025-11-05"
                elif "mysportsfeeds" in api_name.lower():
                    headers = {"Authorization": f"Basic {key}"}
                elif "api-sports" in api_name.lower():
                    headers = {"x-apisports-key": key}
                elif "football-data" in api_name.lower():
                    headers = {"X-Auth-Tokens": key}
                elif "sportmonks" in api_name.lower():
                    params = {"api_token": key}
                elif "isportsapi" in api_name.lower():
                    params = {"api_key": key}
                elif "openligadb" in api_name.lower():
                    params = {"key": key} if key else {}
                elif "publicapis" in api_name.lower():
                    params = {"category": "Sports"}

                async with s.get(url, headers=headers, params=params) as r:
                    if r.status == 200:
                        data = await r.json()
                        items = data.get("data", data.get("response", data.get("result", data.get("events", []))))
                        count = 0
                        for item in items:
                            try:
                                start_str = item.get("date", item.get("commence_time", item.get("fixture", {}).get("date", "")))
                                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                                delta = (start - NOW_UTC).total_seconds() / 3600
                                if 0 <= delta <= max_hours:
                                    match_id = f"{api_name}_{item.get('id', item.get('fixture', {}).get('id', 'unknown'))}"
                                    if match_id not in posted_matches:
                                        sport_type = "soccer" if "football" in api_name.lower() else "basketball" if "nba" in api_name.lower() else "general"
                                        league = "Premier League" if "epl" in api_name.lower() else "NBA" if "nba" in api_name.lower() else "Unknown"
                                        home = item.get("home_team", item.get("teams", {}).get("home", {}).get("name", "Home"))
                                        away = item.get("away_team", item.get("teams", {}).get("away", {}).get("name", "Away"))
                                        matches.append({"id": match_id, "home": home, "away": away, "start": start, "sport": sport_type, "league": league})
                                        count += 1
                            except: continue
                        log.info(f"{api_name}: {count} maç çekildi")
                        if count > 0: break  # Başarılı API'de dur
                    elif r.status == 429:
                        log.warning(f"{api_name} kota doldu – Uyarı loglandı, devam ediliyor")
                        continue
            except Exception as e:
                log.warning(f"{api_name} HATA – Yedek API'ye geçiliyor: {e}")
                continue

    match_cache[cache_key] = {"data": matches, "time": now}
    log.info(f"Toplam {len(matches)} maç çekildi (28 API'den)")
    return matches

# KUPON OLUŞTUR
async def build_coupon(title, max_hours, interval, max_matches):
    global posted_matches, last_coupon_time
    now = datetime.now(TR_TIME)

    last = last_coupon_time.get(title)
    if last and (now - last).total_seconds() < interval * 3600:
        return None

    matches = await fetch_matches(max_hours)
    if not matches: return None

    # En yüksek güven sıralama
    ranked = []
    for m in matches:
        bet, odds, conf, reason = ai_predict(m, m["sport"])
        ranked.append((conf, odds, m, bet, reason))
    ranked.sort(reverse=True)

    selected = ranked[:max_matches]
    total_odds = 1.0
    for _, odds, _, _, _ in selected: total_odds *= odds

    coupon_lines = []
    for conf, odds, m, bet, reason in selected:
        emoji = SPORT_EMOJI.get(m["sport"], "🏆")
        start_str = m["start"].astimezone(TR_TIME).strftime('%d %b %H:%M')
        line = f"{emoji} <b>{m['home']} vs {m['away']}</b>\n{start_str}\n<b>{bet}</b> → {odds:.2f} | %{conf}\n<i>{reason}</i>\n"
        coupon_lines.append(line)

    for _, _, m, _, _ in selected:
        posted_matches[m["id"]] = True
    last_coupon_time[title] = now

    invest = 100 if "CANLI" in title else 50 if "GÜNLÜK" in title else 200
    profit = invest * total_odds

    return (
        f"{banner(title)}\n"
        + "\n".join(coupon_lines) +
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Toplam Oran: <b>{total_odds:.2f}</b>\n"
        f"Yatırım: <b>{invest} TL</b> → Kazanç: <b>{profit:.0f} TL</b>\n"
        f"<a href='https://twitter.com/Gamblingsafe'>@Gamblingsafe</a> | "
        f"<a href='https://stake1090.com/?c=bz1hPARd'>STAKE GİRİŞ</a>\n"
        "ABONE OL! @stakedrip"
    )

# GÖNDER
async def send_coupon(ctx, title, max_hours, interval, max_matches):
    text = await build_coupon(title, max_hours, interval, max_matches)
    if text:
        await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
        log.info(f"{title} ATILDI!")

# JOBS
async def hourly(ctx): await send_coupon(ctx, "CANLI KUPON", 24, 1, 1)
async def daily(ctx):  await send_coupon(ctx, "GÜNLÜK KUPON", 24, 12, 3)
async def vip(ctx):    await send_coupon(ctx, "VIP KUPON", 24, 24, 3)

# TEST
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
    log.info("v31.0 HAZIR – 28 API + KOTA UYARI!")
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
