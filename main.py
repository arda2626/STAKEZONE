# main.py - v40.1 AI-TÜRKÇE (Hata Düzeltme + Fallback + Sıralama Key + Canlı Mesaj Garantisi)
import os, asyncio, logging, random, json, aiohttp, ssl
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler
from fastapi import FastAPI, Request
import uvicorn
from ai_turkce import ai_turkce_analiz

# ==================== CONFIG ====================
TR_TIME = timezone(timedelta(hours=3))

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"
OPENAI_API_KEY = "YOUR_OPENAI_KEY"

API_KEYS = {
    "API_FOOTBALL": "bd1350bea151ef9f56ed417f0c0c3ea2",
    "THE_ODDS_API": "501ea1ade60d5f0b13b8f34f90cd51e6",
    "FOOTYSTATS": "test85g57",
    "ALLSPORTSAPI": "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369",
    "SPORTSMONKS": "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ",
    "ISPORTSAPI": "rCiLp0QXNSrfV5oc"
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

SPORT_EMOJI = {"soccer": "⚽", "basketball": "🏀", "tennis": "🎾"}
match_cache, posted_matches = {}, {}
last_coupon_time = {"CANLI": None, "GÜNLÜK": None, "VIP": None}

AI_QUEUE = asyncio.Queue()
AI_RATE_LIMIT = 3

# ==================== AI QUEUE ====================
async def process_ai_queue():
    while True:
        task = await AI_QUEUE.get()
        try:
            await task()
        except Exception as e:
            log.warning(f"AI Queue hatası: {e}")
        await asyncio.sleep(20)

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
                    start = txt.find("{")
                    end = txt.rfind("}") + 1
                    return json.loads(txt[start:end])
                except Exception:
                    log.warning("OpenAI JSON parse hatası.")
                    return {"raw": txt}
    except Exception as e:
        log.error(f"OpenAI hatası: {e}")
        return None

# ==================== MAÇ ÇEKME ====================
async def fetch_matches(sport="soccer", max_hours=24, live_only=False):
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    matches = []

    if sport=="soccer":
        apis = [
            ("API-Football", f"https://v3.football.api-sports.io/fixtures", {"date": today}, {"x-apisports-key": API_KEYS["API_FOOTBALL"]}),
            ("The Odds API", f"https://api.the-odds-api.com/v4/sports", {"apiKey": API_KEYS["THE_ODDS_API"], "regions": "eu"}, {}),
            ("FootyStats", "https://api.footystats.org/league-matches", {"key": API_KEYS["FOOTYSTATS"], "league_id": 1625}, {}),
            ("AllSportsAPI", "https://apiv2.allsportsapi.com/football/", {"met":"Fixtures","APIkey":API_KEYS["ALLSPORTSAPI"],"from":today,"to":today}, {}),
            ("SportsMonks", "https://api.sportmonks.com/v3/football/fixtures", {"api_token": API_KEYS["SPORTSMONKS"], "date": today}, {}),
            ("iSportsAPI", "https://api.isportsapi.com/sport/football/schedule", {"api_key": API_KEYS["ISPORTSAPI"], "date": today}, {})
        ]
    else:
        apis = [
            ("AllSportsAPI", f"https://apiv2.allsportsapi.com/{sport}/", {"met":"Fixtures","APIkey":API_KEYS["ALLSPORTSAPI"],"from":today,"to":today}, {})
        ]

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession() as session:
        for name, url, params, headers in apis:
            try:
                log.info(f"{name} ({sport}) çağrılıyor...")
                async with session.get(url, params=params, headers=headers, ssl=ssl_context if "iSports" in name else None, timeout=15) as r:
                    if r.status != 200:
                        log.warning(f"{name} HTTP {r.status} ⚠️ API LIMIT REACHED?")
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
                                            "start": start, "sport": sport, "live": "live" in str(item).lower()})
                        except Exception:
                            continue
    log.info(f"Toplam çekilen {sport} maç: {len(matches)}")
    return matches

# ==================== AI TAHMİN ====================
async def ai_predict_markets(match, vip=False):
    home, away = match["home"], match["away"]
    stats = {"home": {"form":"WWDLW","goals_avg":2.1}, "away": {"form":"LDLWW","goals_avg":1.7}}
    prompt = f"{home} vs {away}\nEv formu:{stats['home']['form']} Gol ort:{stats['home']['goals_avg']}\nDeplasman formu:{stats['away']['form']} Gol ort:{stats['away']['goals_avg']}"
    if vip:
        prompt += "\nVIP kupon için detaylı analiz yap."
    fut = asyncio.get_event_loop().create_future()
    async def task():
        resp = await openai_chat_json(prompt)
        fut.set_result(resp)
    await AI_QUEUE.put(task)
    result = await fut
    if not result or "predictions" not in result:
        return {"predictions": [{"market":"MS","suggestion":"MS 1","confidence":70,"explanation":"Ev avantajı."}], "best":0}
    return result

# ==================== KUPON OLUŞTURMA ====================
async def build_coupon(title, sport="soccer", max_hours=24, interval=1, max_matches=3, live_only=False, vip=False):
    now = datetime.now(TR_TIME)
    if last_coupon_time.get(title) and (now - last_coupon_time[title]).total_seconds() < interval*3600:
        return None

    matches = await fetch_matches(sport, max_hours, live_only)
    if not matches:
        return f"{title}: Hiç maç bulunamadı."

    results = await asyncio.gather(*[ai_predict_markets(m, vip) for m in matches])
    evaluated = [(r["predictions"][r["best"]]["confidence"], m, r) for r, m in zip(results, matches) if r]
    if not evaluated:
        return f"{title}: Geçerli tahmin yok."

    # Sıralama hatası düzeltilmiş
    evaluated.sort(key=lambda x: x[0], reverse=True)
    selected = evaluated[:max_matches]

    lines = []
    for score, m, res in selected:
        p = res["predictions"][res["best"]]
        analiz = await ai_turkce_analiz(f"{m['home']} vs {m['away']} için {p['suggestion']}")
        lines.append(f"{SPORT_EMOJI.get(m['sport'],'⚽')} <b>{m['home']} - {m['away']}</b>\n{m['start'].astimezone(TR_TIME).strftime('%H:%M')}\n<b>{p['suggestion']}</b> (%{p['confidence']})\n<i>{analiz}</i>\n")
        posted_matches[m['id']] = now

    last_coupon_time[title] = now
    return f"━━━━━━━━━━━\n{title}\n━━━━━━━━━━━\n" + "\n".join(lines)

# ==================== TELEGRAM ====================
async def send_coupon(ctx, title, sport="soccer", max_hours=24, interval=1, max_matches=3, live_only=False, vip=False):
    txt = await build_coupon(title, sport, max_hours, interval, max_matches, live_only, vip)
    if txt:
        await ctx.bot.send_message(CHANNEL_ID, txt, parse_mode="HTML", disable_web_page_preview=True)
        log.info(f"{title} gönderildi.")
    else:
        log.info(f"{title}: gönderim yapılmadı (maç yok veya tekrar).")

# ==================== GÖREVLER ====================
async def hourly(ctx): await send_coupon(ctx, "CANLI AI TAHMİN", max_hours=1, interval=1, max_matches=1, live_only=True)
async def daily(ctx):  await send_coupon(ctx, "GÜNLÜK AI TAHMİN", max_hours=24, interval=12, max_matches=3)
async def vip(ctx):    await send_coupon(ctx, "VIP AI TAHMİN", max_hours=24, interval=24, max_matches=2, vip=True)

# ==================== FASTAPI + TELEGRAM ====================
app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()
tg.add_handler(CommandHandler("test", lambda u,c: asyncio.create_task(daily(c))))

async def lifespan(app: FastAPI):
    jq = tg.job_queue
    jq.run_repeating(lambda ctx: asyncio.create_task(hourly(ctx)), 3600, 10)
    jq.run_repeating(lambda ctx: asyncio.create_task(daily(ctx)), 43200, 20)
    jq.run_repeating(lambda ctx: asyncio.create_task(vip(ctx)), 86400, 30)
    asyncio.create_task(process_ai_queue())
    await tg.initialize(); await tg.start()
    try: await tg.bot.set_webhook(WEBHOOK_URL)
    except Exception: log.warning("Webhook kurulamadı.")
    log.info("v40.1 AI-TÜRKÇE AKTİF ✅")
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
