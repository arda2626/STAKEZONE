# main.py - RAILWAY UYUMLU, EVENT LOOP HATASI YOK
import asyncio
import random
import aiohttp
import logging
from datetime import datetime, timedelta, time
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ====================== LOGGING ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== CONFIG ======================
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")
CHANNEL = os.getenv("CHANNEL", "@ai_tahmin_kanali")

FALLBACK_MATCHES = [
    {"teams": {"home": {"name": "Galatasaray"}, "away": {"name": "Fenerbahçe"}}},
    {"teams": {"home": {"name": "Manchester City"}, "away": {"name": "Arsenal"}}}
]

SPORTS = {
    "football": {"url": "https://v3.football.api-sports.io", "league": 140},
    "basketball": {"url": "https://v3.basketball.api-sports.io", "league": 12},
    "tennis": {"url": "https://v3.tennis.api-sports.io", "league": 1}
}

# ====================== API WRAPPER ======================
async def fetch_matches(sport: str = "football", hours: int = 24):
    if not API_KEY:
        logger.warning("API_KEY yok → Fallback maçlar")
        return FALLBACK_MATCHES

    config = SPORTS[sport]
    url = f"{config['url']}/fixtures"
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": config["url"].split("://")[1].split("/")[0]
    }
    params = {
        "league": config["league"],
        "season": datetime.now().year,
        "from": datetime.now().strftime("%Y-%m-%d"),
        "to": (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d"),
        "timezone": "Europe/Istanbul"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", [])[:10]
    except Exception as e:
        logger.error(f"API hatası: {e}")

    return FALLBACK_MATCHES

# ====================== AI TAHMİN ======================
def predict_match(home_goals: float = 1.6, away_goals: float = 1.2):
    total = max(home_goals + away_goals, 0.1)
    p_home = home_goals / total
    p_draw = 0.25 + random.uniform(-0.05, 0.05)
    p_away = max(1 - p_home - p_draw, 0.1)

    result = "1" if p_home > 0.45 else "X" if p_draw > 0.35 else "2"
    over25 = total > 2.5
    kg = home_goals > 0.9 and away_goals > 0.8
    oran = round(max(p_home, p_away, p_draw) * 2.8 + random.uniform(-0.3, 0.4), 2)

    return {
        "1X2": result,
        "AltUst": "Üst 2.5" if over25 else "Alt 2.5",
        "KG": "KG Var" if kg else "KG Yok",
        "Oran": oran
    }

# ====================== FORMAT ======================
def format_match(home: str, away: str, pred: dict, is_hourly: bool = True):
    if is_hourly:
        return (
            f"**{home} vs {away}**\n"
            f"**{pred['1X2']}** | {pred['AltUst']} | {pred['KG']}\n"
            f"Oran: **{pred['Oran']}** (AI)"
        )
    else:
        return f"**{home} vs {away}**\n{pred['1X2']} @ {pred['Oran']}"

# ====================== JOBS ======================
async def hourly_prediction(context: ContextTypes.DEFAULT_TYPE):
    sport = random.choice(["football", "basketball"])
    matches = await fetch_matches(sport, 3)
    if not matches:
        return

    match = random.choice(matches)
    home = match.get("teams", {}).get("home", {}).get("name", "Ev Sahibi")
    away = match.get("teams", {}).get("away", {}).get("name", "Deplasman")
    pred = predict_match(1.7, 1.3)

    msg = f"**{datetime.now().strftime('%H:%M')} CANLI TAHMİN**\n\n{format_match(home, away, pred, is_hourly=True)}"
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

async def daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    all_matches = []
    for sport in ["football", "basketball"]:
        ms = await fetch_matches(sport, 24)
        all_matches.extend(ms)

    if len(all_matches) < 2:
        return

    selected = random.sample(all_matches, min(2, len(all_matches)))
    lines = []
    total_odds = 1.0

    for m in selected:
        home = m.get('teams', {}).get('home', {}).get('name', 'Ev Sahibi')
        away = m.get('teams', {}).get('away', {}).get('name', 'Deplasman')
        pred = predict_match(1.8, 1.4)
        total_odds *= pred["Oran"]
        lines.append(format_match(home, away, pred, is_hourly=False))

    msg = (
        f"**GÜNLÜK KUPON ({datetime.now().strftime('%d.%m')})**\n\n"
        + "\n\n".join(lines)
        + f"\n\n**Toplam Oran: {total_odds:.2f}**"
    )
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

# ====================== KOMUTLAR ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Canlı tahmin botu aktif!\nKanal: {CHANNEL}")

# ====================== ANA FONKSİYON ======================
def main():
    if not TOKEN:
        print("HATA: TELEGRAM_TOKEN eksik!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    job = app.job_queue
    job.run_repeating(hourly_prediction, interval=3600, first=10)
    job.run_daily(daily_coupon, time=time(9, 0))

    print("Bot çalışıyor... (TEK DOSYA, EVENT LOOP HATASI YOK)")

    # run_polling() kendi loop'unu yönetir → asyncio.run() YOK!
    app.run_polling()  # SENKRON ÇALIŞIR

# ====================== ÇALIŞTIR ======================
if __name__ == "__main__":
    main()  # asyncio.run() YOK!
