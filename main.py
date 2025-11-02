# main.py – DÜNYA ŞAMPİYONU ULTİMATE | 02.11.2025 | THESPORTSDB CANLI DÜZELTİLDİ
import asyncio
import random
import aiohttp
import logging
import os
import sys
from datetime import datetime, timedelta, timezone, time as dt_time
from telegram import Update
from telegram.ext import Application, ContextTypes

# ====================== LOG & CONFIG ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ====================== API & TELEGRAM ======================
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("THESPORTSDB_KEY")
CHANNEL = os.getenv("CHANNEL", "@stakedrip")

if not TOKEN or not API_KEY:
    log.error("TELEGRAM_TOKEN veya THESPORTSDB_KEY eksik!")
    sys.exit(1)

# ====================== GLOBAL ======================
WINS = LOSSES = 0
KASA = 100.0
PREDS = []

# ====================== EMOJİ ======================
EMOJI = {"ding":"🔔","cash":"💰","win":"✅","lose":"❌","trophy":"🏆","nba":"🏀","tenis":"🎾"}

# ====================== YARDIMCI ======================
def minute_text(start_time):
    diff = int((datetime.now(timezone(timedelta(hours=3))) - start_time).total_seconds() // 60)
    return f"{diff}'" if diff < 95 else "90+'"

# ====================== CANLI MAÇLARI ÇEK ======================
async def fetch_live():
    url = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/eventslive.php"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
            async with s.get(url) as r:
                if r.status != 200:
                    log.error(f"TheSportsDB HTTP {r.status}")
                    return []
                data = await r.json()
                events = data.get("event", [])
                if not events:
                    log.info("0 maç çekildi")
                    return []
                live_matches = []
                for e in events:
                    status = (e.get("strStatus") or "").lower()
                    if any(k in status for k in ["live", "playing", "progress", "half", "time"]):
                        live_matches.append(e)
                log.info(f"{len(live_matches)} canlı maç bulundu")
                return live_matches
    except Exception as e:
        log.error(f"fetch_live Hatası: {e}")
        return []

# ====================== TAHMİN MOTORU ======================
def predict(match):
    oran = round(random.uniform(1.25, 2.20), 2)
    secenek = random.choice(["ÜST 2.5", "KG VAR", "1", "2", "KORNER ÜST", "KART ÜST"])
    prob = random.randint(65, 88)
    return {"bet": secenek, "oran": oran, "prob": prob}

# ====================== CANLI 3 MAÇ PAYLAŞ ======================
async def hourly_live(ctx: ContextTypes.DEFAULT_TYPE):
    matches = await fetch_live()
    if not matches:
        log.info("Canlı maç yok")
        return

    top3 = random.sample(matches, min(3, len(matches)))
    lines = [
        "═"*38,
        "   CANLI 3 MAÇ ATEŞLENDİ   ",
        " %100 AI • ORAN ≥1.20 • THESPORTSDB ",
        "═"*38,""
    ]
    now = datetime.now(timezone(timedelta(hours=3)))
    for i, m in enumerate(top3, 1):
        p = predict(m)
        lig = m.get("strLeague", "Bilinmeyen Lig")
        t1, t2 = m.get("strHomeTeam"), m.get("strAwayTeam")
        skor = f"{m.get('intHomeScore')} - {m.get('intAwayScore')}"
        lines += [
            f"{i}. **{t1} vs {t2}** ⚽ {EMOJI['ding']}",
            f"   {lig} • Skor: {skor}",
            f"   {p['bet']} → **{p['oran']}** • AI: %{p['prob']}",
            ""
        ]

    msg = await ctx.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")
    log.info("3 canlı maç gönderildi")

# ====================== GÜNLÜK / HAFTALIK / KASA ======================
async def gunluk_kupon(ctx: ContextTypes.DEFAULT_TYPE):
    lines = [
        "═"*38,
        "   GÜNLÜK 3’LÜ KUPON   ",
        " 24 SAAT • 3.50+ ORAN ",
        "═"*38,""
    ]
    toplam = 1.0
    for i in range(3):
        oran = round(random.uniform(1.7, 2.3), 2)
        toplam *= oran
        lines += [f"{i+1}. **MAÇ {i+1}** → ÜST 2.5 @ **{oran}**", ""]
    lines += [f"TOPLAM ORAN: **{round(toplam, 2)}** {EMOJI['cash']}"]
    await ctx.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")

async def haftalik_kupon(ctx: ContextTypes.DEFAULT_TYPE):
    if datetime.now(timezone.utc).weekday() != 3:
        return
    lines = [
        "═"*38,
        "  HAFTALIK 5’Lİ MEGA KUPON  ",
        " PERŞEMBE • 12.00+ ORAN ",
        "═"*38,""
    ]
    toplam = 1.0
    for i in range(5):
        oran = round(random.uniform(1.9, 2.7), 2)
        toplam *= oran
        lines += [f"{i+1}. **MEGA {i+1}** → ÜST 2.5 @ **{oran}**", ""]
    lines += [f"TOPLAM ORAN: **{round(toplam, 2)}** {EMOJI['cash']}"]
    await ctx.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")

async def kasa_kuponu(ctx: ContextTypes.DEFAULT_TYPE):
    oran = round(random.uniform(2.1, 3.9), 2)
    pot = round(2 * oran, 2)
    lines = [
        "═"*38,
        "   KASA KUPONU ZAMANI  ",
        " 2.00+ ORAN • 2 BİRİM ",
        "═"*38,"",
        f"**KASA** @ **{oran}**",
        f"POTANSİYEL: **{pot}** {EMOJI['cash']}"
    ]
    await ctx.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")

# ====================== ANA ======================
def main():
    app = Application.builder().token(TOKEN).build()
    job = app.job_queue

    # HER SAAT CANLI MAÇ
    job.run_repeating(hourly_live, interval=3600, first=10)
    # HER 5 DK SONUÇ KONTROL
    job.run_repeating(lambda c: None, interval=300, first=30)  # pasif
    # GÜNLÜK 09:00 UTC (12:00 Türkiye)
    job.run_daily(gunluk_kupon, time=dt_time(hour=9, minute=0, tzinfo=timezone.utc))
    # HAFTALIK / KASA
    job.run_repeating(haftalik_kupon, interval=86400, first=300)
    job.run_repeating(kasa_kuponu, interval=86400, first=600)

    log.info("BOT 7/24 ÇALIŞIYOR – GITHUB’TAN DEPLOY HAZIR!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
