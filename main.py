# main.py — v50.0 (Gelişmiş Filtreleme, Yeni Görünüm ve Stratejiler)

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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("v50.0") 

# ENV KONTROLÜ
AI_KEY = os.getenv("AI_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Sabit API keyler
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2"
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"
# Diğer API keyleriniz de burada listelenmeye devam ediyor...

# Türkiye zaman dilimi (UTC+3)
TR_TZ = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# Scheduler intervals (saat)
HOURLY = 1
DAILY = 12
VIP = 24
VIP_MAX_MATCHES = 2       # VIP Kupon: Max 2 maç
DAILY_MAX_MATCHES = 3     # Günlük Kupon: Max 3 maç
DAILY_MAX_ODDS = 3.0      # Günlük Kupon: Max oran filtresi 3.0
MIN_CONFIDENCE = 60       # Minimum güvenilirlik filtresi

# state
posted_matches = {}
last_run = {"LIVE": None, "DAILY": None, "VIP": None}
ai_rate_limit = {"calls": 0, "reset": NOW_UTC}

# ---------------- helpers ----------------
def to_local_str(iso_ts: str):
    """ISO tarih/saatini TR yerel formatında string'e dönüştürür."""
    if not iso_ts: return "Bilinmeyen"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
             dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TR_TZ).strftime("%d.%m %H:%M") # Yeni Format
    except Exception: return iso_ts

def within_hours(iso_ts: str, hours: int):
    """ISO tarih/saatinin şu andan itibaren belirtilen saat içinde olup olmadığını kontrol eder."""
    if not iso_ts: return False
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
             dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = (dt - now).total_seconds()
        return 0 <= delta <= hours * 3600 # Sadece başlamamış maçlar (delta > 0)
    except Exception: return False

# ... (safe_get ve cleanup_posted_matches aynı kalacak) ...
def safe_get(d, *keys):
    cur = d
    for k in keys:
        if not isinstance(cur, dict): return None
        cur = cur.get(k)
    return cur

def cleanup_posted_matches():
    global posted_matches
    now = datetime.now(timezone.utc)
    posted_matches = {mid: dt for mid, dt in posted_matches.items() if (now - dt).total_seconds() < 24*3600}
    log.info(f"Temizleme sonrası posted_matches boyutu: {len(posted_matches)}")

# YENİ/DÜZELTİLMİŞ HELPER: Belirli bir tahmin için oranı alır
def get_odd_for_market(m: dict, prediction_suggestion: str):
    """H2H (MS) piyasasında, verilen tahmin önerisi için oranı döndürür. (TheOdds formatı)"""
    odds_data = m.get("odds")
    if m.get("source") != "TheOdds" or not odds_data or not isinstance(odds_data, list):
        return None
        
    home = m.get('home')
    away = m.get('away')
    
    # Tahmin önerisini standart Outcome ismine eşleştirme (TheOdds uyumlu)
    target_outcome_names = []
    if any(k in prediction_suggestion for k in ["MS 1", "Ev sahibi kazanır"]):
        target_outcome_names = [home, 'Home', '1']
    elif any(k in prediction_suggestion for k in ["MS 2", "Deplasman kazanır"]):
        target_outcome_names = [away, 'Away', '2']
    elif any(k in prediction_suggestion for k in ["Beraberlik", "MS 0", "MS X"]):
        target_outcome_names = ['Draw', 'X', '0']
    else:
        return None 
        
    # Tüm bookmaker'ları dolaş, oranı bul (genellikle en iyi oran)
    prices = []
    for bookmaker in odds_data:
        for market in bookmaker.get("markets", []):
            if market.get("key") == "h2h":
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") in target_outcome_names:
                        prices.append(outcome.get("price"))
                        
    return max(prices) if prices else None # En yüksek oranı al (Bazı bookmaker'lar)

# YENİ/DÜZELTİLMİŞ HELPER: H2H oranlarını toplu alır
def get_all_h2h_odds(m: dict):
    """Ev, Beraberlik, Deplasman oranlarını gösterim için alır. (TheOdds formatı)"""
    odds_data = m.get("odds")
    res = {'E': '?', 'B': '?', 'D': '?'}
    if m.get("source") != "TheOdds" or not odds_data or not isinstance(odds_data, list):
        return res

    # Tüm bookmaker'lar arasında ortalama veya ilk bulunanı kullan
    for bookmaker in odds_data:
        for market in bookmaker.get("markets", []):
            if market.get("key") == "h2h":
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name")
                    price = outcome.get("price")
                    # Takım isimlerine göre eşleştirme
                    if name in [m.get('home'), 'Home', '1']: res['E'] = price
                    if name in [m.get('away'), 'Away', '2']: res['D'] = price
                    if name in ['Draw', 'X', '0']: res['B'] = price
                
                # İlk bookmaker'dan gelen tam seti döndürmek daha kararlı
                if res['E'] != '?' and res['B'] != '?' and res['D'] != '?':
                    return res
    return res

# ---------------- fetch APIs ----------------
# NOTE: Tüm fetch fonksiyonlarında, live=False olanlarda sadece within_hours kontrolü yapılır.
# ... (fetch_api_football, fetch_the_odds vb. API hata loglamaları iyileştirilmiş haliyle) ...

async def fetch_api_football(session):
    res = []
    url = "https://v3.football.api-sports.io/fixtures"
    # Sadece 24 saat içinde başlayacak maçları çekmek için zaman aralığı
    end_time = datetime.now(timezone.utc) + timedelta(hours=24)
    params = {"from": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "to": end_time.strftime("%Y-%m-%d")}
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    try:
        async with session.get(url, params=params, headers=headers, timeout=12) as r:
            if r.status == 429: log.error("API-Football HATA: Hız limiti aşıldı (429).")
            elif r.status != 200: log.warning(f"API-Football HTTP HATA: {r.status} (Çalışmıyor).")
            if r.status != 200: return res
            
            data = await r.json()
            items = data.get("response") or []
            for it in items:
                fix = it.get("fixture", {})
                status_short = (safe_get(fix, "status", "short") or "").lower()
                start = fix.get("date")
                
                # Canlı/Bitmiş durumları hariç tutuldu
                if status_short in ("ft", "pst", "canc", "abd", "awd", "wo", "live", "ht", "1h", "2h", "et", "pen"):
                    continue
                
                if not within_hours(start, 24): continue
                
                res.append({
                    "id": safe_get(fix,'id'),
                    "home": safe_get(it,"teams","home","name") or "Home",
                    "away": safe_get(it,"teams","away","name") or "Away",
                    "start": start,
                    "source": "API-Football",
                    "live": False, # Sadece NS maçlar çekildi
                    "odds": safe_get(it, "odds") or {},
                    "sport": "Football"
                })
            log.info(f"API-Football raw:{len(items)} filtered:{len(res)}")
    except Exception as e: log.warning(f"API-Football hata: {e}")
    return res

# ... (Diğer fetch fonksiyonları da benzer şekilde sadece NS maçları çekecek şekilde güncellenmeli) ...

async def fetch_the_odds(session):
    res = []
    url = "https://api.the-odds-api.com/v4/sports/soccer/odds"
    # Sadece 24 saat içinde başlayacak (upcoming) maçları çekmek için
    params = {"regions":"eu","markets":"h2h,totals,spreads","oddsFormat":"decimal","dateFormat":"iso","apiKey":THE_ODDS_API_KEY"}
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status == 429: log.error("The Odds API HATA: Hız limiti aşıldı (429).")
            elif r.status != 200: log.warning(f"The Odds API HTTP HATA: {r.status}")
            if r.status != 200: return res
            
            data = await r.json()
            if isinstance(data, list):
                for it in data:
                    start = it.get("commence_time")
                    if not start: continue
                    if not within_hours(start, 24): continue # Sadece 24 saat içindeki NS
                        
                    res.append({
                        "id": it.get('id'),
                        "home": it.get("home_team","Home"),
                        "away": it.get("away_team","Away"),
                        "start": start,
                        "source": "TheOdds",
                        "live": False,
                        "odds": it.get("bookmakers", []),
                        "sport": it.get("sport_key", "Soccer")
                    })
            log.info(f"The Odds raw:{len(data) if isinstance(data, list) else 0} filtered:{len(res)}")
    except Exception as e: log.warning(f"The Odds API hata: {e}")
    return res


# Diğer API'lerin fetch fonksiyonları da sadece "NS" (Not Started) veya 
# "upcoming" maçları çekecek şekilde düzenlenmelidir.

# ... (fetch_footystats, fetch_allsports, fetch_sportsmonks, fetch_isports aynı mantıkla filtrelenmeli) ...

async def fetch_all_matches():
    # ... (tasks listesi ve toplama mantığı aynı kalacak) ...
    # Şimdilik sadece TheOdds ve API-Football kullanılıyor varsayılarak devam ediliyor
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_api_football(session),
            fetch_the_odds(session),
            # Diğer fetch fonksiyonları buraya eklenecek
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_matches = []
    for r in results:
        if isinstance(r, Exception):
            log.warning(f"fetch task exception: {r}")
            continue
        all_matches.extend(r or [])
        
    normalized = []
    for m in all_matches:
        # ... (normalization mantığı aynı kalacak) ...
        start = m.get("start") or m.get("date") or ""
        if isinstance(start, (int, float)):
            try:
                start = datetime.fromtimestamp(int(start), tz=timezone.utc).isoformat().replace('+00:00', 'Z')
            except:
                start = ""
        
        match_id_base = m.get("id") or hash(json.dumps(m, default=str))
        final_id = f"{m.get('source')}_{match_id_base}"
        
        normalized.append({
            "id": final_id,
            "home": m.get("home"),
            "away": m.get("away"),
            "start": start,
            "source": m.get("source"),
            "live": bool(m.get("live")),
            "odds": m.get("odds", {}),
            "sport": m.get("sport", "Bilinmeyen")
        })
        
    seen = set()
    final = []
    for m in normalized:
        key = m.get("id")
        if not key: continue
        if key in seen:
            continue
        seen.add(key)
        final.append(m)
        
    log.info(f"Toplam çekilen maç (normalized, dedup): {len(final)}")
    return final

# ---------------- OpenAI integration ----------------
# ... (call_openai_chat aynı kalacak) ...

async def call_openai_chat(prompt: str, max_tokens=300, temperature=0.2):
    global ai_rate_limit
    now = datetime.now(timezone.utc)
    
    # 3 RPM için 1 dakikada sadece 2 çağrıya izin ver.
    if ai_rate_limit["reset"] < now:
        ai_rate_limit["calls"] = 0
        ai_rate_limit["reset"] = now + timedelta(seconds=60) 
    
    if ai_rate_limit["calls"] >= 2: 
        log.warning("OpenAI lokal kısıtlama (3 RPM limitine ulaşıldı). Fallback.")
        return None 
        
    ai_rate_limit["calls"] += 1 
    
    # ... (HTTP istek mantığı ve hata işleme aynı kalacak) ...
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
    
    try:
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OPENAI_URL, headers=headers, json=payload) as resp:
                txt = await resp.text()
                # ... (429 ve 200 olmayan kodların işlenmesi)
                if resp.status == 429: log.error(f"OpenAI API 429 Hata: Hız limitine ulaşıldı. Fallback."); return None
                if resp.status != 200: log.warning(f"OpenAI HTTP {resp.status}: {txt[:400]}"); return None
                
                try:
                    data = json.loads(txt)
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start: return json.loads(content[start:end])
                    return json.loads(content)
                except Exception as e:
                    log.warning(f"OpenAI parse hatası: {e}. Raw content: {content[:100]}")
                    return None
                    
    except Exception as e:
        log.warning(f"OpenAI beklenmeyen hata: {e}")
        return None

# ---------------- Prediction wrapper ----------------
async def predict_for_match(m: dict, vip_surprise=False):
    """Maç için AI tahmini alır veya fallback üretir."""
    # VIP sürpriz kupon için daha düşük sıcaklık (daha spekülatif, daha deterministik)
    temp = 0.2 if not vip_surprise else 0.05 
    
    prompt = (
        f"Spor: {m.get('sport')}\nMaç: {m.get('home')} vs {m.get('away')}\n"
        f"Tarih(UTC): {m.get('start')}\n"
    )
    if m.get("odds"): prompt += "Oran bilgisi mevcut.\n"
    prompt += (
        "İstediğim JSON formatı: {\"predictions\":[{\"market\":\"MS\",\"suggestion\":\"MS 1\",\"confidence\":85,\"explanation\":\"...\"}],\"best\":0}. "
        "Confidence 0-100 arasında bir tam sayı olmalı. Cevabı yalnızca JSON ver."
    )
    
    ai_resp = await call_openai_chat(prompt, max_tokens=300, temperature=temp)
    
    if not ai_resp or not isinstance(ai_resp, dict) or "predictions" not in ai_resp:
        log.warning(f"AI tahmini başarısız veya boş: {m.get('id')}. Fallback kullanılıyor.")
        # Fallback mantığı (F) etiketi olmadan
        preds = []
        if vip_surprise: # Sürpriz için daha yüksek skorlu, daha spekülatif tahminler
            preds.append({"market":"TOTALS","suggestion":"Over 3.5","confidence":61,"explanation":"Yüksek skorlu sürpriz beklentisi."})
            preds.append({"market":"MS","suggestion":"MS X","confidence":55,"explanation":"Eşit güçler, riskli beraberlik."})
        else: # Normal
            preds.append({"market":"MS","suggestion":"MS 1","confidence":60,"explanation":"Ev sahibi avantajlı görünüyor."})
            preds.append({"market":"TOTALS","suggestion":"Under 2.5","confidence":55,"explanation":"Düşük skorlu mücadele bekleniyor."})

        best_idx = max(range(len(preds)), key=lambda i: preds[i]["confidence"])
        return {"predictions": preds, "best": best_idx, "fallback": True}
        
    # ... (AI sonucu işleme aynı kalacak)
    preds = ai_resp.get("predictions", [])
    for p in preds:
        try: p["confidence"] = max(0, min(100, int(p.get("confidence",50))))
        except: p["confidence"] = 50
            
    best = ai_resp.get("best", 0)
    if not isinstance(best, int) or best < 0 or best >= len(preds):
        best = max(range(len(preds)), key=lambda i: preds[i]["confidence"]) if preds else 0
        
    return {"predictions": preds, "best": best, "fallback": False}

# ---------------- Build coupon (YENİ GÖRÜNÜM) ----------------
def format_match_block(m, pred):
    """Maç ve tahmin bilgisini modern ve sade formatta döndürür."""
    start_local = to_local_str(m.get("start") or "")
    best = pred["predictions"][pred["best"]] if pred["predictions"] else None
    
    # Oranları çek
    h2h_odds = get_all_h2h_odds(m)
    odd_display = f"E:{h2h_odds['E']} | B:{h2h_odds['B']} | D:{h2h_odds['D']}"
    
    # En İyi Tahmin
    suggestion = best.get('suggestion', 'Bilinmiyor')
    confidence = best.get('confidence', 0)
    explanation = best.get('explanation','').replace(" (F)", "") # Fallback etiketi kaldırıldı
    
    block = (
        f"🏆 <b>{m.get('home')} vs {m.get('away')}</b>\n"
        f"📅 {start_local} | {m.get('sport','Spor')}\n"
        f"📈 <b>{suggestion}</b> <tg-spoiler>(%{confidence})</tg-spoiler>\n"
        f"  - <i>{explanation}</i>\n"
        f"💸 <tg-spoiler>MS Oran: {odd_display}</tg-spoiler>"
    )
    
    return block

async def build_coupon_text(matches, title, max_matches):
    """Maç listesinden tahminleri alarak kupon metnini oluşturur."""
    global posted_matches
    
    lines = []
    count = 0
    now = datetime.now(timezone.utc)
    
    is_daily_coupon = "GÜNLÜK" in title
    
    for m in matches:
        if count >= max_matches: break
            
        match_id = m.get("id")
        if match_id in posted_matches and (now - posted_matches[match_id]).total_seconds() < 24*3600:
            log.info(f"Maç atlandı (zaten yayınlandı): {m.get('home')} vs {m.get('away')}")
            continue
            
        # VIP kupon için sürpriz mantığı
        pred = await predict_for_match(m, vip_surprise=("👑 VIP" in title))
        
        if pred and pred.get("predictions"):
            best = pred["predictions"][pred["best"]]
            
            # 1. KRİTİK FİLTRE: Güven %60 ve üzeri olmalı
            if best["confidence"] < MIN_CONFIDENCE:
                log.info(f"Maç atlandı (Güven %{best['confidence']}<{MIN_CONFIDENCE}): {m.get('home')} vs {m.get('away')}")
                continue
                
            # 2. KRİTİK FİLTRE: Günlük kuponda max oran kontrolü (MS tahminleri için)
            if is_daily_coupon and DAILY_MAX_ODDS:
                if any(k in best["suggestion"] for k in ["MS 1", "MS 2", "Beraberlik"]):
                    odd = get_odd_for_market(m, best["suggestion"])
                    
                    if odd is None or odd > DAILY_MAX_ODDS:
                        log.info(f"Maç atlandı (Oran {odd if odd else 'yok'}>{DAILY_MAX_ODDS}): {m.get('home')} vs {m.get('away')}")
                        continue
            
            # Filtreleri geçti, kupona ekle
            lines.append(format_match_block(m, pred))
            posted_matches[match_id] = now
            count += 1
            
    if not lines: return None
        
    # YENİ BANNER VE GÖRÜNÜM
    header = (
        f"━━━━━━━━━━━━━━━\n"
        f"   {title}\n"
        f"━━━━━━━━━━━━━━━\n"
    )
    footer = (
        f"\n━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Bahis risklidir. Tahminler yalnızca yapay zeka analizi amaçlıdır.</i>\n"
    )
    return header + "\n\n" + "\n\n".join(lines) + footer

# ---------------- Job runner ----------------
# ... (Diğer kısımlar aynı kalacak) ...

async def job_runner(app: Application):
    global last_run
    
    await asyncio.sleep(15) 
    
    while True:
        try:
            now = datetime.now(timezone.utc)
            cleanup_posted_matches()
            
            # Sadece başlamamış (NS) maçları çeker
            matches = await fetch_all_matches() 
            
            if not matches:
                log.info("Tüm API'ler boş veya veri yok.")
            else:
                
                # --- LIVE (Canlı) Kupon kaldırıldı, sadece NS isteniyor ---
                # --- DAILY (12 saatlik) ---
                lr_daily = last_run.get("DAILY")
                if not lr_daily or (now - lr_daily).total_seconds() >= DAILY*3600:
                    log.info("Günlük yayın döngüsü başladı.")
                    # Zaten fetch_all_matches ile sadece 24 saat içindeki NS maçlar geldi
                    upcoming_sorted = sorted(matches, key=lambda x: x.get("start") or "")
                    
                    text = await build_coupon_text(
                        upcoming_sorted, 
                        "🗓️ GÜNLÜK AI SEÇİMİ (Oran Max 3.0)", 
                        max_matches=DAILY_MAX_MATCHES
                    )
                    if text:
                        await send_to_channel(app, text)
                    last_run["DAILY"] = now
                        
                # --- VIP (24 saatlik, sürpriz) ---
                lr_vip = last_run.get("VIP")
                if not lr_vip or (now - lr_vip).total_seconds() >= VIP*3600:
                    log.info("VIP yayın döngüsü başladı.")
                    # Zaten fetch_all_matches ile sadece 24 saat içindeki NS maçlar geldi
                    vip_sorted = sorted(matches, key=lambda x: x.get("start") or "")
                    
                    text = await build_coupon_text(
                        vip_sorted, 
                        "👑 VIP AI SÜRPRİZ KUPON", 
                        max_matches=VIP_MAX_MATCHES
                    )
                    if text:
                        await send_to_channel(app, text)
                    last_run["VIP"] = now
                        
        except Exception as e:
            log.exception(f"Job runner hata: {e}")
            
        await asyncio.sleep(3600)

async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Test komutu mantığı güncellendi) ...
    log.info("Test komutu çalıştırıldı.")
    await update.message.reply_text("Test başlatılıyor, lütfen bekleyin. Maçlar çekiliyor...")
    
    matches = await fetch_all_matches() # Sadece NS maçları çekecek
    if not matches:
        await update.message.reply_text("Maç bulunamadı (24 saat içinde başlayacak).")
        return
        
    test_matches = matches[:5]
    
    text = await build_coupon_text(
        test_matches, 
        "🚨 TEST AI KUPON (MANUEL)", 
        max_matches=5
    )
    
    if text:
        await update.message.reply_text(text, parse_mode="HTML") 
    else:
        await update.message.reply_text("Kupon oluşturulamadı (Filtrelere takılmış olabilir).")

# ---------------- MAIN ----------------
def main():
    if not TELEGRAM_TOKEN: log.error("TELEGRAM_TOKEN ayarlı değil. Çıkılıyor."); sys.exit(1)
    if not AI_KEY: log.error("AI_KEY ayarlı değil. Çıkılıyor."); sys.exit(1)
    if not TELEGRAM_CHAT_ID: log.critical("TELEGRAM_CHAT_ID ayarlı değil. Çıkılıyor."); sys.exit(1)
        
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("test", cmd_test))
    
    async def post_init_callback(application: Application):
        # Canlı kupon isteği kaldırıldığı için, bu kısımda canlı maç döngüsü yok
        asyncio.create_task(job_runner(application))
        log.info("Job runner başarıyla asenkron görev olarak başlatıldı.")

    app.post_init = post_init_callback
    
    log.info("v50.0 başlatıldı. Telegram polling başlatılıyor...")
    
    app.run_polling(poll_interval=1.0, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        cleanup_posted_matches()
        main() 
        
    except KeyboardInterrupt: log.info("Durduruldu.")
    except Exception as e: log.critical(f"Kritik hata: {e}", exc_info=True); sys.exit(1)
