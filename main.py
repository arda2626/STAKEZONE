# main.py - v38.1 AI-TÜRKÇE (Stabil + Hata Yönetimli + Çoklu API)
import os, asyncio, logging, random, json, aiohttp, ssl
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from fastapi import FastAPI, Request
import uvicorn
from dotenv import load_dotenv
from ai_turkce import ai_turkce_analiz

# ==================== CONFIG ====================
load_dotenv()
TR_TIME = timezone(timedelta(hours=3))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "REPLACE_ME")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@stakedrip")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://stakezone-ai.onrender.com/stakedrip")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "bd1350bea151ef9f56ed417f0c0c3ea2")
THE_ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY", "501ea1ade60d5f0b13b8f34f90cd51e6")
BALLDONTLIE_KEY = os.getenv("BALLDONTLIE_KEY", "")
FOOTYSTATS_KEY = os.getenv("FOOTYSTATS_KEY", "test85g57")
ALLSPORTSAPI_KEY = os.getenv("ALLSPORTSAPI_KEY", "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369")
SPORTSMONKS_KEY = os.getenv("SPORTSMONKS_KEY", "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ")
ISPORTSAPI_KEY = os.getenv("ISPORTSAPI_KEY", "7MAJu58UDAlMdWrw")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

SPORT_EMOJI = {"soccer": "⚽", "basketball": "🏀", "tennis": "🎾"}

match_cache, team_stats_cache, posted_matches = {}, {}, {}
last_coupon_time = {"CANLI": None, "GÜNLÜK": None, "VIP": None}

# ==================== OPENAI ====================
async def openai_chat_json(prompt: str, max_tokens: int = 350):
    if not OPENAI_API_KEY:
        log.warning("⚠️ OPENAI_API_KEY tanımlı değil.")
        return None

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    system = (
        "Sen bir Türk spor analisti ve veri bilimcisisin. "
        "Kullanıcı Türkçe konuşuyor. Sadece istatistiksel tahmin yap.\n"
        "Yanıt formatı JSON olmalı: {\"predictions\": [...], \"best\": index}"
    )
    payload = {"model": "gpt-4o-mini", "messages": [{"role":"system","content":system},{"role":"user","content":prompt}],
               "temperature":0.25,"max_tokens":max_tokens}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as resp:
                txt = await resp.text()
                try:
                    return json.loads(txt[txt.find("{"):txt.rfind("}")+1])
                except Exception:
                    log.warning("OpenAI JSON parse hatası.")
                    return {"raw": txt}
    except Exception as e:
        log.error(f"OpenAI hatası: {e}")
        return None

# ==================== MAÇ ÇEKME ====================
async def fetch_matches(max_hours=24, live_only=False):
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    matches = []

    apis = [
        ("API-Football", f"https://v3.football.api-sports.io/fixtures", {"date": today}, {"x-apisports-key": API_FOOTBALL_KEY}),
        ("The Odds API", f"https://api.the-odds-api.com/v4/sports", {"apiKey": THE_ODDS_API_KEY, "regions": "eu"}, {}),
        ("FootyStats", "https://api.footystats.org/league-matches", {"key": FOOTYSTATS_KEY, "league_id": 1625}, {}),
        ("AllSportsAPI", "https://apiv2.allsportsapi.com/football/", {"met":"Fixtures","APIkey":ALLSPORTSAPI_KEY,"from":today,"to":today}, {}),
        ("SportsMonks", "https://api.sportmonks.com/v3/football/fixtures", {"api_token": SPORTSMONKS_KEY, "date": today}, {}),
        ("iSportsAPI", "https://api.isportsapi.com/sport/football/schedule", {"api_key": ISPORTSAPI_KEY, "date": today}, {})
    ]

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession() as session:
        for name, url, params, headers in apis:
            try:
                log.info(f"{name} çağrılıyor...")
                async with session.get(url, params=params, headers=headers, ssl=ssl_context if "iSports" in name else None, timeout=15) as r:
                    if r.status != 200:
                        log.warning(f"{name} HTTP {r.status}")
                        continue
                    data = await r.json()
                    items = data.get("response") or data.get("data") or data.get("matches") or data.get("games") or []
                    if not isinstance(items, list): continue

                    for item in items:
                        try:
                            start_str = item.get("date") or item.get("fixture", {}).get("date") or item.get("commence_time")
                            if not start_str: continue
                            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                            delta = (start - now).total_seconds() / 3600
                            if live_only and not "live" in str(item).lower(): continue
                            if not live_only and not (0 <= delta <= max_hours): continue

                            home = item.get("home_team") or item.get("teams", {}).get("home", {}).get("name") or "Home"
                            away = item.get("away_team") or item.get("teams", {}).get("away", {}).get("name") or "Away"
                            matches.append({"id": f"{name}_{item.get('id', random.randint(1,99999))}",
                                            "source": name, "home": home, "away": away,
                                            "start": start, "sport": "soccer", "live": "live" in str(item).lower()})
                        except Exception:
                            continue
            except Exception as e:
                log.warning(f"{name} hata: {e}")

    log.info(f"Toplam çekilen maç: {len(matches)}")
    return matches

# ==================== AI TAHMİN ====================
async def ai_predict_markets(match):
    home, away = match["home"], match["away"]
    stats = {"home": {"form":"WWDLW","goals_avg":2.1}, "away": {"form":"LDLWW","goals_avg":1.7}}
    prompt = f"{home} vs {away}\nEv formu:{stats['home']['form']} Gol ort:{stats['home']['goals_avg']}\nDeplasman formu:{stats['away']['form']} Gol ort:{stats['away']['goals_avg']}"
    ai_resp = await openai_chat_json(prompt)
    if not ai_resp or "predictions" not in ai_resp:
        return {"predictions": [{"market":"MS","suggestion":"MS 1","confidence":70,"explanation":"Ev avantajı."}], "best":0}
    return ai_resp

# ==================== KUPON OLUŞTURMA ====================
async def build_coupon(title, max_hours, interval, max_matches, live_only=False):
    now = datetime.now(TR_TIME)
    if last_coupon_time.get(title) and (now - last_coupon_time[title]).total_seconds() < interval*3600:
        return None

    matches = await fetch_matches(max_hours, live_only)
    if not matches:
        log.info(f"{title}: Hiç maç bulunamadı.")
        return None

    results = await asyncio.gather(*[ai_predict_markets(m) for m in matches])
    evaluated = [(r["predictions"][r["best"]]["confidence"], m, r) for r, m in zip(results, matches) if r]
    if not evaluated:
        log.info(f"{title}: Hiç geçerli tahmin yok.")
        return None

    evaluated.sort(reverse=True)
    selected = evaluated[:max_matches]
    lines = []
    for score, m, res in selected:
        p = res["predictions"][res["best"]]
        analiz = await ai_turkce_analiz(f"{m['home']} vs {m['away']} için {p['suggestion']}")
        lines.append(f"{SPORT_EMOJI['soccer']} <b>{m['home']} - {m['away']}</b>\n{m['start'].astimezone(TR_TIME).strftime('%H:%M')}\n<b>{p['suggestion']}</b> (%{p['confidence']})\n<i>{analiz}</i>\n")

    last_coupon_time[title] = now
    return f"━━━━━━━━━━━\n{title}\n━━━━━━━━━━━\n" + "\n".join(lines)

# ==================== TELEGRAM ====================
async def send_coupon(ctx, title, max_hours, interval, max_matches, live_only=False):
    txt = await build_coupon(title, max_hours, interval, max_matches, live_only)
    if txt:
        await ctx.bot.send_message(CHANNEL_ID, txt, parse_mode="HTML", disable_web_page_preview=True)
        log.info(f"{title} gönderildi.")
    else:
        log.info(f"{title}: gönderim yapılmadı (maç yok).")

async def hourly(ctx): await send_coupon(ctx, "CANLI AI TAHMİN", 1, 1, 1, True)
async def daily(ctx):  await send_coupon(ctx, "GÜNLÜK AI TAHMİN", 24, 12, 3)
async def vip(ctx):    await send_coupon(ctx, "VIP AI TAHMİN", 24, 24, 3)

# ==================== FASTAPI + TELEGRAM ====================
app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()
tg.add_handler(CommandHandler("test", lambda u,c: asyncio.create_task(daily(c))))

async def lifespan(app: FastAPI):
    jq = tg.job_queue
    jq.run_repeating(lambda ctx: asyncio.create_task(hourly(ctx)), 3600, 10)
    jq.run_repeating(lambda ctx: asyncio.create_task(daily(ctx)), 43200, 20)
    jq.run_repeating(lambda ctx: asyncio.create_task(vip(ctx)), 86400, 30)
    await tg.initialize(); await tg.start()
    try:
        await tg.bot.set_webhook(WEBHOOK_URL)
    except Exception:
        log.warning("Webhook kurulamadı.")
    log.info("v38.1 AI-TÜRKÇE AKTİF ✅")
    yield
    await tg.stop(); await tg.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
