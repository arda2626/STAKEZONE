# bot.py - v69.0 - Sambanova LLM (OpenAI Uyumlu)
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

# ***************************************************************
# 🔴 UYARI: SAMBANOVA_URL değişkenini, panelinizden aldığınız 
# kesin adrese ayarlamanız GEREKMEKTEDİR.
# ***************************************************************

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger("STAKEZONE-AI v69.0")

# Telegram anahtarı ENV'den çekilir veya buradaki yedek kullanılır
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8393964009:AAE6BnaKNyLYk3KahAL2k9ABOkdL7eFIb7s")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1001234567890")

# --- AI Anahtarları (Sambanova) ---
SAMBANOVA_KEY = os.getenv("SAMBANOVA_KEY", "2d9ff014-9759-4166-bed7-bfaf5f411ced") # ENTEGRE EDİLDİ
SAMBANOVA_URL = os.getenv("SAMBANOVA_URL", "https://api.sambanova.ai/v1/chat/completions") # Lütfen Sambanova panelinizden KONTROL EDİN
MODEL = "sambanova-llm" # Sambanova Model Adı (Gerekiyorsa güncelleyin)
# ------------------------------------------------------------------------

# --- Spor API Anahtarları (Korundu) ---
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "3838237ec41218c2572ce541708edcfd") 
THE_ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY", "0180c1cbedb086bdcd526bc0464ee771")
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "80a354c67b694ef79c516182ad64aed7")
SPORTS_DATA_KEY = os.getenv("SPORTS_DATA_KEY", "32524949c0784f19a8a19c5d5f90e5d2")
ISPORTS_API_KEY = os.getenv("ISPORTS_API_KEY", "rCiLp0QXNSrfV5oc") 
SPORTMONKS_API_KEY = os.getenv("SPORTMONKS_API_KEY", "cbcas9S9m69LZOcIUR591VpWVjwgppjsLI0o3u9XSnCLWUTqxQbhmpXXXXpD")
# ------------------------------------------------------------------------

TR_TZ = timezone(timedelta(hours=3))
SYSTEM_PROMPT = (
    "Sen, STAKEZONE-AI adlı yapay zeka tarafından yönetilen, üst düzey bir kumarbaz, bahis tahmincisi, "
    "spor yorumcusu ve yapay zeka geliştiricisinin asistanısın. Birincil hedefin, sana sunulan her futbol maçı için "
    "en güvenilir, bilimsel verilere dayalı ve doğru tahmini yapmaktır. Bu, sadece istatistik değil, aynı zamanda "
    "takım formunu, oyuncu sakatlıklarını, lig bağlamını ve API'lerden gelen güncel oranları da dikkate almayı gerektirir. "
    "Yanıt formatın (suggestion, confidence, explanation) zorunludur ve tahminlerin yüksek güvenilirlikte olmalıdır. "
    "Açıklamalarında, tahminini destekleyen temel veri ve analitik sebeplere odaklan. Duygusallıktan kaçın, tamamen veri ve olasılığa dayalı hareket et."
)

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

# ---------------- API'LER (KORUNDU) ----------------
# API'ler (API-Football, TheOdds, Football-Data, Sportsdata, iSports, Sportmonks) önceki versiyonlardan
# hataları düzeltilmiş şekilde korunmuştur. AI entegrasyonu aşağıdadır.

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
    url = "https://api.the-odds-api.com/v4/sports/soccer/odds"
    params = {
        "apiKey": THE_ODDS_API_KEY,
        "regions": "eu,us", 
        "markets": "h2h,totals,btts",
        "oddsFormat": "decimal",
        "daysFrom": 3 
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
            log.info(f"TheOdds: {len(matches)} maç (eu+us)")
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

async def fetch_sportsdata(session):
    log.warning("Sportsdata API, sürekli 404 hatası verdiği için şimdilik devre dışı.")
    return []

async def fetch_isports(session):
    url = "https://api.isportsapi.com/sport/football/schedule"
    today = now_utc().strftime("%Y-%m-%d")
    params = {
        "api_key": ISPORTS_API_KEY,
        "date": today,
        "sclassid": "all" 
    }
    matches = []
    try:
        async with session.get(url, params=params, timeout=20, ssl=False) as r:
            if r.status != 200:
                log.error(f"iSports Hata: {r.status} - {await r.text()}")
                return []
            data = await r.json()
            if data.get("code") == 0 and data.get("data"):
                 for m in data["data"]:
                    start = m.get("matchtime") 
                    if not start or not in_range(start, -3, 72): continue
                    matches.append({
                        "id": f"is_{m.get('id')}",
                        "home": m.get("homeName", "Ev Sahibi"),
                        "away": m.get("awayName", "Deplasman"),
                        "start": start,
                        "live": m.get("state") == "playing",
                        "odds": [],
                        "source": "iSports",
                        "league": m.get("sclassName", "iSports Ligi")
                    })
            log.info(f"iSports: {len(matches)} maç")
            return matches
    except Exception as e:
        log.error(f"iSports hata: {e}")
        return []

async def fetch_sportmonks(session):
    url = "https://api.sportmonks.com/v3/football/fixtures/upcoming"
    params = {
        "api_token": SPORTMONKS_API_KEY,
        "include": "participants;league",
        "per_page": 50 
    }
    matches = []
    try:
        async with session.get(url, params=params, timeout=20) as r:
            if r.status != 200:
                log.error(f"Sportmonks Hata: {r.status} - {await r.text()}")
                return []
            data = await r.json()
            for m in data.get("data", []):
                start = m.get("starting_at")
                if not start or not in_range(start, -3, 72): continue
                
                participants_data = m.get("participants", {}).get("data", [])
                teams = {p["meta"]["location"]: p["name"] for p in participants_data if p.get("meta", {}).get("location")}
                league = m.get("league", {}).get("data", {}).get("name", "Sportmonks Ligi")
                
                matches.append({
                    "id": f"sm_{m.get('id')}",
                    "home": teams.get("home", "Ev Sahibi"),
                    "away": teams.get("away", "Deplasman"),
                    "start": start,
                    "live": m.get("state") == "Live",
                    "odds": [],
                    "source": "Sportmonks",
                    "league": league
                })
            log.info(f"Sportmonks: {len(matches)} maç")
            return matches
    except Exception as e:
        log.error(f"Sportmonks hata: {e}")
        return []

# ---------------- TÜM MATCH TOPLAMA ----------------
async def fetch_all_matches():
    async with aiohttp.ClientSession() as s:
        results = await asyncio.gather(
            fetch_api_football(s),
            fetch_theodds(s),
            fetch_football_data(s),
            fetch_sportsdata(s), 
            fetch_isports(s),
            fetch_sportmonks(s),
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

# ---------------- ORAN / AI / KUPON ----------------
def get_odd(m, suggestion):
    if m["source"] != "TheOdds": return None
    for book in m.get("odds", []):
        for market in book.get("markets", []):
            outcomes = market["outcomes"]
            if market["key"] == "h2h":
                if ("1" in suggestion or m["home"] in suggestion) and any(o["name"] == m["home"] for o in outcomes):
                    return round([o["price"] for o in outcomes if o["name"] == m["home"]][0], 2)
                if ("2" in suggestion or m["away"] in suggestion) and any(o["name"] == m["away"] for o in outcomes):
                    return round([o["price"] for o in outcomes if o["name"] == m["away"]][0], 2)
                if "X" in suggestion and any(o["name"] == "Draw" for o in outcomes):
                    return round([o["price"] for o in outcomes if o["name"] == "Draw"][0], 2)
            if market["key"] == "totals" and "Over" in suggestion:
                over_outcome = next((o["price"] for o in outcomes if "Over" in o["name"]), None)
                if over_outcome: return round(over_outcome, 2)
            if market["key"] == "btts" and ("KG Var" in suggestion or "Yes" in suggestion):
                return round([o["price"] for o in outcomes if o["name"] == "Yes"][0], 2)
    return None

async def predict_match(m):
    global ai_calls, ai_reset
    now = now_utc()
    if now > ai_reset: ai_calls, ai_reset = 0, now + timedelta(minutes=1)
    if ai_calls >= 8: 
        log.warning("AI Rate Limit uyarısı! 3 saniye bekleniyor.")
        await asyncio.sleep(3); return None
    ai_calls += 1
    
    odds_info = ""
    if m["source"] == "TheOdds" and m["odds"]:
        h2h_odds = []
        for book in m["odds"]:
            for market in book.get("markets", []):
                if market["key"] == "h2h":
                    odds_dict = {o["name"]: o["price"] for o in market["outcomes"]}
                    home_o = odds_dict.get(m["home"])
                    away_o = odds_dict.get(m["away"])
                    draw_o = odds_dict.get("Draw")
                    if home_o and away_o and draw_o:
                        h2h_odds.append(f"{m['home']} ({home_o}), Beraberlik ({draw_o}), {m['away']} ({away_o})")
                        break
            if h2h_odds: break
        if h2h_odds: odds_info = f" | Mevcut H2H Oranları: {h2h_odds[0]}"

    user_prompt = (
        f"Maç: {m['home']} vs {m['away']} | Lig: {m['league']} | {to_tr(m['start'])} | Canlı: {'Evet' if m['live'] else 'Hayır'}"
        f"{odds_info}\nEn iyi 1 tahmin (MS 1, Over 2.5, KG Var vb.)\nJSON: {{\"suggestion\": \"MS 1\", \"confidence\": 85, \"explanation\": \"...\"}}"
    )
    
    try:
        # Sambanova API Çağrısı (OpenAI formatında)
        async with aiohttp.ClientSession() as s:
            async with s.post(
                SAMBANOVA_URL, 
                json={
                    "model": MODEL, 
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ], 
                    "temperature": 0.3, 
                    "max_tokens": 120
                }, 
                headers={"Authorization": f"Bearer {SAMBANOVA_KEY}"}, 
                timeout=15
            ) as r:
                if r.status != 200: 
                    log.error(f"Sambanova API Hata: {r.status} - {await r.text()}")
                    return None
                
                # Yanıtın OpenAI formatında olduğunu varsayıyoruz
                response_data = await r.json()
                if not response_data.get("choices"):
                    log.error(f"Sambanova yanıtı beklenenden farklı: {response_data}")
                    return None
                    
                txt = response_data["choices"][0]["message"]["content"]
                
                # JSON Ayıklama
                start_index = txt.find("{")
                end_index = txt.rfind("}") + 1
                if start_index == -1 or end_index == -1:
                    log.error(f"Sambanova JSON Parse Error: {txt}")
                    return None
                return json.loads(txt[start_index:end_index])
    except Exception as e: 
        log.error(f"Sambanova Tahmin Hatası: {e}")
        return None

async def build_coupon(matches, title, max_n, min_conf, type_name):
    candidates = []
    now = now_utc()
    for m in matches:
        mid = str(m["id"])
        if mid in posted_matches and (now - posted_matches[mid]).total_seconds() < 7200: continue
        
        pred = await predict_match(m)
        if not pred or pred.get("confidence", 0) < min_conf: continue
        
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
        
    return f"🔥 {title} (v69.0 - Sambanova)\n{'─' * 32}\n" + "\n\n".join(lines) + f"\n{'─' * 32}\n<i>Sorumluluk size aittir.</i>"

# ---------------- GÖREVLER, TEST ve MAIN ----------------

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

async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.message.chat_id) != str(TELEGRAM_CHAT_ID):
        await update.message.reply_text("Bu komutu sadece yetkili kanalda kullanabilirsiniz.")
        return
        
    await update.message.reply_text("Maçlar çekiliyor...")
    matches = await fetch_all_matches()
    if not matches:
        await update.message.reply_text("Maç yok. API anahtarlarını veya maç aralığını kontrol et.")
        return
        
    test_match = matches[0]
    await update.message.reply_text(f"İlk maç için AI tahmini çekiliyor (Sambanova): {test_match['home']} vs {test_match['away']}")
    
    pred = await predict_match(test_match)
    
    if pred:
        lines = [f"<b>{len(matches)} MAÇ BULUNDU</b>", f"<b>AI TEST SONUCU ({test_match['source']})</b>"]
        lines.append(f"• Tahmin: {pred['suggestion']} (%{pred['confidence']})")
        lines.append(f"• Açıklama: <i>{pred['explanation']}</i>")
        lines.append("\n<b>İLK 5 MAÇIN KAYNAĞI:</b>")
        for m in matches[:5]:
            lines.append(f"• {m['home']} vs {m['away']} | {to_tr(m['start'])} | Kaynak: {m['source']}")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    else:
        await update.message.reply_text("Maçlar bulundu, ancak AI tahmininde bir hata oluştu (Sambanova API hatası, Rate Limit vb.). Lütfen API URL'sini ve kota durumunu kontrol edin.")

def main():
    if not all([TELEGRAM_TOKEN, SAMBANOVA_KEY, TELEGRAM_CHAT_ID]):
        log.critical("ENV EKSİK! Lütfen TELEGRAM_TOKEN, SAMBANOVA_KEY ve TELEGRAM_CHAT_ID değerlerini kontrol edin.")
        return

    try:
        if not TELEGRAM_CHAT_ID.startswith("-100"):
            log.warning("TELEGRAM_CHAT_ID bir kanal ID'si (genellikle -100 ile başlar) gibi görünmüyor. Botun kanala gönderme yetkisini kontrol edin.")
    except:
        pass


    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("test", cmd_test))

    async def post_init(application):
        asyncio.create_task(job_runner(application))

    app.post_init = post_init

    async def error_handler(update, context):
        if isinstance(context.error, Conflict):
            log.critical("ZOMBİ BOT TESPİT EDİLDİ! 3 saniye içinde kapanıyor...")
            await asyncio.sleep(3)
            os._exit(0) 

    app.add_error_handler(error_handler)

    log.info("STAKEZONE-AI v69.0 ZOMBİ ÖLDÜRÜCÜ BAŞLADI")
    
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        timeout=30,
        poll_interval=2.0,
        bootstrap_retries=3
    )

if __name__ == "__main__":
    main()
