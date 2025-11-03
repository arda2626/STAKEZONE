# main.py — STAKEDRIP AI ULTRA (tek dosya çalıştırılabilir orchestrator)
import asyncio, logging, aiohttp
from datetime import time as dt_time, timezone
from telegram.ext import Application
from telegram import Bot
from db import init_db, DB_PATH, mark_posted, was_posted_recently
from fetch_matches import fetch_all_matches    # senin mevcut fetch_matches modülün ile uyumlu
from prediction import ai_predict               # senin prediction modülüne uyumlu
from messages import create_live_banner, create_daily_banner, create_vip_banner
from results import check_results
from utils import turkey_now

# ------------- CONFIG (telefon kullanımına göre kolay düzenleme) -------------
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"   # burayı kendi token ile değiştir
CHANNEL_ID = "@stakedrip"                                          # kanal ya da chat id
API_FOOTBALL_KEY = "3838237ec41218c2572ce541708edcfd"    # eğer API-Football kullanacaksan buraya key yazabilirsin (opsiyonel)
DB_FILE = DB_PATH
MAX_LIVE_PICKS = 3
MIN_CONFIDENCE = 0.60
MIN_ODDS = 1.20

# ------------- LOGGING -------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("stakedrip")

# ------------- STARTUP -------------
async def hourly_live_job(ctx):
    """
    Bu job Application.job_queue tarafından çağrılır. ctx: JobContext
    fetch_all_matches fonksiyonun mevcut modülünle uyumlu olacak şekilde yazdım:
      - async def fetch_all_matches(api_key=None) veya async def fetch_all_matches()
    """
    bot = ctx.bot
    try:
        # çağır: varsa API key gönder
        matches = []
        try:
            # çağırırken fonksiyon arg_count kontrol etmek istemezsen basit await kullan
            matches = await fetch_all_matches(API_FOOTBALL_KEY) if API_FOOTBALL_KEY else await fetch_all_matches()
        except TypeError:
            # eğer fetch_all_matches signature farklıysa: parametresiz çağır
            matches = await fetch_all_matches()

        if not matches:
            log.info("hourly_live: maç bulunamadı")
            return

        # canlı olanları al, her saat en fazla MAX_LIVE_PICKS
        live = [m for m in matches if m.get("live") or m.get("is_live")]
        if not live:
            log.info("hourly_live: şu an canlı maç yok")
            return
        chosen = []
        for m in live:
            if len(chosen) >= MAX_LIVE_PICKS:
                break
            eid = m.get("id") or m.get("idEvent") or m.get("event_id")
            if eid and was_posted_recently(eid, hours=24, path=DB_FILE):
                log.info(f"hourly_live: {eid} son 24saatte gönderildi, atlanıyor")
                continue
            p = ai_predict(m)
            # normalize alanlar
            p.setdefault("home", m.get("home") or m.get("strHomeTeam"))
            p.setdefault("away", m.get("away") or m.get("strAwayTeam"))
            p.setdefault("league", m.get("league") or m.get("strLeague"))
            p.setdefault("odds", m.get("odds", 1.5))
            p.setdefault("confidence", p.get("confidence", 0.5))
            p.setdefault("bet", p.get("bet", "Ev Sahibi Kazanır"))
            # filtre eşikleri
            if p["odds"] >= MIN_ODDS and p["confidence"] >= MIN_CONFIDENCE:
                # dakika/period bilgisi varsa göster
                p["minute"] = m.get("minute") or m.get("intRound") or m.get("strTime") or m.get("time")
                chosen.append((eid, p))

        if not chosen:
            log.info("hourly_live: uygun tahmin yok (filtreler sonrası)")
            return

        # post et ve DB'ye kaydet
        preds = [p for eid,p in chosen]
        text = create_live_banner(preds)
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        # kaydet: posted_events ile 24h koruma
        for eid,p in chosen:
            if eid:
                mark_posted(eid, path=DB_FILE)
        log.info(f"hourly_live: {len(preds)} tahmin gönderildi.")
    except Exception as e:
        log.exception("hourly_live hata:")

async def daily_coupon_job(ctx):
    bot = ctx.bot
    try:
        try:
            matches = await fetch_all_matches(API_FOOTBALL_KEY) if API_FOOTBALL_KEY else await fetch_all_matches()
        except TypeError:
            matches = await fetch_all_matches()
        upcoming = [m for m in matches if not (m.get("live") or m.get("is_live"))]
        picks = []
        for m in upcoming:
            p = ai_predict(m)
            p.setdefault("home", m.get("home"))
            p.setdefault("away", m.get("away"))
            p.setdefault("odds", m.get("odds",1.5))
            p.setdefault("confidence", p.get("confidence",0.5))
            picks.append(p)
        # en yüksek güvene göre sırala ve 3 al
        chosen = sorted(picks, key=lambda x: x.get("confidence",0), reverse=True)[:3]
        if chosen:
            text = create_daily_banner(chosen)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info("daily_coupon: gönderildi.")
    except Exception as e:
        log.exception("daily_coupon hata:")

async def vip_coupon_job(ctx):
    bot = ctx.bot
    try:
        try:
            matches = await fetch_all_matches(API_FOOTBALL_KEY) if API_FOOTBALL_KEY else await fetch_all_matches()
        except TypeError:
            matches = await fetch_all_matches()
        picks = []
        for m in matches:
            p = ai_predict(m)
            p.setdefault("home", m.get("home"))
            p.setdefault("away", m.get("away"))
            p.setdefault("odds", m.get("odds",1.5))
            p.setdefault("confidence", p.get("confidence",0.5))
            picks.append(p)
        vip = sorted(picks, key=lambda x: x.get("confidence",0), reverse=True)[:3]
        if vip:
            text = create_vip_banner(vip)
            await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            log.info("vip_coupon: gönderildi.")
    except Exception as e:
        log.exception("vip_coupon hata:")

async def results_job(ctx):
    # Gün sonu özeti: results.check_results çağır veya kendi özetini at
    bot = ctx.bot
    try:
        # check_results burada asenkron bir fonksiyon ise çağır, değilse sessiz
        try:
            await check_results(bot)
        except TypeError:
            # eğer check_results sync ise ignore
            pass
    except Exception as e:
        log.exception("results_job hata:")

def schedule(app: Application):
    jq = app.job_queue
    # Saatlik canlı: her saat başı (first=0 hemen çalıştırmasın istersen değiştir)
    jq.run_repeating(hourly_live_job, interval=3600, first=10, name="hourly_live")
    # Günlük kupon: günde iki kez değil - istenirse interval ayarla; burada her 12 saatte bir yerine günlük 09:00 TR gibi bir zaman seçilebilir.
    jq.run_repeating(daily_coupon_job, interval=3600*12, first=60, name="daily_coupon")
    # VIP/KASA: günlük
    jq.run_repeating(vip_coupon_job, interval=86400, first=120, name="vip_coupon")
    # Gün sonu özet (Turkey 23:00 -> UTC 20:00)
    from datetime import time as dt_time, timezone
    jq.run_daily(results_job, time=dt_time(hour=20, minute=0, tzinfo=timezone.utc), name="results_check")

async def main():
    # DB init
    init_db(DB_FILE)
    # app ve bot
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    schedule(app)
    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    # keep running
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Durduruldu.")
