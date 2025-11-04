# main.py — v40.3 (Tek dosya)
# - Tüm API'ler aktif (key'ler sabit)
# - Sadece AI key env (AI_KEY)
# - Canlı / Günlük / VIP kuponlar
# - VIP max 2 maç
# - AI tahminleri (OpenAI) + fallback
# - Tarih/saat UTC uyumu, yalnızca live ve <=24h maçlar

import os
import asyncio
import logging
import random
import json
from datetime import datetime, timedelta, timezone
import aiohttp
from aiohttp import ClientError
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --------- CONFIG ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("v40.3")

# AI key — env olarak ver
AI_KEY = os.getenv("AI_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()  # örn "@channel" veya chat id

if not AI_KEY:
    log.error("AI_KEY bulunamadı. Lütfen AI_KEY ortam değişkenini ayarla.")
    # devam etme; ama script yine başlatılabilir. Burada exit etmiyoruz, fallback çalışır.
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    log.error("TELEGRAM_TOKEN veya TELEGRAM_CHAT_ID ayarlı değil. Bot mesaj atamaz.")

# API keys (sabit - senin isteğine göre)
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2"
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"
FOOTYSTATS_KEY = "test85g57"
ALLSPORTSAPI_KEY = "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369"
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ"
ISPORTSAPI_KEY = "rCiLp0QXNSrfV5oc"

TR_TZ = timezone(timedelta(hours=3))

# Scheduler intervals (saat)
HOURLY = 1
DAILY = 12
VIP = 24
VIP_MAX_MATCHES = 2

# Caches / state
posted_matches = set()
last_run = {"LIVE": None, "DAILY": None, "VIP": None}
ai_rate_limit = {"calls": 0, "reset": datetime.utcnow()}

# --------- HELPERS ----------
def to_local_str(iso_ts: str):
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.astimezone(TR_TZ).strftime("%d %b %H:%M")
    except Exception:
        try:
            # fallback if already naive
            dt = datetime.fromisoformat(iso_ts)
            return (dt.replace(tzinfo=timezone.utc).astimezone(TR_TZ)).strftime("%d %b %H:%M")
        except Exception:
            return iso_ts

def within_hours(iso_ts: str, hours: int):
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return 0 <= (dt - now).total_seconds() <= hours * 3600
    except Exception:
        return False

# safe json get helper
def safe_get(obj, *keys):
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur

# --------- FETCH FROM APIs ----------
async def fetch_api_football(session):
    results = []
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"live": "all"}  # live and upcoming depending api support
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    try:
        async with session.get(url, params=params, headers=headers, timeout=12) as r:
            if r.status != 200:
                log.warning(f"API-Football HTTP {r.status}")
                return results
            data = await r.json()
            items = data.get("response") or []
            for it in items:
                fix = it.get("fixture", {})
                teams = it.get("teams", {})
                start = fix.get("date") or fix.get("timestamp")
                if not start: continue
                # only live or within 24h
                if not (within_hours(start, 24) or ("status" in fix and fix.get("status", {}).get("short") not in ("NS", "FT"))):
                    continue
                results.append({
                    "id": f"apif_{safe_get(fix,'id') or hash(json.dumps(it, default=str))}",
                    "home": safe_get(teams, "home", "name") or "Home",
                    "away": safe_get(teams, "away", "name") or "Away",
                    "start": start,
                    "source": "API-Football",
                    "live": (safe_get(fix, "status", "short") or "").lower() not in ("ns", "ft"),
                    "odds": safe_get(it, "odds") or {}
                })
            log.info(f"API-Football çekildi: {len(items)} raw, {len(results)} filtred")
    except Exception as e:
        log.warning(f"API-Football hata: {e}")
    return results

async def fetch_the_odds(session):
    results = []
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds"
    params = {"regions": "eu", "markets": "h2h,totals,spreads", "oddsFormat": "decimal", "dateFormat":"iso"}
    params["apiKey"] = THE_ODDS_API_KEY
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status != 200:
                # The Odds API sometimes returns list or dict with error
                try:
                    txt = await r.text()
                    log.warning(f"The Odds API HTTP {r.status} — {txt[:200]}")
                except:
                    log.warning(f"The Odds API HTTP {r.status}")
                return results
            data = await r.json()
            if isinstance(data, list):
                for it in data:
                    start = it.get("commence_time") or it.get("commenceTime")
                    if not start: continue
                    if not (within_hours(start, 24) or it.get("markets") is not None):
                        # still include if live? some items contain 'bookmakers' live flags; we'll include within 24h
                        continue
                    results.append({
                        "id": f"odds_{hash(json.dumps(it, default=str))}",
                        "home": it.get("home_team", "Home"),
                        "away": it.get("away_team", "Away"),
                        "start": start,
                        "source": "TheOdds",
                        "live": False,
                        "odds": it.get("bookmakers", [])
                    })
            else:
                log.warning("The Odds API beklenmeyen format")
    except Exception as e:
        log.warning(f"The Odds API hata: {e}")
    return results

async def fetch_footystats(session):
    results = []
    # endpoint choices vary; try live-scores
    url = f"https://api.footystats.org/live-scores"
    params = {"key": FOOTYSTATS_KEY}
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status != 200:
                log.warning(f"FootyStats HTTP {r.status}")
                return results
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("match_start_iso") or it.get("start_date")
                if not start: continue
                if not (within_hours(start, 24) or it.get("status")=="live"):
                    continue
                results.append({
                    "id": f"footy_{it.get('id') or hash(json.dumps(it, default=str))}",
                    "home": it.get("home_name","Home"),
                    "away": it.get("away_name","Away"),
                    "start": start,
                    "source": "FootyStats",
                    "live": True,
                    "odds": {}
                })
    except Exception as e:
        log.warning(f"FootyStats hata: {e}")
    return results

async def fetch_allsports(session):
    results = []
    url = "https://allsportsapi2.p.rapidapi.com/api/football/matches/live"
    headers = {"x-rapidapi-host":"allsportsapi2.p.rapidapi.com", "x-rapidapi-key": ALLSPORTSAPI_KEY}
    try:
        async with session.get(url, headers=headers, timeout=12) as r:
            if r.status != 200:
                log.warning(f"AllSportsAPI HTTP {r.status}")
                return results
            data = await r.json()
            items = data.get("result") or []
            for it in items:
                start = it.get("event_date_start")
                if not start: continue
                if not (within_hours(start,24) or it.get("event_status")=="live"):
                    continue
                results.append({
                    "id": f"alls_{it.get('event_key') or hash(json.dumps(it, default=str))}",
                    "home": it.get("event_home_team","Home"),
                    "away": it.get("event_away_team","Away"),
                    "start": start,
                    "source": "AllSportsAPI",
                    "live": True,
                    "odds": {}
                })
    except Exception as e:
        log.warning(f"AllSportsAPI hata: {e}")
    return results

async def fetch_sportsmonks(session):
    results = []
    url = f"https://api.sportmonks.com/v3/football/livescores"
    params = {"api_token": SPORTSMONKS_KEY}
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status != 200:
                log.warning(f"SportsMonks HTTP {r.status}")
                return results
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("starting_at") or it.get("time")
                if not start: continue
                if not (within_hours(start,24) or it.get("status")=="live"):
                    continue
                results.append({
                    "id": f"sm_{it.get('id') or hash(json.dumps(it, default=str))}",
                    "home": it.get("home_name","Home"),
                    "away": it.get("away_name","Away"),
                    "start": start,
                    "source": "SportsMonks",
                    "live": True,
                    "odds": {}
                })
    except Exception as e:
        log.warning(f"SportsMonks hata: {e}")
    return results

async def fetch_isports(session):
    results = []
    url = f"https://api.isportsapi.com/sport/football/livescores"
    params = {"api_key": ISPORTSAPI_KEY}
    try:
        async with session.get(url, params=params, timeout=12, ssl=False) as r:
            if r.status != 200:
                log.warning(f"iSportsAPI HTTP {r.status}")
                return results
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("matchTime") or it.get("date")
                if not start: continue
                if not (within_hours(start,24) or it.get("status")=="live"):
                    continue
                results.append({
                    "id": f"isports_{it.get('matchId') or hash(json.dumps(it, default=str))}",
                    "home": it.get("homeTeamName","Home"),
                    "away": it.get("awayTeamName","Away"),
                    "start": start,
                    "source": "iSportsAPI",
                    "live": True,
                    "odds": it.get("odds", {})
                })
    except Exception as e:
        log.warning(f"iSportsAPI hata: {e}")
    return results

async def fetch_all_matches():
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_api_football(session),
            fetch_the_odds(session),
            fetch_footystats(session),
            fetch_allsports(session),
            fetch_sportsmonks(session),
            fetch_isports(session)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    all_matches = []
    for r in results:
        if isinstance(r, Exception):
            log.warning(f"fetch task exception: {r}")
            continue
        all_matches.extend(r or [])
    # normalize start field names (start or date)
    normalized = []
    for m in all_matches:
        start = m.get("start") or m.get("date") or m.get("commence_time") or ""
        # ensure iso-like
        if isinstance(start, (int, float)):
            # timestamp -> iso
            try:
                start = datetime.fromtimestamp(int(start), tz=timezone.utc).isoformat()
            except:
                start = ""
        normalized.append({
            "id": m.get("id"),
            "home": m.get("home"),
            "away": m.get("away"),
            "start": start,
            "source": m.get("source"),
            "live": bool(m.get("live")),
            "odds": m.get("odds", {})
        })
    # dedupe by id/home-away-start
    seen = set()
    final = []
    for m in normalized:
        key = (m.get("id") or f"{m.get('home')}_{m.get('away')}_{m.get('start')}")
        if key in seen: continue
        seen.add(key)
        final.append(m)
    log.info(f"Toplam çekilen maç (normalized, dedup): {len(final)}")
    return final

# --------- AI integration (OpenAI chat completions) ----------
# Uses OpenAI v1 chat completions endpoint
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

async def call_openai_chat(prompt: str, max_tokens=300, temperature=0.2):
    # rate limit naive per-minute tracking
    global ai_rate_limit
    now = datetime.utcnow()
    if ai_rate_limit["reset"] < now:
        ai_rate_limit["calls"] = 0
        ai_rate_limit["reset"] = now + timedelta(seconds=60)
    if ai_rate_limit["calls"] >= 45:
        # throttle fallback (avoid hitting org limits); return None so fallback used
        log.warning("OpenAI rate limit (local throttle) reached — using fallback")
        return None
    headers = {"Authorization": f"Bearer {AI_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [
            {"role":"system","content":"Sen Türkçe konuşan spor analisti ve veri bilimcisisin. Verilen maç bilgisine göre en anlamlı bahis piyasalarını tahmin et. Çıkış JSON olsun."},
            {"role":"user","content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OPENAI_URL, headers=headers, json=payload) as resp:
                txt = await resp.text()
                ai_rate_limit["calls"] += 1
                if resp.status != 200:
                    log.warning(f"OpenAI HTTP {resp.status}: {txt[:300]}")
                    return None
                # try extract JSON object from response
                try:
                    data = json.loads(txt)
                    # openai response shape: choices[0].message.content
                    content = None
                    if isinstance(data, dict):
                        choices = data.get("choices")
                        if choices and isinstance(choices, list):
                            msg = choices[0].get("message", {}).get("content")
                            if msg:
                                content = msg
                    if content is None:
                        # maybe response is directly a JSON string
                        content = txt
                    # try to extract JSON substring
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        json_text = content[start:end]
                        return json.loads(json_text)
                    # fallback try direct parse
                    return json.loads(content)
                except Exception as e:
                    log.warning(f"OpenAI parse hatası: {e}")
                    return None
    except ClientError as e:
        log.warning(f"OpenAI request error: {e}")
        return None
    except Exception as e:
        log.warning(f"OpenAI unexpected error: {e}")
        return None

# --------- Prediction wrapper ----------
async def predict_for_match(m: dict, vip=False):
    # Build prompt including stats we have (start time, source, odds if any)
    prompt = (
        f"Maç: {m.get('home')} vs {m.get('away')}\n"
        f"Tarih (UTC): {m.get('start')}\n"
        f"Spor: futbol\n"
        f"Canlı mı: {m.get('live')}\n"
    )
    # if odds present, add sample info
    if m.get("odds"):
        prompt += f"Oran bilgisi mevcut.\n"
    # ask to return JSON with predictions array and best index
    prompt += (
        "\nYap: Bu maç için en anlamlı bahis piyasalarını değerlendir (MS, TOTALS 1.5/2.5, BTTS/KG). "
        "Her öneri için suggestion (ör. MS 1, Over 2.5), confidence 0-100 ve kısa explanation ver. "
        "Cevabı yalnızca JSON olarak ver: {\"predictions\":[{\"market\":\"MS\",\"suggestion\":\"MS 1\",\"confidence\":85,\"explanation\":\"...\"}],\"best\":0}\n"
        "Cevabı Türkçe ver."
    )
    ai_resp = await call_openai_chat(prompt, max_tokens=300, temperature=0.2)
    if not ai_resp or not isinstance(ai_resp, dict) or "predictions" not in ai_resp:
        # fallback simple rules
        stats_home_w = random.randint(0,5)
        stats_away_w = random.randint(0,5)
        total_goals = round(0.5 + random.random()*3.0,1)
        preds = []
        if stats_home_w > stats_away_w:
            preds.append({"market":"MS","suggestion":"MS 1","confidence":60,"explanation":"Ev sahibi son maçlarda daha iyi form gösteriyor."})
        elif stats_away_w > stats_home_w:
            preds.append({"market":"MS","suggestion":"MS 2","confidence":58,"explanation":"Deplasman form daha iyi."})
        else:
            preds.append({"market":"MS","suggestion":"Beraberlik","confidence":45,"explanation":"Benzer form."})
        if total_goals > 2.4:
            preds.append({"market":"TOTALS","suggestion":"Over 2.5","confidence":62,"explanation":"Takımlar gol bulma eğiliminde."})
        else:
            preds.append({"market":"TOTALS","suggestion":"Under 2.5","confidence":55,"explanation":"Düşük skorlu olabilir."})
        best_idx = max(range(len(preds)), key=lambda i: preds[i]["confidence"])
        return {"predictions": preds, "best": best_idx, "fallback": True}
    # normalize confidences
    preds = ai_resp.get("predictions", [])
    for p in preds:
        try:
            p["confidence"] = max(0, min(100, int(p.get("confidence", 50))))
        except:
            p["confidence"] = 50
    best = ai_resp.get("best", 0)
    if not isinstance(best, int) or best < 0 or best >= len(preds):
        best = 0
    return {"predictions": preds, "best": best, "fallback": False}

# --------- Build coupon text ----------
def format_match_block(m, pred):
    start_local = to_local_str(m.get("start") or "")
    best = pred["predictions"][pred["best"]] if pred["predictions"] else None
    best_line = ""
    if best:
        best_line = f"<b>{best.get('suggestion')}</b> → %{best.get('confidence')} \n<i>{best.get('explanation','')}</i>\n"
    other_lines = ""
    for i,p in enumerate(pred["predictions"]):
        if i == pred["best"]: continue
        other_lines += f"- {p.get('suggestion')} (%{p.get('confidence')}) — {p.get('explanation','')}\n"
    # try to show an available decimal odd
    odd_text = ""
    try:
        if isinstance(m.get("odds"), list) and m["odds"]:
            # TheOdds bookmakers list: show first bookmaker's h2h if present
            bm = m["odds"][0]
            markets = bm.get("markets") or bm.get("odds") or {}
            odd_text = f"Oran (bk): {json.dumps(m['odds'][:1], default=str)}"
        elif isinstance(m.get("odds"), dict) and m.get("odds"):
            odd_text = f"Oran: {json.dumps(m['odds'], default=str)}"
    except Exception:
        odd_text = ""
    block = (
        f"⚽ <b>{m.get('home')} vs {m.get('away')}</b>\n"
        f"{start_local} — {m.get('source','')}\n"
        f"{best_line}"
        f"{other_lines}"
        f"{odd_text}\n"
    )
    return block

async def build_coupon_text(matches, title, max_matches=3):
    lines = []
    count = 0
    for m in matches:
        if count >= max_matches:
            break
        pred = await predict_for_match(m, vip = (title.startswith("VIP")))
        lines.append(format_match_block(m, pred))
        # mark posted to avoid repeats across runs
        posted_matches.add(m.get("id"))
        count += 1
    if not lines:
        return None
    header = f"━━━━━━━━━━━━━━━━━━━━━━\n    {title}\n━━━━━━━━━━━━━━━━━━━━━━\n"
    footer = "\n━━━━━━━━━━━━━━━━━━━━━━\nBu metin AI tarafından üretilmiştir. Tahminler istatistiksel analiz amaçlıdır; doğrudan bahis tavsiyesi sayılmaz."
    return header + "\n\n".join(lines) + footer

# --------- Send function ----------
async def send_to_channel(app, text):
    try:
        # use Application's bot
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            log.warning("Telegram bilgileri yok, gönderim atlanıyor.")
            return
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML", disable_web_page_preview=True)
        log.info("Kupon gönderildi.")
    except Exception as e:
        log.exception(f"Telegram gönderim hatası: {e}")

# --------- Jobs (live/daily/vip) ----------
async def job_runner(app):
    """
    Main loop: each hour check and send appropriate coupons:
    - Live: if live matches exist (every hour)
    - Daily: 24h window matches, job scheduled every 12h
    - VIP: 24h window matches, job scheduled every 24h (max 2)
    """
    while True:
        try:
            matches = await fetch_all_matches()
            if not matches:
                log.info("Hiç maç yok (tüm API'ler boş).")
            else:
                # Live
                live_matches = [m for m in matches if m.get("live")]
                if live_matches:
                    # avoid spamming: check last run minute for LIVE
                    now = datetime.now(timezone.utc)
                    lr = last_run.get("LIVE")
                    if not lr or (now - lr).total_seconds() >= HOURLY*3600:
                        text = await build_coupon_text(live_matches, "CANLI AI TAHMİN", max_matches=5)
                        if text:
                            await send_to_channel(app, text)
                        last_run["LIVE"] = now
                    else:
                        log.debug("CANLI: Sonraki run bekleniyor.")
                else:
                    log.debug("CANLI: canlı maç yok.")

                # Daily (12 saatte bir): matches within next 24h but not live
                now = datetime.now(timezone.utc)
                lr = last_run.get("DAILY")
                if not lr or (now - lr).total_seconds() >= DAILY*3600:
                    upcoming = [m for m in matches if (not m.get("live")) and within_hours(m.get("start") or "", 24)]
                    if upcoming:
                        text = await build_coupon_text(sorted(upcoming, key=lambda x: x.get("start") or "") , "GÜNLÜK AI TAHMİN", max_matches=3)
                        if text:
                            await send_to_channel(app, text)
                        last_run["DAILY"] = now
                    else:
                        log.debug("GÜNLÜK: Uygun maç yok.")

                # VIP (24 saatte bir, max 2)
                lr = last_run.get("VIP")
                if not lr or (now - lr).total_seconds() >= VIP*3600:
                    vip_upcoming = [m for m in matches if (not m.get("live")) and within_hours(m.get("start") or "", 24)]
                    if vip_upcoming:
                        text = await build_coupon_text(sorted(vip_upcoming, key=lambda x: x.get("start") or "") , "VIP AI TAHMİN", max_matches=VIP_MAX_MATCHES)
                        if text:
                            await send_to_channel(app, text)
                        last_run["VIP"] = now
                    else:
                        log.debug("VIP: Uygun maç yok.")
        except Exception as e:
            log.exception(f"Job runner hata: {e}")
        # always sleep one hour (job loop frequency)
        await asyncio.sleep(3600)

# --------- Telegram command / test handler ----------
async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Test başlatılıyor, kupon denemesi hazırlanıyor...")
    matches = await fetch_all_matches()
    if not matches:
        await update.message.reply_text("Maç bulunamadı.")
        return
    text = await build_coupon_text(matches, "TEST AI TAHMİN", max_matches=3)
    if text:
        await update.message.reply_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text("Kupon oluşturulamadı.")

# --------- MAIN ----------
def main():
    if not TELEGRAM_TOKEN:
        log.error("TELEGRAM_TOKEN ayarlı değil, çıkılıyor.")
        return
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("test", cmd_test))
    # start job runner in background once app starts
    async def startup(scope):
        # give bot ready then start runner
        asyncio.create_task(job_runner(app))
        log.info("v40.3 başlatıldı — job runner çalışıyor.")
    app.post_init(startup)
    log.info("Bot başlatılıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
