# bot.py - v63.3 - TÜM LİGLER + GERÇEK ORAN + AI KUPON
import os
import asyncio
import logging
import json
from datetime import datetime, timedelta, timezone

import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger("v63.3 - TÜM LİGLER BOTU")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1001234567890")
AI_KEY = os.getenv("AI_KEY", "sk-...")  # OpenAI API Key

# API ANAHTARLARI
API_FOOTBALL_KEY = "e35c566553ae8a89972f76ab04c16bd2"
THE_ODDS_API_KEY = "0180c1cbedb086bdcd526bc0464ee771"
FOOTBALL_DATA_KEY = "80a354c67b694ef79c516182ad64aed7"

# OpenAI
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o"

# Zaman
TR_TZ = timezone(timedelta(hours=3))

# Scheduler
VIP_INTERVAL = 3 * 3600    # 3 saat
DAILY_INTERVAL = 12 * 3600 # 12 saat
LIVE_INTERVAL = 1 * 3600   # 1 saat

# Filtreler
MIN_CONF = 70
LIVE_MIN_CONF = 82
MAX_DAILY_ODDS = 2.1

# State
posted_matches = {}
last_run = {}
ai_calls = 0
ai_reset = datetime.now(timezone.utc)

# ---------------- ZAMAN ----------------
def now_utc():
    return datetime.now(timezone.utc)

def to_tr(iso):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(TR_TZ).strftime("%d.%m %H:%M")
    except: return "?"

def in_range(iso, min_h, max_h):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = (dt - now_utc()).total_seconds() / 3600
        return min_h <= delta <= max_h
    except: return False

# ---------------- API: API-FOOTBALL (TÜM LİGLER) ----------------
async def fetch_api_football(session):
    today = now_utc().strftime("%Y-%m-%d")
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"date": today, "timezone": "Europe/Istanbul"}
    try:
        async with session.get(url, params=params, headers=headers, timeout=25) as r:
            if r.status != 200: return []
            data = await r.json()
            matches = []
            for f in data.get("response", []):
                fix = f.get("fixture", {})
                start = fix.get("date")
                if not start or not in_range(start, -3, 72): continue
                teams = f.get("teams", {})
                league = f.get("league", {}).get("name", "Bilinmeyen Lig")
                matches.append({
                    "id": f"af_{fix.get('id')}",
                    "home": teams.get("home", {}).get("name"),
                    "away": teams.get("away", {}).get("name"),
                    "start": start,
                    "live": fix.get("status", {}).get("short") in ["1H", "2H", "HT", "LIVE"],
                    "odds": [],
                    "source": "API-Football",
                    "league": league
                })
            log.info(f"API-Football: {len(matches)} maç")
            return matches
    except Exception as e:
        log.error(f"API-Football hata: {e}")
        return []

# ---------------- API: THEODDS (TÜM LİGLER - soccer) ----------------
async def fetch_theodds_all(session):
    url = "https://api.the-odds-api.com/v4/sports/odds"
    params = {
        "apiKey": THE_ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h,totals,btts",
        "oddsFormat": "decimal",
        "sport": "soccer"
    }
    try:
        async with session.get(url, params=params, timeout=25) as r:
            if r.status != 200: return []
            data = await r.json()
            matches = []
            for game in data:
                start = game.get("commence_time")
                if not start or not in_range(start, -3, 72): continue
                matches.append({
                    "id": f"odds_{game.get('id')}",
                    "home": game.get("home_team"),
                    "away": game.get("away_team"),
                    "start": start,
                    "live": False,
                    "odds": game.get("bookmakers", []),
                    "source": "TheOdds",
                    "league": game.get("sport_nice", "Futbol")
                })
            log.info(f"TheOdds: {len(matches)} maç")
            return matches
    except Exception as e:
        log.error(f"TheOdds hata: {e}")
        return []

# ---------------- API: FOOTBALL-DATA (5 BÜYÜK LİG) ----------------
async def fetch_football_data(session):
    comps = ["PL", "BL1", "SA", "FL1", "PD"]
    today = now_utc().strftime("%Y-%m-%d")
    day_after = (now_utc() + timedelta(days=2)).strftime("%Y-%m-%d")
    headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
    all_matches = []
    for comp in comps:
        url = f"https://api.football-data.org/v4/competitions/{comp}/matches"
        params = {"dateFrom": today, "dateTo": day_after}
        try:
            async with session.get(url, params=params, headers=headers, timeout=15) as r:
                if r.status != 200: continue
                data = await r.json()
                for m in data.get("matches", []):
                    start = m.get("utcDate")
                    if not start or not in_range(start, -3, 72): continue
                    all_matches.append({
                        "id": f"fd_{m.get('id')}",
                        "home": m.get("homeTeam", {}).get("name"),
                        "away": m.get("awayTeam", {}).get("name"),
                        "start": start,
                        "live": m.get("status") == "IN_PLAY",
                        "odds": [],
                        "source": "Football-Data",
                        "league": m.get("competition", {}).get("name", comp)
                    })
        except: pass
    log.info(f"Football-Data: {len(all_matches)} maç")
    return all_matches

# ---------------- TÜM MAÇLARI ÇEK ----------------
async def fetch_all_matches():
    async with aiohttp.ClientSession() as s:
        results = await asyncio.gather(
            fetch_api_football(s),
            fetch_theodds_all(s),
            fetch_football_data(s),
            return_exceptions=True
        )
    all_matches = []
    for res in results:
        if isinstance(res, list):
            all_matches.extend(res)
    
    # Tekilleştir
    seen = set()
    unique = []
    for m in all_matches:
        key = (m.get("home", ""), m.get("away", ""), m.get("start", "")[:16])
        if key not in seen and m.get("home") and m.get("away"):
            seen.add(key)
            unique.append(m)
    
    log.info(f"TOPLAM MAÇ: {len(unique)}")
    return unique

# ---------------- ORAN ÇEK ----------------
def get_odd(m, suggestion):
    if m["source"] != "TheOdds": return None
    for book in m.get("odds", []):
        for market in book.get("markets", []):
            key = market["key"]
            outcomes = market["outcomes"]
            if key == "h2h":
                if "1" in suggestion:
                    for o in outcomes:
                        if o["name"] == m["home"]:
                            return round(o["price"], 2)
                elif "2" in suggestion:
                    for o in outcomes:
                        if o["name"] == m["away"]:
                            return round(o["price"], 2)
                elif "X" in suggestion:
                    for o in outcomes:
                        if o["name"] == "Draw":
                            return round(o["price"], 2)
            elif key == "totals" and "Over" in suggestion:
                for o in outcomes:
                    if "Over" in o["name"]:
                        return round(o["price"], 2)
            elif key == "btts" and "KG Var" in suggestion:
                for o in outcomes:
                    if o["name"] == "Yes":
                        return round(o["price"], 2)
    return None

# ---------------- OPENAI TAHMİN ----------------
async def predict_match(m):
    global ai_calls, ai_reset
    now = now_utc()
    if now > ai_reset:
        ai_calls = 0
        ai_reset = now + timedelta(minutes=1)
    if ai_calls >= 8:
        await asyncio.sleep(3)
        return None
    ai_calls += 1

    prompt = f"""
Maç: {m['home']} vs {m['away']}
Lig: {m['league']}
Başlama: {to_tr(m['start'])} (TR)
Canlı: {'Evet' if m['live'] else 'Hayır'}

En iyi 1 bahis tahmini yap (MS 1, MS X, MS 2, Over 2.5, KG Var vb.)
JSON döndür:
{{"suggestion": "MS 1", "confidence": 85, "explanation": "Kısa analiz..."}}
"""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(OPENAI_URL, json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 120
            }, headers={"Authorization": f"Bearer {AI_KEY}"}, timeout=15) as r:
                if r.status != 200: return None
                data = await r.json()
                txt = data["choices"][0]["message"]["content"]
                start = txt.find("{")
                end = txt.rfind("}") + 1
                return json.loads(txt[start:end])
    except Exception as e:
        log.warning(f"AI hata: {e}")
        return None

# ---------------- KUPON OLUŞTUR ----------------
async def build_coupon(matches, title, max_n, min_conf, type_name):
    candidates = []
    now = now_utc()
    for m in matches:
        mid = str(m["id"])
        if mid in posted_matches and (now - posted_matches[mid]).total_seconds() < 7200:
            continue
        pred = await predict_match(m)
        if not pred or pred["confidence"] < min_conf:
            continue
        odd = get_odd(m, pred["suggestion"])
        if type_name == "DAILY" and odd and odd > MAX_DAILY_ODDS:
            continue
        candidates.append((m, pred, odd))
    
    candidates.sort(key=lambda x: x[1]["confidence"], reverse=True)
    selected = candidates[:max_n]
    if not selected: return None
    
    lines = []
    for m, pred, odd in selected:
        odd_text = f"Oran: <b>{odd}</b>" if odd else "Oran: Yok"
        lines.append(
            f"<b>{m['home']} vs {m['away']}</b>\n"
            f"   {to_tr(m['start'])} | {m['league']}\n"
            f"   <b>{pred['suggestion']}</b> (%{pred['confidence']})\n"
            f"   {odd_text}\n"
            f"   <i>{pred['explanation']}</i>"
        )
        posted_matches[str(m["id"])] = now
    
    header = f"{title}\n{'─' * 32}\n"
    footer = f"\n{'─' * 32}\n<i>Sorumluluk size aittir.</i>"
    return header + "\n\n".join(lines) + footer

# ---------------- GÖREVLER ----------------
async def job_runner(app):
    await asyncio.sleep(10)
    while True:
        try:
            matches = await fetch_all_matches()
            now = now_utc()

            # VIP
            if "VIP" not in last_run or (now - last_run["VIP"]).total_seconds() > VIP_INTERVAL:
                text = await build_coupon(matches, "VIP SÜRPRİZ KUPON", 1, 84, "VIP")
                if text: await app.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="HTML")
                last_run["VIP"] = now

            # GÜNLÜK
            if "DAILY" not in last_run or (now - last_run["DAILY"]).total_seconds() > DAILY_INTERVAL:
                text = await build_coupon(matches, "GÜNLÜK GARANTİ KUPON", 3, 72, "DAILY")
                if text: await app.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="HTML")
                last_run["DAILY"] = now

            # CANLI
            if "LIVE" not in last_run or (now - last_run["LIVE"]).total_seconds() > LIVE_INTERVAL:
                live = [m for m in matches if m["live"]]
                if live:
                    text = await build_coupon(live, "CANLI FIRSAT KUPON", 2, 80, "LIVE")
                    if text: await app.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="HTML")
                last_run["LIVE"] = now

            await asyncio.sleep(60)
        except Exception as e:
            log.exception(f"Job hatası: {e}")
            await asyncio.sleep(60)

# ---------------- KOMUTLAR ----------------
async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tüm liglerden maçlar çekiliyor...")
    matches = await fetch_all_matches()
    if not matches:
        await update.message.reply_text("Maç bulunamadı. API anahtarlarını kontrol et.")
        return
    lines = [f"<b>TEST: {len(matches)} MAÇ BULUNDU</b>"]
    for m in matches[:3]:
        lines.append(f"• {m['home']} vs {m['away']} | {to_tr(m['start'])} | {m['source']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# ---------------- ANA ----------------
def main():
    if not all([TELEGRAM_TOKEN, AI_KEY, TELEGRAM_CHAT_ID]):
        log.critical("ENV eksik: TELEGRAM_TOKEN, AI_KEY, TELEGRAM_CHAT_ID")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("test", cmd_test))

    async def post_init(application):
        asyncio.create_task(job_runner(application))

    app.post_init = post_init
    log.info("v63.3 - TÜM LİGLER BOTU BAŞLADI")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
