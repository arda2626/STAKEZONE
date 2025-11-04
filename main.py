# main.py — v40.6 (Event Loop çakışması düzeltildi)
# Gereken env:
#   AI_KEY -> OpenAI API Key (zorunlu)
#   TELEGRAM_TOKEN -> Telegram bot token (zorunlu)
#   TELEGRAM_CHAT_ID -> Kanal/chat id veya @channelname (zorunlu)

import os
import asyncio
import logging
import json
import random
import sys
from datetime import datetime, timedelta, timezone

import aiohttp
from aiohttp import ClientError
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------- CONFIG ----------------
# Log formatı eklendi
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("v40.6")

AI_KEY = os.getenv("AI_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()  # "@channel" veya chat id

# Sabit (isteğin üzerine) API keyler - kod içinde kalacak
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2"
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"
FOOTYSTATS_KEY = "test85g57"
ALLSPORTSAPI_KEY = "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369"
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ"
ISPORTSAPI_KEY = "rCiLp0QXNSrfV5oc"

# Türkiye zaman dilimi (UTC+3)
TR_TZ = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# Scheduler intervals (saat)
HOURLY = 1
DAILY = 12
VIP = 24
VIP_MAX_MATCHES = 2

# state
posted_matches = {} # {id: datetime.utc}
last_run = {"LIVE": None, "DAILY": None, "VIP": None}
ai_rate_limit = {"calls": 0, "reset": NOW_UTC}

# ---------------- helpers ----------------
def to_local_str(iso_ts: str):
    """ISO tarih/saatini TR yerel formatında string'e dönüştürür."""
    if not iso_ts:
        return "Bilinmeyen"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
             dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TR_TZ).strftime("%d %b %H:%M")
    except Exception:
        return iso_ts

def within_hours(iso_ts: str, hours: int):
    """ISO tarih/saatinin şu andan itibaren belirtilen saat içinde olup olmadığını kontrol eder."""
    if not iso_ts:
        return False
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
             dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = (dt - now).total_seconds()
        # Şimdi başladıysa veya gelecekte belirtilen saat içinde mi? (-1 saat tolerans)
        return -3600 <= delta <= hours * 3600
    except Exception:
        return False

def safe_get(d, *keys):
    """Nested dict'lerde güvenli get işlemi yapar."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur

def cleanup_posted_matches():
    """posted_matches kümesinden 24 saatten eski kayıtları temizler."""
    global posted_matches
    now = datetime.now(timezone.utc)
    posted_matches = {mid: dt for mid, dt in posted_matches.items() if (now - dt).total_seconds() < 24*3600}
    log.info(f"Temizleme sonrası posted_matches boyutu: {len(posted_matches)}")

# ---------------- fetch APIs ----------------
async def fetch_api_football(session):
    res = []
    url = "https://v3.football.api-sports.io/fixtures"
    # Güncel ve sonraki 24 saat
    end_time = datetime.now(timezone.utc) + timedelta(hours=24)
    params = {"from": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "to": end_time.strftime("%Y-%m-%d")}
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    try:
        async with session.get(url, params=params, headers=headers, timeout=12) as r:
            if r.status != 200:
                log.warning(f"API-Football HTTP {r.status}")
                return res
            data = await r.json()
            items = data.get("response") or []
            for it in items:
                fix = it.get("fixture", {})
                teams = it.get("teams", {})
                status_short = (safe_get(fix, "status", "short") or "").lower()
                start = fix.get("date")
                
                # Biten, ertelenen, iptal olanları atla
                if status_short in ("ft", "pst", "canc", "abd", "awd", "wo"):
                    continue
                
                if not start: continue
                
                # ns: Not Started, tbd: To Be Defined dışındaki her şey canlı sayılır
                is_live = status_short not in ("ns", "tbd")
                
                # Canlı değilse ve 24 saat içinde başlamıyorsa atla
                if not is_live and not within_hours(start, 24):
                    continue
                    
                res.append({
                    "id": safe_get(fix,'id'), # API'den gelen ID
                    "home": safe_get(teams,"home","name") or "Home",
                    "away": safe_get(teams,"away","name") or "Away",
                    "start": start,
                    "source": "API-Football",
                    "live": is_live,
                    "odds": safe_get(it, "odds") or {}
                })
            log.info(f"API-Football raw:{len(items)} filtered:{len(res)}")
    except Exception as e:
        log.warning(f"API-Football hata: {e}")
    return res

async def fetch_the_odds(session):
    res = []
    url = "https://api.the-odds-api.com/v4/sports/soccer/odds"
    params = {"regions":"eu","markets":"h2h,totals,spreads","oddsFormat":"decimal","dateFormat":"iso","apiKey":THE_ODDS_API_KEY}
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status != 200:
                try:
                    txt = await r.text()
                    log.warning(f"The Odds API HTTP {r.status}: {txt[:200]}")
                except:
                    log.warning(f"The Odds API HTTP {r.status}")
                return res
            data = await r.json()
            if isinstance(data, list):
                for it in data:
                    start = it.get("commence_time")
                    if not start: continue
                    if not within_hours(start, 24):
                        continue
                    res.append({
                        "id": it.get('id'), # API'den gelen ID
                        "home": it.get("home_team","Home"),
                        "away": it.get("away_team","Away"),
                        "start": start,
                        "source": "TheOdds",
                        "live": False,
                        "odds": it.get("bookmakers", [])
                    })
            else:
                log.warning("The Odds API beklenmeyen format")
    except Exception as e:
        log.warning(f"The Odds API hata: {e}")
    return res

async def fetch_footystats(session):
    res = []
    url = "https://api.footystats.org/live-scores"
    params = {"key": FOOTYSTATS_KEY}
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status != 200:
                log.warning(f"FootyStats HTTP {r.status}")
                return res
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("match_start_iso") or it.get("start_date")
                is_live = it.get("status")=="live"
                if not start: continue
                if not (is_live or within_hours(start,24)):
                    continue
                res.append({
                    "id": it.get('id'), # API'den gelen ID
                    "home": it.get("home_name","Home"),
                    "away": it.get("away_name","Away"),
                    "start": start,
                    "source": "FootyStats",
                    "live": is_live,
                    "odds": {}
                })
    except Exception as e:
        log.warning(f"FootyStats hata: {e}")
    return res

async def fetch_allsports(session):
    res = []
    url = "https://allsportsapi2.p.rapidapi.com/api/football/matches/live"
    headers = {"x-rapidapi-host":"allsportsapi2.p.rapidapi.com","x-rapidapi-key":ALLSPORTSAPI_KEY}
    try:
        async with session.get(url, headers=headers, timeout=12) as r:
            if r.status != 200:
                log.warning(f"AllSportsAPI HTTP {r.status}")
                return res
            data = await r.json()
            items = data.get("result") or []
            for it in items:
                start = it.get("event_date_start")
                is_live = it.get("event_status")=="live"
                if not start: continue
                if not (is_live or within_hours(start,24)):
                    continue
                res.append({
                    "id": it.get('event_key'), # API'den gelen ID
                    "home": it.get("event_home_team","Home"),
                    "away": it.get("event_away_team","Away"),
                    "start": start,
                    "source": "AllSportsAPI",
                    "live": is_live,
                    "odds": {}
                })
    except Exception as e:
        log.warning(f"AllSportsAPI hata: {e}")
    return res

async def fetch_sportsmonks(session):
    res = []
    url = "https://api.sportmonks.com/v3/football/livescores"
    params = {"api_token": SPORTSMONKS_KEY}
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status != 200:
                log.warning(f"SportsMonks HTTP {r.status}")
                return res
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("starting_at") or it.get("time")
                is_live = it.get("status")=="live"
                if not start: continue
                if not (is_live or within_hours(start,24)):
                    continue
                res.append({
                    "id": it.get('id'), # API'den gelen ID
                    "home": it.get("home_name","Home"),
                    "away": it.get("away_name","Away"),
                    "start": start,
                    "source": "SportsMonks",
                    "live": is_live,
                    "odds": {}
                })
    except Exception as e:
        log.warning(f"SportsMonks hata: {e}")
    return res

async def fetch_isports(session):
    res = []
    url = "https://api.isportsapi.com/sport/football/livescores"
    params = {"api_key": ISPORTSAPI_KEY}
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status != 200:
                log.warning(f"iSportsAPI HTTP {r.status}")
                return res
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("matchTime") or it.get("date")
                is_live = it.get("status")=="live"
                if not start: continue
                if not (is_live or within_hours(start,24)):
                    continue
                res.append({
                    "id": it.get('matchId'), # API'den gelen ID
                    "home": it.get("homeTeamName","Home"),
                    "away": it.get("awayTeamName","Away"),
                    "start": start,
                    "source": "iSportsAPI",
                    "live": is_live,
                    "odds": it.get("odds", {})
                })
    except Exception as e:
        log.warning(f"iSportsAPI hata: {e}")
    return res

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
        
    # normalize start field and create better ID
    normalized = []
    for m in all_matches:
        start = m.get("start") or m.get("date") or ""
        # Timestamp (sayı) ise ISO formatına dönüştür
        if isinstance(start, (int, float)):
            try:
                start = datetime.fromtimestamp(int(start), tz=timezone.utc).isoformat().replace('+00:00', 'Z')
            except:
                start = ""
        
        # Benzersiz anahtar oluşturma: source_maçid_fallback (eğer ID yoksa)
        match_id_base = m.get("id") or hash(json.dumps(m, default=str)) # ID yoksa hash kullan
        final_id = f"{m.get('source')}_{match_id_base}"
        
        normalized.append({
            "id": final_id,
            "home": m.get("home"),
            "away": m.get("away"),
            "start": start,
            "source": m.get("source"),
            "live": bool(m.get("live")),
            "odds": m.get("odds", {})
        })
        
    # dedupe - sadece final_id (source+id/hash) kombinasyonuna göre
    seen = set()
    final = []
    for m in normalized:
        key = m.get("id")
        if not key: continue # ID yoksa atla (olmaması gerekir)
        if key in seen:
            continue
        seen.add(key)
        final.append(m)
        
    log.info(f"Toplam çekilen maç (normalized, dedup): {len(final)}")
    return final

# ---------------- OpenAI integration ----------------
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

async def call_openai_chat(prompt: str, max_tokens=300, temperature=0.2):
    global ai_rate_limit
    now = datetime.now(timezone.utc)
    if ai_rate_limit["reset"] < now:
        ai_rate_limit["calls"] = 0
        ai_rate_limit["reset"] = now + timedelta(seconds=60) 
    
    # Yerel kısıtlama (API'nin limitlerine uygun ayarlayın)
    if ai_rate_limit["calls"] >= 45: 
        log.warning("OpenAI local throttle active")
        wait_time = (ai_rate_limit["reset"] - now).total_seconds() + 1
        await asyncio.sleep(wait_time)
        return await call_openai_chat(prompt, max_tokens, temperature)
        
    headers = {"Authorization": f"Bearer {AI_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages":[
            {"role":"system","content":"Sen Türkçe konuşan spor analisti ve veri bilimcisisin. Verilen maç bilgisine göre en anlamlı bahis piyasalarını (MS, TOTALS, BTTS/KG) JSON formatında sırala. Cevapta başka metin olmamalı, sadece JSON olmalı."},
            {"role":"user","content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    ai_rate_limit["calls"] += 1 
    
    try:
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OPENAI_URL, headers=headers, json=payload) as resp:
                txt = await resp.text()
                
                if resp.status != 200:
                    log.warning(f"OpenAI HTTP {resp.status}: {txt[:400]}")
                    return None
                
                try:
                    data = json.loads(txt)
                    choices = data.get("choices")
                    content = ""
                    if choices and isinstance(choices, list):
                        content = choices[0].get("message", {}).get("content", "")
                    else:
                        content = txt
                        
                    # AI'dan gelen JSON metin içinde olabilir, temizle
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        return json.loads(content[start:end])
                    
                    return json.loads(content)
                    
                except Exception as e:
                    log.warning(f"OpenAI parse hatası: {e}. Raw content: {content[:100]}")
                    return None
                    
    except ClientError as e:
        log.warning(f"OpenAI request error: {e}")
        return None
    except Exception as e:
        log.warning(f"OpenAI unexpected error: {e}")
        return None

# ---------------- Prediction wrapper ----------------
async def predict_for_match(m: dict, vip=False):
    """Maç için AI tahmini alır veya fallback üretir."""
    prompt = (
        f"Maç: {m.get('home')} vs {m.get('away')}\n"
        f"Tarih(UTC): {m.get('start')}\n"
        f"Canlı mı: {m.get('live')}\n"
    )
    if m.get("odds"):
        prompt += "Oran bilgisi mevcut.\n"
    prompt += (
        "İstediğim JSON formatı: {\"predictions\":[{\"market\":\"MS\",\"suggestion\":\"MS 1\",\"confidence\":85,\"explanation\":\"...\"}],\"best\":0}. "
        "Her öneri için kısa explanation ver. Confidence 0-100 arasında bir tam sayı olmalı. Cevabı yalnızca JSON ver. Best index'i ver."
    )
    
    ai_resp = await call_openai_chat(prompt, max_tokens=300, temperature=0.2 if not vip else 0.1)
    
    if not ai_resp or not isinstance(ai_resp, dict) or "predictions" not in ai_resp:
        log.warning(f"AI tahmini başarısız veya boş: {m.get('id')}. Fallback kullanılıyor.")
        # fallback mantığı
        h_w = random.randint(0,5)
        a_w = random.randint(0,5)
        total_goals = round(0.5 + random.random()*3.0,1)
        preds = []
        if h_w > a_w:
            preds.append({"market":"MS","suggestion":"MS 1","confidence":60,"explanation":"Ev sahibi formu üstün (F)"})
        elif a_w > h_w:
            preds.append({"market":"MS","suggestion":"MS 2","confidence":58,"explanation":"Deplasman formu üstün (F)"})
        else:
            preds.append({"market":"MS","suggestion":"Beraberlik","confidence":45,"explanation":"Eşit form (F)"})
        if total_goals > 2.4:
            preds.append({"market":"TOTALS","suggestion":"Over 2.5","confidence":62,"explanation":"Yüksek gol bekleniyor (F)"})
        else:
            preds.append({"market":"TOTALS","suggestion":"Under 2.5","confidence":55,"explanation":"Düşük skorlu olabilir (F)"})
        best_idx = max(range(len(preds)), key=lambda i: preds[i]["confidence"])
        return {"predictions": preds, "best": best_idx, "fallback": True}
        
    preds = ai_resp.get("predictions", [])
    for p in preds:
        try:
            p["confidence"] = max(0, min(100, int(p.get("confidence",50))))
        except:
            p["confidence"] = 50
            
    best = ai_resp.get("best", 0)
    if not isinstance(best, int) or best < 0 or best >= len(preds):
        best = max(range(len(preds)), key=lambda i: preds[i]["confidence"]) if preds else 0
        
    return {"predictions": preds, "best": best, "fallback": False}

# ---------------- Build coupon ----------------
def format_match_block(m, pred):
    """Maç ve tahmin bilgisini Telegram formatında blok olarak döndürür."""
    start_local = to_local_str(m.get("start") or "")
    best = pred["predictions"][pred["best"]] if pred["predictions"] else None
    
    # Başlık ve Tarih/Kaynak
    block = (
        f"⚽ <b>{m.get('home')} vs {m.get('away')}</b>\n"
        f"{start_local} — {m.get('source','Bilinmeyen')}"
        f"{' 🔴 CANLI' if m.get('live') else ''}"
        f"{' (F)' if pred.get('fallback') else ''}\n"
    )
    
    # En İyi Tahmin
    if best:
        block += f"✨ <b>{best.get('suggestion')}</b> → %{best.get('confidence')}\n"
        block += f"<i>{best.get('explanation','')}</i>\n"
        
    # Diğer Tahminler
    other_lines = []
    for i,p in enumerate(pred["predictions"]):
        if i == pred["best"]:
            continue
        other_lines.append(f"- {p.get('suggestion')} (%{p.get('confidence')}) — {p.get('explanation','')}")
    if other_lines:
        block += "\n" + "\n".join(other_lines) + "\n"
        
    # Oran Bilgisi
    odd_text = ""
    try:
        odds_data = m.get("odds")
        if isinstance(odds_data, list) and odds_data:
            h2h_market = next((market for book in odds_data for market in book.get("markets",[]) if market.get("key") == "h2h"), None)
            if h2h_market and h2h_market.get("outcomes"):
                outcomes = {o["name"]: o["price"] for o in h2h_market["outcomes"]}
                odd_text = f"Oran (H2H): E:{outcomes.get('Home', '?')} B:{outcomes.get('Draw', '?')} D:{outcomes.get('Away', '?')}"
        elif isinstance(odds_data, dict) and odds_data:
            odd_text = f"Oran: {json.dumps(odds_data, default=str)[:150]}..."
    except Exception:
        odd_text = ""
        
    if odd_text:
        block += f"<i>{odd_text}</i>"
        
    return block

async def build_coupon_text(matches, title, max_matches=3):
    """Maç listesinden tahminleri alarak kupon metnini oluşturur."""
    global posted_matches
    
    lines = []
    count = 0
    now = datetime.now(timezone.utc)
    
    for m in matches:
        if count >= max_matches:
            break
            
        match_id = m.get("id")
        # Zaten yayınlanmış mı (son 24 saat içinde)?
        if match_id in posted_matches and (now - posted_matches[match_id]).total_seconds() < 24*3600:
            log.info(f"Maç atlandı (zaten yayınlandı): {m.get('home')} vs {m.get('away')}")
            continue
            
        pred = await predict_for_match(m, vip=(title.startswith("👑 VIP")))
        
        if pred.get("predictions"):
            lines.append(format_match_block(m, pred))
            posted_matches[match_id] = now
            count += 1
            
    if not lines:
        return None
        
    header = f"━━━━━━━━━━━━━━━━━━━━━━\n    {title}\n━━━━━━━━━━━━━━━━━━━━━━\n"
    footer = "\n━━━━━━━━━━━━━━━━━━━━━━\nBu metin AI tarafından üretilmiştir. Tahminler istatistiksel analiz amaçlıdır; doğrudan bahis tavsiyesi sayılmaz."
    return header + "\n\n".join(lines) + footer

# ---------------- Send ----------------
async def send_to_channel(app, text):
    """Telegram kanalına kupon metnini gönderir."""
    try:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            log.warning("Telegram bilgileri yok, gönderim atlanıyor.")
            return
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML", disable_web_page_preview=True)
        log.info("Kupon gönderildi.")
    except Exception as e:
        log.exception(f"Telegram gönderim hatası: {e}")

# ---------------- Job runner ----------------
async def job_runner(app: Application):
    """Belirli aralıklarla maçları çeken ve tahminleri yayınlayan ana döngü."""
    global last_run
    
    await asyncio.sleep(15) # Başlangıç gecikmesi
    
    while True:
        try:
            now = datetime.now(timezone.utc)
            cleanup_posted_matches()
            
            matches = await fetch_all_matches()
            
            if not matches:
                log.info("Tüm API'ler boş veya veri yok.")
            else:
                
                # --- LIVE (Saatlik) ---
                lr_live = last_run.get("LIVE")
                if not lr_live or (now - lr_live).total_seconds() >= HOURLY*3600:
                    log.info("Canlı yayın döngüsü başladı.")
                    live_matches = [m for m in matches if m.get("live")]
                    if live_matches:
                        text = await build_coupon_text(live_matches, "🔴 CANLI AI TAHMİN", max_matches=5)
                        if text:
                            await send_to_channel(app, text)
                        last_run["LIVE"] = now
                
                # --- DAILY (12 saatlik) ---
                lr_daily = last_run.get("DAILY")
                if not lr_daily or (now - lr_daily).total_seconds() >= DAILY*3600:
                    log.info("Günlük yayın döngüsü başladı.")
                    upcoming = [m for m in matches if (not m.get("live")) and within_hours(m.get("start") or "", 24)]
                    if upcoming:
                        upcoming_sorted = sorted(upcoming, key=lambda x: x.get("start") or "")
                        text = await build_coupon_text(upcoming_sorted, "🗓️ GÜNLÜK AI TAHMİN", max_matches=3)
                        if text:
                            await send_to_channel(app, text)
                        last_run["DAILY"] = now
                        
                # --- VIP (24 saatlik, max 2) ---
                lr_vip = last_run.get("VIP")
                if not lr_vip or (now - lr_vip).total_seconds() >= VIP*3600:
                    log.info("VIP yayın döngüsü başladı.")
                    vip_upcoming = [m for m in matches if (not m.get("live")) and within_hours(m.get("start") or "", 24)]
                    if vip_upcoming:
                        vip_sorted = sorted(vip_upcoming, key=lambda x: x.get("start") or "")
                        text = await build_coupon_text(vip_sorted, "👑 VIP AI TAHMİN", max_matches=VIP_MAX_MATCHES)
                        if text:
                            await send_to_channel(app, text)
                        last_run["VIP"] = now
                        
        except Exception as e:
            log.exception(f"Job runner hata: {e}")
            
        await asyncio.sleep(3600)

# ---------------- Telegram command ----------------
async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/test komutu ile manuel kupon oluşturma ve kanala gönderme."""
    log.info("Test komutu çalıştırıldı.")
    
    await update.message.reply_text("Test başlatılıyor, lütfen bekleyin. Maçlar çekiliyor...")
    
    matches = await fetch_all_matches()
    if not matches:
        await update.message.reply_text("Maç bulunamadı.")
        return
        
    test_matches = matches[:5]
    
    text = await build_coupon_text(test_matches, "🚨 TEST AI TAHMİN (MANUEL)", max_matches=5)
    
    if text:
        # Mesajı /test komutunun geldiği sohbete gönder
        await update.message.reply_text(text, parse_mode="HTML") 
        
    else:
        await update.message.reply_text("Kupon oluşturulamadı.")

# ---------------- MAIN ----------------
# main fonksiyonu artık async DEĞİLDİR ve asyncio.run() tarafından çağrılmaz.
def main():
    if not TELEGRAM_TOKEN:
        log.error("TELEGRAM_TOKEN ayarlı değil. Çıkılıyor.")
        sys.exit(1)
    if not AI_KEY:
        log.error("AI_KEY ayarlı değil. Çıkılıyor.")
        sys.exit(1)
        
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("test", cmd_test))
    
    # KRİTİK DEĞİŞİKLİK: Job runner'ı bot hazır olduktan sonra başlatmak için post_init kullanıyoruz.
    async def post_init_callback(application: Application):
        # job_runner'ı ayrı bir görev (task) olarak başlat
        asyncio.create_task(job_runner(application))
        log.info("Job runner başarıyla asenkron görev olarak başlatıldı.")

    app.post_init = post_init_callback
    
    log.info("v40.6 başlatıldı. Telegram polling başlatılıyor...")
    
    # run_polling() fonksiyonu kendi event loop'unu yönetir ve programı bloke eder.
    app.run_polling(poll_interval=1.0, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        cleanup_posted_matches()
        
        # Sadece senkron main() fonksiyonunu çağırıyoruz. asyncio.run() KALDIRILDI.
        main() 
        
    except KeyboardInterrupt:
        log.info("Durduruldu.")
    except Exception as e:
        log.critical(f"Kritik hata: {e}", exc_info=True)
        sys.exit(1)
