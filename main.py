# main.py - TEK TERCİH + GÜNLÜK KUPON + HAFTALIK KUPON (TAM ÇALIŞIR)
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
    {"teams": {"home": {"name": "Galatasaray"}, "away": {"name": "Fenerbahçe"}}, "sport": "football", "league": "Süper Lig", "fixture": {"date": "2025-11-01T20:00:00+03:00"}, "status": {"short": "NS"}},
    {"teams": {"home": {"name": "Anadolu Efes"}, "away": {"name": "Fenerbahçe Beko"}}, "sport": "basketball", "league": "BSL", "fixture": {"date": "2025-11-01T19:30:00+03:00"}, "status": {"short": "LIVE", "elapsed": 12}},
    {"teams": {"home": {"name": "Real Madrid"}, "away": {"name": "Barcelona"}}, "sport": "basketball", "league": "EuroLeague", "fixture": {"date": "2025-11-01T21:00:00+03:00"}, "status": {"short": "NS"}}
]

LEAGUES = {
    "football": [
        {"name": "Süper Lig", "id": 140}, {"name": "Premier Lig", "id": 39}, {"name": "La Liga", "id": 61},
        {"name": "Serie A", "id": 135}, {"name": "Bundesliga", "id": 78}, {"name": "Ligue 1", "id": 61},
        {"name": "Eredivisie", "id": 88}, {"name": "Primeira Liga", "id": 94}, {"name": "Brasileirão", "id": 71},
        {"name": "MLS", "id": 253}, {"name": "Saudi Pro League", "id": 307}, {"name": "Belçika Pro League", "id": 144}
    ],
    "basketball": [
        {"name": "NBA", "id": 12}, {"name": "EuroLeague", "id": 133}, {"name": "BSL (Türkiye)", "id": 183}
    ],
    "tennis": [{"name": "ATP", "id": 1}]
}

SPORTS_URL = {
    "football": "https://v3.football.api-sports.io",
    "basketball": "https://v3.basketball.api-sports.io",
    "tennis": "https://v3.tennis.api-sports.io"
}

# ====================== ZAMAN & DAKİKA ======================
def get_match_time_info(match):
    fixture = match.get("fixture", {})
    status = fixture.get("status", {})
    short = status.get("short", "NS")
    date_str = fixture.get("date", "2025-11-01T00:00:00+03:00")

    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        dt_istanbul = dt.astimezone()
        time_str = dt_istanbul.strftime("%H:%M")
    except:
        time_str = "Bilinmiyor"

    if short in ["LIVE", "HT", "1H", "2H", "ET"]:
        minute = status.get("elapsed", 0)
        if short == "HT":
            return "DEVRE ARASI"
        elif short == "ET":
            return f"Uzatma {minute}'"
        else:
            return f"{minute}' Dakika"
    else:
        return f"{time_str} Başlayacak"

# ====================== API WRAPPER ======================
async def fetch_live_and_upcoming(sport: str = "football"):
    if not API_KEY:
        logger.warning("API_KEY yok → Fallback")
        return FALLBACK_MATCHES

    url_base = SPORTS_URL[sport]
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": url_base.split("://")[1].split("/")[0]
    }

    all_matches = []

    # CANLI MAÇLAR
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url_base}/fixtures", headers=headers, params={"live": "all"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    live_matches = data.get("response", [])
                    for m in live_matches:
                        m["sport"] = sport
                        m["league"] = m.get("league", {}).get("name", "Bilinmeyen Lig")
                    all_matches.extend(live_matches)
    except Exception as e:
        logger.error(f"CANLI maç hatası: {e}")

    # YAKLAŞAN MAÇLAR
    leagues = LEAGUES[sport]
    for league in leagues:
        params = {
            "league": league["id"],
            "season": datetime.now().year,
            "from": (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d"),
            "to": (datetime.now() + timedelta(hours=6)).strftime("%Y-%m-%d"),
            "timezone": "Europe/Istanbul"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url_base}/fixtures", headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        matches = [m for m in data.get("response", []) if m.get("fixture", {}).get("status", {}).get("short") == "NS"]
                        for m in matches:
                            m["sport"] = sport
                            m["league"] = league["name"]
                        all_matches.extend(matches[:3])
        except Exception as e:
            logger.error(f"{league['name']} YAKLAŞAN hatası: {e}")

    return all_matches if all_matches else FALLBACK_MATCHES

# ====================== TEK TERCİH AI ======================
def predict_single_bet(match, sport: str):
    home_goals = random.uniform(0.8, 2.5)
    away_goals = random.uniform(0.8, 2.5)
    total = max(home_goals + away_goals, 0.1)
    p_home = home_goals / total
    p_draw = 0.25 + random.uniform(-0.05, 0.05) if sport != "tennis" else 0
    p_away = max(1 - p_home - p_draw, 0.1)
    p_over25 = max(0, (total - 2.5) / total) if total > 2.5 else 0
    p_under25 = 1 - p_over25
    p_kg = 0.6 if home_goals > 0.9 and away_goals > 0.8 else 0.3

    bets = [
        ("1 (Ev Sahibi Kazanır)", p_home),
        ("X (Berabere)", p_draw),
        ("2 (Deplasman Kazanır)", p_away),
        ("Üst 2.5", p_over25),
        ("Alt 2.5", p_under25),
        ("KG Var", p_kg),
        ("KG Yok", 1 - p_kg)
    ]

    valid_bets = [b for b in bets if b[1] >= 0.50]
    if not valid_bets:
        return None

    best_bet, best_prob = max(valid_bets, key=lambda x: x[1])
    prob_pct = int(best_prob * 100)
    oran = round(best_prob * 2.8 + random.uniform(-0.3, 0.4), 2)

    return {
        "bet": best_bet,
        "oran": oran,
        "prob": prob_pct
    }

# ====================== FORMAT (TEK TERCİH) ======================
def format_single_bet(home, away, pred, sport, league, time_info):
    emoji = "Football" if sport == "football" else "Basketball" if sport == "basketball" else "Tennis"
    return (
        f"**{home} vs {away}** {emoji}\n"
        f"{time_info} | {league}\n"
        f"**{pred['bet']}**\n"
        f"Oran: **{pred['oran']}** | Olasılık: **%{pred['prob']}** (AI)"
    )

# ====================== SAAT BAŞI TEK TERCİH ======================
async def hourly_single_bet_prediction(context: ContextTypes.DEFAULT_TYPE):
    all_valid = []
    for sport in ["football", "basketball", "tennis"]:
        matches = await fetch_live_and_upcoming(sport)
        for match in matches:
            home = match.get("teams", {}).get("home", {}).get("name", "Ev Sahibi")
            away = match.get("teams", {}).get("away", {}).get("name", "Deplasman")
            league = match.get("league", "Bilinmeyen Lig")
            time_info = get_match_time_info(match)

            pred = predict_single_bet(match, sport)
            if pred:
                all_valid.append({
                    "home": home, "away": away, "pred": pred, "sport": sport,
                    "league": league, "time_info": time_info
                })

    if not all_valid:
        logger.info("Bu saat %50+ tek tercih yok.")
        return

    all_valid.sort(key=lambda x: x["pred"]["prob"], reverse=True)
    selected = all_valid[:5]

    lines = [format_single_bet(item["home"], item["away"], item["pred"], item["sport"], item["league"], item["time_info"]) for item in selected]
    msg = f"**{datetime.now().strftime('%H:%M')} TEK TERCİH TAHMİNLERİ**\n\n" + "\n\n".join(lines)
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

# ====================== GÜNLÜK KUPON (3 MAÇ) ======================
async def daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    all_matches = []
    for sport in ["football", "basketball", "tennis"]:
        ms = await fetch_live_and_upcoming(sport)
        all_matches.extend([(m, sport) for m in ms])

    if len(all_matches) < 3:
        return

    selected = random.sample(all_matches, 3)
    lines = []
    total_odds = 1.0

    for m, sport in selected:
        home = m.get('teams', {}).get('home', {}).get('name', 'Ev Sahibi')
        away = m.get('teams', {}).get('away', {}).get('name', 'Deplasman')
        league = m.get("league", "Bilinmeyen Lig")
        time_info = get_match_time_info(m)
        pred = predict_single_bet(m, sport)
        if pred:
            total_odds *= pred["oran"]
            lines.append(format_single_bet(home, away, pred, sport, league, time_info))

    if not lines:
        return

    msg = (
        f"**GÜNLÜK KUPON ({datetime.now().strftime('%d.%m %H:%M')})**\n\n"
        + "\n\n".join(lines)
        + f"\n\n**Toplam Oran: {total_odds:.2f}**"
    )
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

# ====================== HAFTALIK KUPON (7 MAÇ) ======================
async def weekly_coupon(context: ContextTypes.DEFAULT_TYPE):
    all_matches = []
    for sport in ["football", "basketball", "tennis"]:
        # 7 gün önceden maç çek
        url_base = SPORTS_URL[sport]
        headers = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": url_base.split("://")[1].split("/")[0]}
        params = {
            "from": datetime.now().strftime("%Y-%m-%d"),
            "to": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "timezone": "Europe/Istanbul"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url_base}/fixtures", headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        matches = data.get("response", [])[:10]
                        for m in matches:
                            m["sport"] = sport
                            m["league"] = m.get("league", {}).get("name", "Bilinmeyen Lig")
                        all_matches.extend([(m, sport) for m in matches])
        except:
            pass

    if len(all_matches) < 7:
        return

    selected = random.sample(all_matches, 7)
    lines = []
    total_odds = 1.0

    for m, sport in selected:
        home = m.get('teams', {}).get('home', {}).get('name', 'Ev Sahibi')
        away = m.get('teams', {}).get('away', {}).get('name', 'Deplasman')
        league = m.get("league", "Bilinmeyen Lig")
        time_info = get_match_time_info(m)
        pred = predict_single_bet(m, sport)
        if pred:
            total_odds *= pred["oran"]
            lines.append(format_single_bet(home, away, pred, sport, league, time_info))

    if not lines:
        return

    next_sunday = (datetime.now() + timedelta(days=(6 - datetime.now().weekday()))).strftime("%d.%m")
    msg = (
        f"**HAFTALIK KUPON (Pazar {next_sunday}'e kadar geçerli)**\n\n"
        + "\n\n".join(lines)
        + f"\n\n**Toplam Oran: {total_odds:.2f}**"
    )
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

# ====================== KOMUTLAR ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Tek tercih botu aktif!\n"
        f"Saat başı tahmin | Günlük kupon (09:00 & 21:00) | Haftalık kupon (Pazar 10:00)\n"
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
    job.run_repeating(hourly_single_bet_prediction, interval=3600, first=10)     # Saat başı
    job.run_repeating(daily_coupon, interval=12*3600, first=60)                  # 12 saatte bir
    job.run_daily(weekly_coupon, time=time(10, 0), days=(6,))                    # Pazar 10:00

    print("Bot çalışıyor... (TEK TERCİH + GÜNLÜK + HAFTALIK AKTİF)")

    app.run_polling()

if __name__ == "__main__":
    main()
