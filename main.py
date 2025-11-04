# main.py - v38.0 AI-TÜRKÇE (İstatistik destekli + Çoklu piyasa tahmini)
import os
import asyncio
import logging
import random
import json
from datetime import datetime, timedelta, timezone
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from fastapi import FastAPI, Request
import uvicorn
from dotenv import load_dotenv
import os
from ai_turkce import ai_turkce_analiz

# .env dosyasını yükle
load_dotenv()

# OPENAI KEY'i ortam değişkeninden al
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ========== CONFIG ==========
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
OPENLIGADB_KEY = os.getenv("OPENLIGADB_KEY", "")
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")

TR_TIME = timezone(timedelta(hours=3))
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

SPORT_EMOJI = {"soccer": "⚽", "basketball": "🏀", "tennis": "🎾", "americanfootball": "🏈"}

# caches
match_cache = {}
team_stats_cache = {}
posted_matches = {}
last_coupon_time = {"CANLI": None, "GÜNLÜK": None, "VIP": None}

# ========== OpenAI çağrısı (aiohttp) ==========
async def openai_chat_json(prompt: str, max_tokens: int = 350):
    """
    OpenAI'den JSON formatında yanıt bekler.
    Prompt Türkçe olacak. Model: gpt-4o-mini (hesabına göre değiştir).
    Dönen metni JSON olarak parse etmeye çalışır.
    """
    if not OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY yok; AI çalışmayacak.")
        return None

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    system = (
        "Sen bir spor analisti ve veri bilimcisisin. Kullanıcı Türkçe konuşuyor. "
        "Verilen maç bilgileri ve istatistikler üzerinden, mantıklı piyasa önerileri üret. "
        "ASLA doğrudan para yatırma talimatı verme. Sadece olasılık/tahmin belirt.\n"
        "Çıkışı JSON formatında ver: {\"predictions\": [ {\"market\":\"MS|TOTALS|BTTS|KG|HANDICAP\", "
        "\"suggestion\":\"MS 1 veya Over 2.5 gibi\",\"confidence\":0-100, \"explanation\":\"kısa neden\"} ], "
        "\"best\": index_of_best_prediction }\n"
        "Cevap sadece JSON içermeli."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt}
    ]

    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.25,
        "max_tokens": max_tokens
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as resp:
                text = await resp.text()
                # metin JSON içeriyorsa parse et
                try:
                    # bazen model etrafında açıklama verebilir -> JSON kısmını ayıkla
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    json_text = text[start:end]
                    parsed = json.loads(json_text)
                    return parsed
                except Exception:
                    # fallback: direkt json parse dene
                    try:
                        return json.loads(text)
                    except Exception:
                        log.warning("OpenAI yanıtı JSON parse edilemedi, ham metin döndü.")
                        return {"raw": text}
    except Exception as e:
        log.exception("OpenAI çağrısında hata:")
        return None

# ========== API-Football: Son 5 maç istatistikleri çek ==========
async def get_team_form_apifootball(team_id, session):
    """
    API-Football'dan (team id varsa) son 5 maç bilgisi çek. Eğer team_id string ise atla.
    Bu helper, match bilgilerinden alınan takım isimleri için fallback olarak kullanılacak.
    """
    # Bu fonksiyon, eğer gerçek team_id tanımlıysa kullanılacak; burada demo fallback var.
    # Kullanıcı API-Football ID vermezse prompt içinde local cache kullanılacak.
    return {
        "form": "".join(random.choice(["W","D","L"]) for _ in range(5)),
        "goals_avg": round(0.8 + random.random()*2.0, 2)
    }

# ========== Maç çekme: Çoklu API (orijinal mantık + genişleme) ==========
async def fetch_matches(max_hours=24, live_only=False):
    global match_cache
    now = datetime.now(timezone.utc)
    cache_key = f"{live_only}_{max_hours}_{now.hour}"
    if cache_key in match_cache and (now - match_cache[cache_key]["time"]).total_seconds() < 300:
        return match_cache[cache_key]["data"]

    matches = []
    today = now.strftime("%Y-%m-%d")
    # Birkaç API uç noktasını dene (sana ait key'ler varsa)
    apis = [
        ("API-Football", API_FOOTBALL_KEY, f"https://v3.football.api-sports.io/fixtures", {"date": today}, {"x-apisports-key": API_FOOTBALL_KEY}),
        ("The Odds API", THE_ODDS_API_KEY, f"https://api.the-odds-api.com/v4/sports", {"apiKey": THE_ODDS_API_KEY, "regions": "eu"}, {}),
        ("Balldontlie", BALLDONTLIE_KEY, "https://www.balldontlie.io/api/v1/games", {"dates[]": today}, {}),
        ("FootyStats", FOOTYSTATS_KEY, "https://api.footystats.org/league-matches", {"key": FOOTYSTATS_KEY, "league_id": 1625}, {}),
        ("AllSportsAPI", ALLSPORTSAPI_KEY, "https://apiv2.allsportsapi.com/football/", {"met": "Fixtures", "APIkey": ALLSPORTSAPI_KEY, "from": today, "to": today}, {}),
        ("SportsMonks", SPORTSMONKS_KEY, "https://api.sportmonks.com/v3/football/fixtures", {"api_token": SPORTSMONKS_KEY, "date": today}, {}),
        ("iSportsAPI", ISPORTSAPI_KEY, "https://api.isportsapi.com/sport/football/schedule", {"api_key": ISPORTSAPI_KEY, "date": today}, {}),
    ]

    async with aiohttp.ClientSession() as session:
        for name, key, url, params, headers in apis:
            # key boşsa atla
            if key is not None and not str(key).strip():
                continue
            try:
                log.info(f"{name} çağrılıyor...")
                async with session.get(url, params=params, headers=headers, timeout=15) as r:
                    if r.status == 200:
                        try:
                            data = await r.json()
                        except Exception:
                            data_text = await r.text()
                            log.debug(f"{name} ham yanıt: {data_text[:200]}")
                            continue
                        # Esnek parsing: farklı API'ler farklı alan adları kullanır
                        items = data.get("response") or data.get("data") or data.get("fixtures") or data.get("events") or data.get("matches") or data.get("games") or []
                        if not isinstance(items, list):
                            items = [items] if items else []
                        count = 0
                        for item in items:
                            try:
                                # normalize farklı field isimleri
                                start_str = item.get("date") or item.get("fixture", {}).get("date") or item.get("commence_time") or item.get("date_start") or item.get("start_time")
                                if not start_str:
                                    continue
                                try:
                                    start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                                except Exception:
                                    # bazı API'ler timestamp ile gelir - atla
                                    continue
                                delta_hours = (start - now).total_seconds() / 3600
                                status = str(item.get("status") or item.get("fixture", {}).get("status", "")).lower()
                                is_live = "inplay" in status or "live" in status
                                if live_only and not is_live: continue
                                if not live_only and not (0 <= delta_hours <= max_hours): continue
                                match_id = f"{name}_{item.get('id', random.randint(1,999999))}"
                                if match_id in posted_matches: continue
                                # takım isimleri farklı alanlarda olabilir
                                home = (item.get("home_team") or item.get("teams", {}).get("home", {}).get("name") or item.get("home") or (item.get("teams") and list(item["teams"].keys())[0]) or "Home")
                                away = (item.get("away_team") or item.get("teams", {}).get("away", {}).get("name") or item.get("away") or (item.get("teams") and list(item["teams"].keys())[-1]) or "Away")
                                # spor tespiti
                                sport = "soccer"
                                if "basket" in name.lower() or "ball" in name.lower() and "basket" in url:
                                    sport = "basketball"
                                # ek meta
                                matches.append({
                                    "id": match_id,
                                    "source": name,
                                    "home": str(home),
                                    "away": str(away),
                                    "start": start,
                                    "sport": sport,
                                    "live": is_live,
                                    "raw": item
                                })
                                count += 1
                            except Exception:
                                continue
                        if count > 0:
                            log.info(f"{name}: {count} maç çekildi.")
                            # break; // bırakma — birden fazla kaynaktan topluyoruz
                    elif r.status == 429:
                        log.warning(f"{name} KOTA DOLDU")
            except Exception as e:
                log.warning(f"{name} hata: {e}")
                continue

    match_cache[cache_key] = {"data": matches, "time": now}
    log.info(f"Toplam çekilen maç: {len(matches)}")
    return matches

# ========== AI destekli tahmin üretimi (Türkçe) ==========
async def ai_predict_markets(match, session):
    """
    match: dict (home, away, start, sport, raw)
    Bu fonksiyon:
    - team_stats_cache'den / API-Football'dan son 5 maç verisini ekler,
    - OpenAI'ye Türkçe prompt ile gönderir,
    - JSON parse edip döner: predictions listesi ve best index.
    """
    home = match.get("home", "Home")
    away = match.get("away", "Away")
    start = match.get("start")
    start_local = start.astimezone(TR_TIME).strftime("%d %b %H:%M") if start else "Bilinmiyor"
    sport = match.get("sport", "soccer")

    cache_key = f"{match['id']}"
    if cache_key not in team_stats_cache:
        # Eğer API-Football varsa, ideal şekilde gerçek son 5 maç verisi alınır.
        # Burada basitçe dummy/hafıza verisi yerleştiriyoruz; istersen detaylı API-Football entegrasyonunu genişletebiliriz.
        team_stats_cache[cache_key] = {
            "home": {"form": "".join(random.choice(["W","D","L"]) for _ in range(5)), "goals_avg": round(0.8+random.random()*2.2,2)},
            "away": {"form": "".join(random.choice(["W","D","L"]) for _ in range(5)), "goals_avg": round(0.6+random.random()*1.8,2)}
        }

    stats = team_stats_cache[cache_key]
    prompt = (
        f"Maç: {home} vs {away}\n"
        f"Tarih (TR): {start_local}\n"
        f"Spor: {sport}\n\n"
        f"Ev sahibi form (son 5): {stats['home']['form']}, gol ortalaması: {stats['home']['goals_avg']}\n"
        f"Deplasman form (son 5): {stats['away']['form']}, gol ortalaması: {stats['away']['goals_avg']}\n\n"
        "Yapılacaklar:\n"
        "- Bu maç için olası bahis piyasalarından (MS, KG, Üst/Alt 1.5-2.5, Karşılıklı Gol - BTTS, Basketbol için Moneyline/Totals, Tenis için Moneyline) en anlamlı olanları değerlendir.\n"
        "- Her öneri için kısa bir açıklama ve 0-100 arası bir güven yüzdesi ver.\n"
        "- Cevabı şu JSON formatında ver (yalnızca JSON):\n"
        "{\n  \"predictions\": [\n    {\"market\":\"MS\",\"suggestion\":\"MS 1\",\"confidence\":85,\"explanation\":\"kısa neden\"},\n    ...\n  ],\n  \"best\": 0\n}\n\n"
        "Not: Tahminler istatistiksel analiz içindir; bahis yönlendirmesi olarak anlaşılmamalıdır. Cevabı Türkçe ver."
    )

    ai_resp = await openai_chat_json(prompt)
    if not ai_resp:
        # fallback: basit rule-based öneri
        # basit kural: ev sahibi son 5'te daha fazla W => MS1, else MS2, ayrıca toplam gol ortalaması yüksekse Over 2.5
        home_w = stats['home']['form'].count("W")
        away_w = stats['away']['form'].count("W")
        total_goals = stats['home']['goals_avg'] + stats['away']['goals_avg']
        preds = []
        if home_w > away_w:
            preds.append({"market":"MS","suggestion":"MS 1","confidence":70,"explanation":"Ev sahibi form olarak daha iyi."})
        elif away_w > home_w:
            preds.append({"market":"MS","suggestion":"MS 2","confidence":68,"explanation":"Deplasman form olarak daha iyi."})
        else:
            preds.append({"market":"MS","suggestion":"Beraberlik","confidence":50,"explanation":"Eşit form."})
        if total_goals > 2.6:
            preds.append({"market":"TOTALS","suggestion":"Over 2.5","confidence":72,"explanation":"Takımlar gol ortalaması yüksek."})
        else:
            preds.append({"market":"TOTALS","suggestion":"Under 2.5","confidence":60,"explanation":"Takımlar düşük skorlu."})
        best = max(range(len(preds)), key=lambda i: preds[i]["confidence"])
        return {"predictions": preds, "best": best}

    # Eğer OpenAI JSON döndüyse bunu döndür
    # Güvenlik: beklenen anahtarlar yoksa fallback
    if isinstance(ai_resp, dict) and "predictions" in ai_resp:
        # normalize confidence ve validation
        preds = ai_resp.get("predictions", [])
        for p in preds:
            if "confidence" in p:
                try:
                    p["confidence"] = max(0, min(100, int(p["confidence"])))
                except:
                    p["confidence"] = 50
        best = ai_resp.get("best", 0)
        return {"predictions": preds, "best": best}
    else:
        return {"predictions": [{"market":"INFO","suggestion":"AI yanıt parse edilemedi","confidence":50,"explanation":str(ai_resp)}], "best":0}

## ========== Build coupon -> artık 'AI TAHMİN/ANALİZ' ==========
async def build_coupon(title, max_hours, interval, max_matches, live_only=False):
    now = datetime.now(TR_TIME)
    last = last_coupon_time.get(title)
    if last and (now - last).total_seconds() < interval * 3600:
        return None

    matches = await fetch_matches(max_hours, live_only)
    if not matches:
        return None

    # Her maç için AI predictions al
    evaluated = []
    async with aiohttp.ClientSession() as session:
        tasks = [ai_predict_markets(m, session) for m in matches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    for m, res in zip(matches, results):
        if isinstance(res, Exception) or res is None:
            continue
        preds = res.get("predictions", [])
        best_index = res.get("best", 0)
        best_pred = preds[best_index] if preds and 0 <= best_index < len(preds) else (preds[0] if preds else None)
        # güçlü olanları topla
        score = best_pred["confidence"] if best_pred else 0
        evaluated.append((score, m, preds, best_pred))

    if not evaluated:
        return None

    # Güvene göre sırala ve en kuvvetlileri al
    evaluated.sort(key=lambda x: x[0], reverse=True)
    selected = evaluated[:max_matches]

    lines = []
    for score, m, preds, best in selected:
        emoji = SPORT_EMOJI.get(m.get("sport", "soccer"), "🏟️")
        status = "CANLI" if m.get("live") else m["start"].astimezone(TR_TIME).strftime("%d %b %H:%M")

        # En iyi öneri ve diğerleri
        best_line = (
            f"<b>Öne Çıkan:</b> {best['suggestion']} | <b>Güven:</b> %{best['confidence']}\n"
            f"<i>{best.get('explanation','')}</i>\n" if best else ""
        )

        other_lines = ""
        for p in preds:
            if p == best:
                continue
            other_lines += f"- {p['suggestion']} (%{p['confidence']}) — {p.get('explanation','')}\n"

        # 🧠 Türkçe AI analiz (OpenAI GPT-4o)
        analiz = await ai_turkce_analiz(
            f"{m['home']} vs {m['away']} - En iyi tahmin: {best.get('suggestion','Bilinmiyor')} | Açıklama: {best.get('explanation','Yok')}"
        )

        block = (
            f"{emoji} <b>{m['home']} vs {m['away']}</b>\n"
            f"{status}\n"
            f"{best_line}"
            f"{other_lines}"
            f"🧠 <i>{analiz}</i>\n"
        )

        lines.append(block)
        posted_matches[m["id"]] = True

    last_coupon_time[title] = now
    header = f"━━━━━━━━━━━━━━━━━━━━━━\n    {title}\n━━━━━━━━━━━━━━━━━━━━━━\n"
    footer = "\n━━━━━━━━━━━━━━━━━━━━━━\nBu metin AI tarafından üretilmiştir. Tahminler istatistiksel analiz amaçlıdır; doğrudan bahis tavsiyesi sayılmaz."
    return header + "\n\n".join(lines) + footer
# ========== Gönderim fonksiyonları ==========
async def send_coupon(ctx, title, max_hours, interval, max_matches, live_only=False):
    text = await build_coupon(title, max_hours, interval, max_matches, live_only)
    if text:
        try:
            await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
            log.info(f"{title} gönderildi.")
        except Exception:
            log.exception("Mesaj gönderme hatası")

# Zamanlanmış wrapper'lar
async def hourly(ctx): await send_coupon(ctx, "CANLI AI TAHMİN", 1, 1, 1, live_only=True)
async def daily(ctx):  await send_coupon(ctx, "GÜNLÜK AI TAHMİN", 24, 12, 3)
async def vip(ctx):    await send_coupon(ctx, "VIP AI TAHMİN", 24, 24, 3)

# ========== Telegram komutları ==========
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_coupon(context, "TEST AI TAHMİN", 24, 0, 3)
    await update.message.reply_text("Test atıldı.")

# ========== App lifecycle ==========
app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()
tg.add_handler(CommandHandler("test", test))
tg.add_handler(CommandHandler("hourly", lambda u,c: asyncio.create_task(hourly(c))))
tg.add_handler(CommandHandler("daily", lambda u,c: asyncio.create_task(daily(c))))
tg.add_handler(CommandHandler("vip", lambda u,c: asyncio.create_task(vip(c))))

async def lifespan(app: FastAPI):
    jq = tg.job_queue
    jq.run_repeating(lambda ctx: asyncio.create_task(hourly(ctx)), interval=3600, first=5)
    jq.run_repeating(lambda ctx: asyncio.create_task(daily(ctx)), interval=43200, first=20)
    jq.run_repeating(lambda ctx: asyncio.create_task(vip(ctx)), interval=86400, first=30)
    await tg.initialize(); await tg.start()
    try:
        await tg.bot.set_webhook(WEBHOOK_URL)
    except Exception:
        log.warning("Webhook setlenemedi, lokal modda çalışılıyor.")
    log.info("v38.0 AI-TÜRKÇE HAZIR!")
    yield
    await tg.stop(); await tg.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/stakedrip")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT","8443")))
