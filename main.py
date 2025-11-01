# main.py - 30+ FUTBOL + NBA + EUROLİG + BSL + ATP, RAILWAY UYUMLU
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
CHANNEL = os.getenv("CHANNEL", "@stakedrip")

# Fallback maçlar
FALLBACK_MATCHES = [
    {"teams": {"home": {"name": "Galatasaray"}, "away": {"name": "Fenerbahçe"}}, "sport": "football", "league": "Süper Lig"},
    {"teams": {"home": {"name": "Anadolu Efes"}, "away": {"name": "Fenerbahçe Beko"}}, "sport": "basketball", "league": "BSL"},
    {"teams": {"home": {"name": "Real Madrid"}, "away": {"name": "Barcelona"}}, "sport": "basketball", "league": "EuroLeague"},
    {"teams": {"home": {"name": "Lakers"}, "away": {"name": "Warriors"}}, "sport": "basketball", "league": "NBA"},
    {"teams": {"home": {"name": "Djokovic"}, "away": {"name": "Alcaraz"}}, "sport": "tennis", "league": "ATP"}
]

# 30+ LİG + BASKETBOL + TENİS
LEAGUES = {
    "football": [
        {"name": "Süper Lig", "id": 140},
        {"name": "Premier Lig", "id": 39},
        {"name": "La Liga", "id": 61},
        {"name": "Serie A", "id": 135},
        {"name": "Bundesliga", "id": 78},
        {"name": "Ligue 1", "id": 61},
        {"name": "Eredivisie", "id": 88},
        {"name": "Primeira Liga", "id": 94},
        {"name": "Brasileirão", "id": 71},
        {"name": "MLS", "id": 253},
        {"name": "J1 League", "id": 98},
        {"name": "K League", "id": 292},
        {"name": "A-League", "id": 188},
        {"name": "Saudi Pro League", "id": 307},
        {"name": "Belçika Pro League", "id": 144},
        {"name": "Avusturya Bundesliga", "id": 218},
        {"name": "İskoçya Premiership", "id": 179},
        {"name": "Danimarka Superliga", "id": 119},
        {"name": "Norveç Eliteserien", "id": 103},
        {"name": "İsveç Allsvenskan", "id": 113},
        {"name": "Rusya Premier Lig", "id": 235},
        {"name": "Ukrayna Premier Lig", "id": 333},
        {"name": "Polonya Ekstraklasa", "id": 106},
        {"name": "Çek Liga", "id": 345},
        {"name": "Hırvatistan HNL", "id": 210},
        {"name": "Yunanistan Super League", "id": 197},
        {"name": "Arjantin Liga Profesional", "id": 128},
        {"name": "Kolombiya Primera A", "id": 253},
        {"name": "Meksika Liga MX", "id": 262},
        {"name": "Şili Primera División", "id": 268}
    ],
    "basketball": [
        {"name": "NBA", "id": 12},
        {"name": "EuroLeague", "id": 133},     # EuroLeague
        {"name": "BSL (Türkiye)", "id": 183}   # Türkiye Basketbol Süper Ligi
    ],
    "tennis": [{"name": "ATP", "id": 1}]
}

SPORTS_URL = {
    "football": "https://v3.football.api-sports.io",
    "basketball": "https://v3.basketball.api-sports.io",
    "tennis": "https://v3.tennis.api-sports.io"
}

# ====================== API WRAPPER ======================
async def fetch_matches(sport: str = "football", hours: int = 24):
    if not API_KEY:
        logger.warning("API_KEY yok → Fallback maçlar")
        return FALLBACK_MATCHES

    url_base = SPORTS_URL[sport]
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": url_base.split("://")[1].split("/")[0]
    }

    all_matches = []
    leagues = LEAGUES[sport]

    for league in leagues:
        params = {
            "league": league["id"],
            "season": datetime.now().year,
            "from": datetime.now().strftime("%Y-%m-%d"),
            "to": (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d"),
            "timezone": "Europe/Istanbul"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url_base}/fixtures", headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        matches = data.get("response", [])
                        for m in matches:
                            m["sport"] = sport
                            m["league"] = league["name"]
                        all_matches.extend(matches[:2])  # Her ligden max 2 maç
                        if matches:
                            logger.info(f"{league['name']} → {len(matches)} maç çekildi")
                    else:
                        logger.error(f"{league['name']} API Hatası: {resp.status}")
        except Exception as e:
            logger.error(f"{league['name']} Bağlantı hatası: {e}")

    if not all_matches:
        logger.warning("Hiç maç çekilemedi → Fallback")
        return FALLBACK_MATCHES

    random.shuffle(all_matches)
    return all_matches[:10]  # Toplam 10 rastgele maç

# ====================== AI TAHMİN ======================
def predict_match(home_goals: float = 1.6, away_goals: float = 1.2, sport: str = "football"):
    total = max(home_goals + away_goals, 0.1)
    p_home = home_goals / total
    p_draw = 0.25 + random.uniform(-0.05, 0.05) if sport != "tennis" else 0
    p_away = max(1 - p_home - p_draw, 0.1)

    result = "1" if p_home > 0.45 else "X" if p_draw > 0.35 else "2"
    over25 = total > 2.5
    kg = home_goals > 0.9 and away_goals > 0.8
    oran = round(max(p_home, p_away, p_draw if p_draw > 0 else p_away) * 2.8 + random.uniform(-0.3, 0.4), 2)

    if sport == "tennis":
        return {
            "1X2": result,
            "AltUst": "Üst 22.5 Set" if over25 else "Alt 22.5 Set",
            "KG": "Her İkisi Kazanır Set" if kg else "Yok",
            "Oran": oran
        }
    else:
        return {
            "1X2": result,
            "AltUst": "Üst 2.5" if over25 else "Alt 2.5",
            "KG": "KG Var" if kg else "KG Yok",
            "Oran": oran
        }

# ====================== FORMAT ======================
def format_match(home: str, away: str, pred: dict, sport: str, league: str, is_hourly: bool = True):
    emoji = "⚽" if sport == "football" else "🏀" if sport == "basketball" else "🎾"
    league_tag = f"*{league}*" if is_hourly else league
    if is_hourly:
        return (
            f"**{home} vs {away}** {emoji}\n"
            f"{league_tag}\n"
            f"**{pred['1X2']}** | {pred['AltUst']} | {pred['KG']}\n"
            f"Oran: **{pred['Oran']}** (AI)"
        )
    else:
        return f"**{home} vs {away}** {emoji}\n{league_tag}\n{pred['1X2']} @ {pred['Oran']}"

# ====================== JOBS ======================
async def hourly_prediction(context: ContextTypes.DEFAULT_TYPE):
    sport = random.choice(["football", "basketball", "tennis"])
    matches = await fetch_matches(sport, 3)
    if not matches:
        return

    match = random.choice(matches)
    home = match.get("teams", {}).get("home", {}).get("name", "Ev Sahibi")
    away = match.get("teams", {}).get("away", {}).get("name", "Deplasman")
    league = match.get("league", "Bilinmeyen Lig")
    pred = predict_match(1.7, 1.3, sport)

    msg = f"**{datetime.now().strftime('%H:%M')} CANLI TAHMİN**\n\n{format_match(home, away, pred, sport, league, is_hourly=True)}"
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

async def daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    all_matches = []
    for sport in ["football", "basketball", "tennis"]:
        ms = await fetch_matches(sport, 24)
        all_matches.extend([(m, sport) for m in ms])

    if len(all_matches) < 2:
        return

    selected = random.sample(all_matches, min(3, len(all_matches)))
    lines = []
    total_odds = 1.0

    for m, sport in selected:
        home = m.get('teams', {}).get('home', {}).get('name', 'Ev Sahibi')
        away = m.get('teams', {}).get('away', {}).get('name', 'Deplasman')
        league = m.get("league", "Bilinmeyen Lig")
        pred = predict_match(1.8, 1.4, sport)
        total_odds *= pred["Oran"]
        lines.append(format_match(home, away, pred, sport, league, is_hourly=False))

    msg = (
        f"**GÜNLÜK KUPON ({datetime.now().strftime('%d.%m')})**\n\n"
        + "\n\n".join(lines)
        + f"\n\n**Toplam Oran: {total_odds:.2f}**"
    )
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

# ====================== KOMUTLAR ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Canlı tahmin botu aktif!\n"
        f"Futbol (30+ lig), NBA, EuroLeague, BSL, ATP\n"
        f"Kanal: {CHANNEL}"
    )

# ====================== ANA FONKSİYON ======================
def main():
    if not TOKEN:
        print("HATA: TELEGRAM_TOKEN eksik!")
        return

    print(f"Bot başlatılıyor... Kanal: {CHANNEL}")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    job = app.job_queue
    job.run_repeating(hourly_prediction, interval=3600, first=10)
    job.run_daily(daily_coupon, time=time(9, 0))

    print("Bot çalışıyor... (30+ Lig + EuroLeague + BSL + NBA + ATP)")

    app.run_polling()

# ====================== ÇALIŞTIR ======================
if __name__ == "__main__":
    main()
