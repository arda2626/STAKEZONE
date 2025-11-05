import os
import asyncio
import logging
import json
import re
from datetime import datetime, timedelta, timezone

import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("v63.1 - HATASIZ GERÇEK BOT")

AI_KEY = os.getenv("AI_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# GERÇEK API ANAHTARLARI
API_FOOTBALL_KEY = "e35c566553ae8a89972f76ab04c16bd2"
THE_ODDS_API_KEY = "0180c1cbedb086bdcd526bc0464ee771"
FOOTBALL_DATA_KEY = "80a354c67b694ef79c516182ad64aed7"

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o"

TR_TZ = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

VIP_INTERVAL_HOURS = 3
DAILY_INTERVAL_HOURS = 12
LIVE_INTERVAL_HOURS = 1

MIN_CONFIDENCE = 70
LIVE_MIN_CONFIDENCE = 85
DAILY_MAX_ODDS = 2.0

posted_matches = {}
last_run = {}
ai_calls = 0
ai_reset = NOW_UTC

# ---------------- HELPERS ----------------
def to_local_str(iso_ts):
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.astimezone(TR_TZ).strftime("%d.%m %H:%M")
    except: return "Bilinmiyor"

def within_time_range(iso_ts, min_h, max_h):
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = (dt - now).total_seconds() / 3600
        return min_h <= delta <= max_h
    except: return False

def safe_get(d, *keys):
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d

# ---------------- GERÇEK API ----------------
async def fetch_api_football(session):
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"from": NOW_UTC.strftime("%Y-%m-%d"), "to": (NOW_UTC + timedelta(days=3)).strftime("%Y-%m-%d")}
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    try:
        async with session.get(url, params=params, headers=headers, timeout=15) as r:
            if r.status != 200: return []
            data = await r.json()
            matches = []
            for f in data.get("response", []):
                fix = f.get("fixture", {})
                start = fix.get("date")
                if not within_time_range(start, 0, 72): continue
                matches.append({
                    "id": fix.get("id"),
                    "home": safe_get(f, "teams", "home", "name"),
                    "away": safe_get(f, "teams", "away", "name"),
                    "start": start,
                    "live": safe_get(fix, "status", "short") in ["1H", "2H", "HT", "LIVE"],
                    "odds": f.get("odds", []),
                    "source": "API-Football"
                })
            return matches
    except Exception as e:
        log.warning(f"API-Football hata: {e}")
        return []

async def fetch_theodds(session):
    url = "https://api.the-odds-api.com/v4/sports/soccer/odds"
    params = {"apiKey": THE_ODDS_API_KEY, "regions": "eu", "markets": "h2h,totals,btts", "oddsFormat": "decimal"}
    try:
        async with session.get(url, params=params, timeout=15) as r:
            if r.status != 200: return []
            data = await r.json()
            matches = []
            for game in data:
                start = game.get("commence_time")
                if not within_time_range(start, 0, 72): continue
                matches.append({
                    "id": game.get("id"),
                    "home": game.get("home_team"),
                    "away": game.get("away_team"),
                    "start": start,
                    "live": False,
                    "odds": game.get("bookmakers", []),
                    "source": "TheOdds"
                })
            return matches
    except Exception as e:
        log.warning(f"TheOdds hata: {e}")
        return []

async def fetch_football_data(session):
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
    params = {"dateFrom": NOW_UTC.strftime("%Y-%m-%d"), "dateTo": (NOW_UTC + timedelta(days=3)).strftime("%Y-%m-%d")}
    try:
        async with session.get(url, params=params, headers=headers, timeout=15) as r:
            if r.status != 200: return []
            data = await r.json()
            matches = []
            for m in data.get("matches", []):
                start = m.get("utcDate")
                if not within_time_range(start, 0, 72): continue
                matches.append({
                    "id": m.get("id"),
                    "home": safe_get(m, "homeTeam", "name"),
                    "away": safe_get(m, "awayTeam", "name"),
                    "start": start,
                    "live": m.get("status") == "IN_PLAY",
                    "odds": [],
                    "source": "Football-Data"
                })
            return matches
    except Exception as e:
        log.warning(f"Football-Data hata: {e}")
        return []

async def fetch_all_real_matches():
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_api_football(session),
            fetch_theodds(session),
            fetch_football_data(session)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_matches = []
    for res in results:
        if isinstance(res, list):
            all_matches.extend(res)
    
    seen = set()
    unique = []
    for m in all_matches:
        key = (m["home"], m["away"], m["start"][:16])
        if key not in seen:
            seen.add(key)
            unique.append(m)
    
    log.info(f"Toplam gerçek maç: {len(unique)}")
    return unique

# ---------------- ORAN ÇEKME ----------------
def get_odd(m, suggestion):
    odds = m.get("odds", [])
    if m["source"] == "TheOdds":
        for book in odds:
            for market in book.get("markets", []):
                if market["key"] == "h2h" and "1" in suggestion:
                    for o in market["outcomes"]:
                        if o["name"] == m["home"]:
                            return o["price"]
    return None

# ---------------- OPENAI TAHMİN ----------------
async def predict_match(m):
    global ai_calls, ai_reset
    now = datetime.now(timezone.utc)
    if now > ai_reset:
        ai_calls = 0
        ai_reset = now + timedelta(minutes=1)
    if ai_calls >= 8: 
        await asyncio.sleep(5)
        return None
    ai_calls += 1

    prompt = f"""
Maç: {m['home']} vs {m['away']}
Başlama: {to_local_str(m['start'])} (TR)
Canlı: {'Evet' if m['live'] else 'Hayır'}

En iyi 1 bahis tahmini yap.
JSON formatı:
{{"suggestion": "MS 1", "confidence": 85, "explanation": "Kısa analiz..."}}
"""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(OPENAI_URL, json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 150
            }, headers={"Authorization": f"Bearer {AI_KEY}"}) as r:
                if r.status != 200: return None
                data = await r.json()
                content = data["choices"][0]["message"]["content"]
                start = content.find("{")
                end = content.rfind("}") + 1
                return json.loads(content[start:end])
    except Exception as e:
        log.warning(f"OpenAI hata: {e}")
        return None

# ---------------- KUPON OLUŞTUR ----------------
async def build_coupon(matches, title, max_n, min_conf, coupon_type):
    candidates = []
    now = datetime.now(timezone.utc)
    for m in matches:
        mid = str(m["id"])
        if mid in posted_matches and (now - posted_matches[mid]).total_seconds() < 7200:
            continue
        pred = await predict_match(m)
        if not pred or pred["confidence"] < min_conf:
            continue
        odd = get_odd(m, pred["suggestion"])
        if coupon_type == "DAILY" and odd and odd > DAILY_MAX_ODDS:
            continue
        candidates.append((m, pred, odd))
    
    candidates.sort(key=lambda x: x[1]["confidence"], reverse=True)
    selected = candidates[:max_n]
    
    if not selected: return None
    
    lines = []
    for m, pred, odd in selected:
        odd_text = f"Oran: <b>{odd:.2f}</b>" if odd else "Oran: Bilinmiyor"
        lines.append(
            f"<b>{m['home']} vs {m['away']}</b>\n"
            f"   {to_local_str(m['start'])} | {'CANLI' if m['live'] else 'Öncesi'}\n"
            f"   <b>{pred['suggestion']}</b> (%{pred['confidence']})\n"
            f"   {odd_text}\n"
            f"   <i>{pred['explanation']}</i>"
        )
        posted_matches[str(m["id"])] = now
    
    header = f"{' '.join(title.split())}\n{'─'*30}\n"
    footer = f"\n{'─'*30}\n<i>Sorumluluk size aittir.</i>"
    return header + "\n\n".join(lines) + footer

# ---------------- GÖREVLER ----------------
async def job_runner(app: Application):
    await asyncio.sleep(10)
    while True:
        try:
            matches = await fetch_all_real_matches()
            now = datetime.now(timezone.utc)

            # VIP
            if "VIP" not in last_run or (now - last_run["VIP"]).total_seconds() > VIP_INTERVAL_HOURS*3600:
                text = await build_coupon(matches, "VIP SÜRPRİZ", 1, 85, "VIP")
                if text: await app.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="HTML")
                last_run["VIP"] = now

            # GÜNLÜK
            if "DAILY" not in last_run or (now - last_run["DAILY"]).total_seconds() > DAILY_INTERVAL_HOURS*3600:
                text = await build_coupon(matches, "GÜNLÜK GARANTİ", 3, 75, "DAILY")
                if text: await app.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="HTML")
                last_run["DAILY"] = now

            # CANLI
            if "LIVE" not in last_run or (now - last_run["LIVE"]).total_seconds() > LIVE_INTERVAL_HOURS*3600:
                live_matches = [m for m in matches if m["live"]]
                if live_matches:
                    text = await build_coupon(live_matches, "CANLI FIRSAT", 2, 80, "LIVE")
                    if text: await app.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="HTML")
                last_run["LIVE"] = now

            await asyncio.sleep(60)
        except Exception as e:
            log.exception(f"Job hatası: {e}")
            await asyncio.sleep(60)

# ---------------- TEST KOMUTU ----------------
async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Test başlatılıyor...")
    matches = await fetch_all_real_matches()
    text = await build_coupon(matches, "TEST KUPON", 3, 70, "TEST")
    if text:
        await update.message.reply_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text("Kupon oluşturulamadı.")

# ---------------- ANA ----------------
def main():
    if not all([TELEGRAM_TOKEN, AI_KEY, TELEGRAM_CHAT_ID]):
        log.critical("ENV eksik! TELEGRAM_TOKEN, AI_KEY, TELEGRAM_CHAT_ID gerekli.")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("test", cmd_test))

    # post_init ile job_runner'ı başlat
    async def post_init(application: Application):
        asyncio.create_task(job_runner(application))

    app.post_init = post_init

    log.info("v63.1 - HATASIZ BOT BAŞLADI")
    # BURASI KRİTİK: await YOK, SENKRON!
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()  # asyncio.run DEĞİL!
