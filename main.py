# bot.py - v64.2 - TheOdds + Sportsdata düzeltmesi (tam - job'lar korunmuştur)
import os
import asyncio
import logging
import json
import signal
from datetime import datetime, timedelta, timezone

import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import Conflict

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger("STAKEZONE-AI v64.2")

# Telegram ve AI anahtarları ENV'den çekilir veya buradaki yedek kullanılır
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1001234567890")
AI_KEY = os.getenv("AI_KEY", "sk-...")

# --- API Anahtarları (Sizin Tarafınızdan Sağlanan/Kullanılan Değerler) ---
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "e35c566553ae8a89972f76ab04c16bd2")
THE_ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY", "0180c1cbedb086bdcd526bc0464ee771")
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "80a354c67b694ef79c516182ad64aed7")
# Sportradar kaldırıldı; yerine Sportsdata key eklendi
SPORTS_DATA_KEY = os.getenv("SPORTS_DATA_KEY", "32524949c0784f19a8a19c5d5f90e5d2")
# ------------------------------------------------------------------------

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o"
TR_TZ = timezone(timedelta(hours=3))

posted_matches = {}
last_run = {}
ai_calls = 0
ai_reset = datetime.now(timezone.utc)

# ---------------- ZAMAN ----------------
def now_utc(): return datetime.now(timezone.utc)
def to_tr(iso):
    try: return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TR_TZ).strftime("%d.%m %H:%M")
    except: return "?"
def in_range(iso, min_h, max_h):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
        return min_h <= (dt - now_utc()).total_seconds() / 3600 <= max_h
    except: return False

# ---------------- API'LER ----------------

async def fetch_api_football(session):
    today = now_utc().strftime("%Y-%m-%d")
    tomorrow = (now_utc() + timedelta(days=1)).strftime("%Y-%m-%d")
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"from": today, "to": tomorrow, "timezone": "Europe/Istanbul"}
    try:
        async with session.get(url, params=params, headers=headers, timeout=25) as r:
            if r.status != 200:
                log.error(f"API-Football Hata: {r.status} - {await r.text()}")
                return []
            data = await r.json()
            matches = []
            for f in data.get("response", []):
                fix = f.get("fixture", {})
                start = fix.get("date")
                if not start or not in_range(start, -3, 72): continue
                teams = f.get("teams", {})
                league = f.get("league", {}).get("name", "Lig")
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
        log.error(f"API-Football: {e}")
        return []

async def fetch_theodds(session):
    # DÜZELTME: doğru TheOdds rota (soccer)
    url = "https://api.the-odds-api.com/v4/sports/soccer/odds"
    today = now_utc().strftime("%Y-%m-%d")
    params = {
        "apiKey": THE_ODDS_API_KEY,
        "regions": "eu,us,tr",
        "markets": "h2h,totals,btts",
        "oddsFormat": "decimal",
        "date": today
    }
    try:
        async with session.get(url, params=params, timeout=30) as r:
            if r.status != 200:
                log.error(f"TheOdds Hata: {r.status} - {await r.text()}")
                return []
            data = await r.json()
            matches = []
            for game in data:
                start = game.get("commence_time")
                if not start or not in_range(start, -3, 72): continue
                home = game.get("home_team")
                away = game.get("away_team")
                if not home or not away: continue
                matches.append({
                    "id": f"odds_{game.get('id')}",
                    "home": home,
                    "away": away,
                    "start": start,
                    "live": False,
                    "odds": game.get("bookmakers", []),
                    "source": "TheOdds",
                    "league": game.get("sport_nice", "Futbol")
                })
            log.info(f"TheOdds: {len(matches)} maç (eu+us+tr)")
            return matches
    except Exception as e:
        log.error(f"TheOdds hata: {e}")
        return []

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

# ------------------ SPORTS DATA ------------------
async def fetch_sportsdata(session):
    today = now_utc().strftime("%Y-%m-%d")
    url = f"https://api.sportsdata.io/v4/soccer/scores/json/GamesByDate/{today}"
    headers = {"Ocp-Apim-Subscription-Key": SPORTS_DATA_KEY}
    matches = []
    try:
        async with session.get(url, headers=headers, timeout=25) as r:
            if r.status == 404:
                log.warning("Sportsdata: GamesByDate kapalı, GamesBySeason/EPL/2025 deneniyor...")
                url2 = "https://api.sportsdata.io/v4/soccer/scores/json/GamesBySeason/EPL/2025"
                async with session.get(url2, headers=headers, timeout=25) as r2:
                    if r2.status == 200:
                        data = await r2.json()
                    else:
                        log.warning(f"Sportsdata fallback başarısız: {r2.status} - {await r2.text()}")
                        return []
            elif r.status != 200:
                log.warning(f"Sportsdata Hata: {r.status} - {await r.text()}")
                return []
            else:
                data = await r.json()
            for m in data:
                start = m.get("Day") or m.get("DateTime") or m.get("DayTime")
                if not start or not in_range(start, -3, 72): continue
                home = m.get("HomeTeamName") or m.get("HomeTeam")
                away = m.get("AwayTeamName") or m.get("AwayTeam")
                if not home or not away: continue
                status = m.get("Status") or m.get("GameState") or ""
                live = status in ["InProgress", "Live", "InProgressCritical"]
                comp = m.get("Competition")
                if isinstance(comp, dict):
                    league = comp.get("Name") or comp.get("CompetitionName") or "Sportsdata Ligi"
                else:
                    league = comp or "Sportsdata Ligi"
                matches.append({
                    "id": f"sd_{m.get('GameId') or m.get('Id')}",
                    "home": home,
                    "away": away,
                    "start": start,
                    "live": live,
                    "odds": [],
                    "source": "Sportsdata",
                    "league": league
                })
            log.info(f"Sportsdata: {len(matches)} maç")
            return matches
    except Exception as e:
        log.error(f"Sportsdata hata: {e}")
        return []

# ---------------- TÜM MATCH TOPLAMA ----------------
async def fetch_all_matches():
    async with aiohttp.ClientSession() as s:
        results = await asyncio.gather(
            fetch_api_football(s),
            fetch_theodds(s),
            fetch_football_data(s),
            fetch_sportsdata(s),
            return_exceptions=True
        )
    all_matches = [m for res in results if isinstance(res, list) for m in res]
    seen = set()
    unique = []
    for m in all_matches:
        key = (m.get("home",""), m.get("away",""), str(m.get("start",""))[:16])
        if key not in seen and m.get("home") and m.get("away"):
            seen.add(key)
            unique.append(m)
    log.info(f"TOPLAM MAÇ: {len(unique)}")
    return unique

# ---------------- ORAN / AI / KUPON (AYNI) ----------------
def get_odd(m, suggestion):
    if m["source"] != "TheOdds": return None
    for book in m.get("odds", []):
        for market in book.get("markets", []):
            outcomes = market["outcomes"]
            if market["key"] == "h2h":
                if "1" in suggestion and any(o["name"] == m["home"] for o in outcomes):
                    return round([o["price"] for o in outcomes if o["name"] == m["home"]][0], 2)
                if "2" in suggestion and any(o["name"] == m["away"] for o in outcomes):
                    return round([o["price"] for o in outcomes if o["name"] == m["away"]][0], 2)
                if "X" in suggestion and any(o["name"] == "Draw" for o in outcomes):
                    return round([o["price"] for o in outcomes if o["name"] == "Draw"][0], 2)
            if market["key"] == "totals" and "Over" in suggestion:
                return round([o["price"] for o in outcomes if "Over" in o["name"]][0], 2)
            if market["key"] == "btts" and "KG Var" in suggestion:
                return round([o["price"] for o in outcomes if o["name"] == "Yes"][0], 2)
    return None

async def predict_match(m):
    global ai_calls, ai_reset
    now = now_utc()
    if now > ai_reset: ai_calls, ai_reset = 0, now + timedelta(minutes=1)
    if ai_calls >= 8: await asyncio.sleep(3); return None
    ai_calls += 1
    prompt = f"Maç: {m['home']} vs {m['away']} | Lig: {m['league']} | {to_tr(m['start'])} | Canlı: {'Evet' if m['live'] else 'Hayır'}\nEn iyi 1 tahmin (MS 1, Over 2.5, KG Var vb.)\nJSON: {{\"suggestion\": \"MS 1\", \"confidence\": 85, \"explanation\": \"...\"}}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(OPENAI_URL, json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 120}, headers={"Authorization": f"Bearer {AI_KEY}"}, timeout=15) as r:
                if r.status != 200: return None
                txt = (await r.json())["choices"][0]["message"]["content"]
                return json.loads(txt[txt.find("{"):txt.rfind("}")+1])
    except: return None

async def build_coupon(matches, title, max_n, min_conf, type_name):
    candidates = []
    now = now_utc()
    for m in matches:
        mid = str(m["id"])
        if mid in posted_matches and (now - posted_matches[mid]).total_seconds() < 7200: continue
        pred = await predict_match(m)
        if not pred or pred["confidence"] < min_conf: continue
        odd = get_odd(m, pred["suggestion"])
        if type_name == "DAILY" and odd and odd > 2.1: continue
        candidates.append((m, pred, odd))
    candidates.sort(key=lambda x: x[1]["confidence"], reverse=True)
    selected = candidates[:max_n]
    if not selected: return None
    lines = []
    for m, pred, odd in selected:
        lines.append(
            f"<b>{m['home']} vs {m['away']}</b>\n"
            f"   {to_tr(m['start'])} | {m['league']}\n"
            f"   <b>{pred['suggestion']}</b> (%{pred['confidence']})\n"
            f"   Oran: <b>{odd or 'Yok'}</b>\n"
            f"   <i>{pred['explanation']}</i>"
        )
        posted_matches[str(m["id"])] = now
    return f"{title}\n{'─' * 32}\n" + "\n\n".join(lines) + f"\n{'─' * 32}\n<i>Sorumluluk size aittir.</i>"

# ---------------- GÖREVLER ----------------
async def job_runner(app):
    await asyncio.sleep(15)
    while True:
        try:
            matches = await fetch_all_matches()
            now = now_utc()
            if "VIP" not in last_run or (now - last_run["VIP"]).total_seconds() > 3*3600:
                text = await build_coupon(matches, "VIP SÜRPRİZ KUPON", 1, 84, "VIP")
                if text: await app.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="HTML")
                last_run["VIP"] = now
            if "DAILY" not in last_run or (now - last_run["DAILY"]).total_seconds() > 12*3600:
                text = await build_coupon(matches, "GÜNLÜK GARANTİ KUPON", 3, 72, "DAILY")
                if text: await app.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="HTML")
                last_run["DAILY"] = now
            if "LIVE" not in last_run or (now - last_run["LIVE"]).total_seconds() > 3600:
                live = [m for m in matches if m["live"]]
                if live:
                    text = await build_coupon(live, "CANLI FIRSAT KUPON", 2, 80, "LIVE")
                    if text: await app.bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="HTML")
                last_run["LIVE"] = now
            await asyncio.sleep(60)
        except Exception as e:
            log.exception(f"Job error: {e}")
            await asyncio.sleep(60)

# ---------------- TEST ----------------
async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Maçlar çekiliyor...")
    matches = await fetch_all_matches()
    if not matches:
        await update.message.reply_text("Maç yok. API anahtarlarını kontrol et.")
        return
    lines = [f"<b>{len(matches)} MAÇ BULUNDU</b>"]
    for m in matches[:5]:
        lines.append(f"• {m['home']} vs {m['away']} | {to_tr(m['start'])} | Kaynak: {m['source']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# ---------------- ZOMBİ ÖLDÜRÜCÜ ----------------
def main():
    if not all([TELEGRAM_TOKEN, AI_KEY, TELEGRAM_CHAT_ID]):
        log.critical("ENV EKSİK!")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("test", cmd_test))

    async def post_init(application):
        asyncio.create_task(job_runner(application))

    app.post_init = post_init

    # ZOMBİ BOT ÖLDÜRÜCÜ
    async def error_handler(update, context):
        if isinstance(context.error, Conflict):
            log.critical("ZOMBİ BOT TESPİT EDİLDİ! 3 saniye içinde kapanıyor...")
            await asyncio.sleep(3)
            os._exit(0)  # TEMİZ KAPAN

    app.add_error_handler(error_handler)

    log.info("STAKEZONE-AI v64.2 ZOMBİ ÖLDÜRÜCÜ BAŞLADI")
    
    # RAILWAY İÇİN ÖZEL POLLING
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        timeout=30,
        poll_interval=2.0,
        bootstrap_retries=3
    )

if __name__ == "__main__":
    main()
