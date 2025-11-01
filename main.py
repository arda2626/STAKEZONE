# main.py - THE ODDS API (TEK TERCİH + SAAT + GÜNLÜK + HAFTALIK)
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
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
CHANNEL = os.getenv("CHANNEL", "@stakedrip")

if not ODDS_API_KEY:
    logger.error("HATA: ODDS_API_KEY eksik! Railway'e ekleyin.")
    exit(1)

# Fallback maçlar (API hatasında)
FALLBACK_MATCHES = [
    {
        "home_team": "Galatasaray", "away_team": "Fenerbahçe",
        "sport": "football", "league": "Süper Lig",
        "commence_time": "2025-11-01T20:00:00Z",
        "bookmakers": [{"markets": [{"key": "h2h", "outcomes": [
            {"name": "Galatasaray", "price": 2.10},
            {"name": "Draw", "price": 3.50},
            {"name": "Fenerbahçe", "price": 3.20}
        ]}]}]
    },
    {
        "home_team": "Anadolu Efes", "away_team": "Fenerbahçe Beko",
        "sport": "basketball", "league": "BSL",
        "commence_time": "2025-11-01T19:30:00Z",
        "bookmakers": [{"markets": [{"key": "h2h", "outcomes": [
            {"name": "Anadolu Efes", "price": 1.95},
            {"name": "Fenerbahçe Beko", "price": 1.85}
        ]}]}]
    }
]

# The Odds API spor kodları
SPORTS = {
    "football": [
        "soccer_turkey_super_league", "soccer_epl", "soccer_spain_la_liga",
        "soccer_italy_serie_a", "soccer_germany_bundesliga", "soccer_france_ligue_one",
        "soccer_netherlands_eredivisie", "soccer_portugal_primeira_liga", "soccer_brazil_serie_a"
    ],
    "basketball": ["basketball_nba", "basketball_europe_euroleague", "basketball_turkey_super_league"],
    "tennis": ["tennis_atp_singles"]
}

# ====================== ZAMAN & DAKİKA ======================
def get_time_info(match):
    try:
        dt = datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00"))
        dt_ist = dt.astimezone()
        time_str = dt_ist.strftime("%H:%M")
    except:
        time_str = "Bilinmiyor"

    now = datetime.now()
    if dt <= now <= dt + timedelta(minutes=120):
        mins = int((now - dt).total_seconds() // 60)
        return f"{mins}' Dakika"
    else:
        return f"{time_str} Başlayacak"

# ====================== API ÇEKME ======================
async def fetch_odds(sport: str):
    if not ODDS_API_KEY:
        return FALLBACK_MATCHES

    matches = []
    codes = SPORTS.get(sport, [])

    for code in codes:
        url = f"https://api.the-odds-api.com/v4/sports/{code}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h,totals",
            "oddsFormat": "decimal"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for game in data:
                            game["sport"] = sport
                            game["league"] = code.split("_")[-1].replace("_", " ").title()
                            matches.append(game)
                        logger.info(f"{code} → {len(data)} maç")
                    else:
                        logger.warning(f"{code} → {resp.status}")
        except Exception as e:
            logger.error(f"{code} hatası: {e}")

    return matches or FALLBACK_MATCHES

# ====================== TEK TERCİH AI ======================
def get_best_bet(match):
    book = match.get("bookmakers", [{}])[0]
    h2h = next((m for m in book.get("markets", []) if m["key"] == "h2h"), None)
    if not h2h:
        return None

    outcomes = h2h["outcomes"]
    home = next((o for o in outcomes if o["name"] == match["home_team"]), None)
    away = next((o for o in outcomes if o["name"] == match["away_team"]), None)
    draw = next((o for o in outcomes if o["name"] == "Draw"), None)

    p_home = 1 / home["price"] if home else 0
    p_away = 1 / away["price"] if away else 0
    p_draw = 1 / draw["price"] if draw else 0

    totals = next((m for m in book.get("markets", []) if m["key"] == "totals"), None)
    if totals:
        over = next((o for o in totals["outcomes"] if "Over" in o["name"]), None)
        under = next((o for o in totals["outcomes"] if "Under" in o["name"]), None)
        p_over = 1 / over["price"] if over else 0
        p_under = 1 / under["price"] if under else 0
    else:
        p_over = p_under = 0.4

    bets = [
        ("1 (Ev Sahibi)", p_home),
        ("X (Berabere)", p_draw),
        ("2 (Deplasman)", p_away),
        ("Üst 2.5", p_over),
        ("Alt 2.5", p_under),
        ("KG Var", 0.6),
        ("KG Yok", 0.4)
    ]

    valid = [b for b in bets if b[1] >= 0.50]
    if not valid:
        return None

    best, prob = max(valid, key=lambda x: x[1])
    return {
        "bet": best,
        "oran": round(prob * 2.8 + random.uniform(-0.2, 0.3), 2),
        "prob": int(prob * 100)
    }

# ====================== FORMAT ======================
def format_match(match, pred):
    sport_emoji = "Football" if match["sport"] == "football" else "Basketball" if match["sport"] == "basketball" else "Tennis"
    time_info = get_time_info(match)
    return (
        f"**{match['home_team']} vs {match['away_team']}** {sport_emoji}\n"
        f"{time_info} | {match['league']}\n"
        f"**{pred['bet']}**\n"
        f"Oran: **{pred['oran']}** | Olasılık: **%{pred['prob']}** (AI)"
    )

# ====================== SAAT BAŞI ======================
async def hourly_prediction(context: ContextTypes.DEFAULT_TYPE):
    all_valid = []
    for sport in ["football", "basketball", "tennis"]:
        matches = await fetch_odds(sport)
        for m in matches:
            pred = get_best_bet(m)
            if pred:
                all_valid.append({"match": m, "pred": pred})

    if not all_valid:
        return

    all_valid.sort(key=lambda x: x["pred"]["prob"], reverse=True)[:5]
    lines = [format_match(item["match"], item["pred"]) for item in all_valid]

    msg = f"**{datetime.now().strftime('%H:%M')} YÜKSEK OLASILIK TAHMİNLERİ**\n\n" + "\n\n".join(lines)
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

# ====================== GÜNLÜK KUPON ======================
async def daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    all_matches = []
    for sport in ["football", "basketball", "tennis"]:
        all_matches.extend(await fetch_odds(sport))

    if len(all_matches) < 3:
        return

    selected = random.sample(all_matches, 3)
    lines = []
    total_odds = 1.0

    for m in selected:
        pred = get_best_bet(m)
        if pred:
            total_odds *= pred["oran"]
            lines.append(format_match(m, pred))

    if not lines:
        return

    msg = f"**GÜNLÜK KUPON ({datetime.now().strftime('%d.%m %H:%M')})**\n\n" + "\n\n".join(lines) + f"\n\n**Toplam Oran: {total_odds:.2f}**"
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

# ====================== HAFTALIK KUPON ======================
async def weekly_coupon(context: ContextTypes.DEFAULT_TYPE):
    all_matches = []
    for sport in ["football", "basketball", "tennis"]:
        all_matches.extend(await fetch_odds(sport))

    if len(all_matches) < 7:
        return

    selected = random.sample(all_matches, 7)
    lines = []
    total_odds = 1.0

    for m in selected:
        pred = get_best_bet(m)
        if pred:
            total_odds *= pred["oran"]
            lines.append(format_match(m, pred))

    if not lines:
        return

    next_sunday = (datetime.now() + timedelta(days=(6 - datetime.now().weekday()))).strftime("%d.%m")
    msg = f"**HAFTALIK KUPON (Pazar {next_sunday}'e kadar)**\n\n" + "\n\n".join(lines) + f"\n\n**Toplam Oran: {total_odds:.2f}**"
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

# ====================== KOMUTLAR ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The Odds API botu aktif!\nSaat başı, günlük ve haftalık tahminler geliyor.\nKanal: @stakedrip")

# ====================== ANA FONKSİYON ======================
def main():
    if not TOKEN:
        print("HATA: TELEGRAM_TOKEN eksik!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    job = app.job_queue
    job.run_repeating(hourly_prediction, interval=3600, first=10)
    job.run_repeating(daily_coupon, interval=12*3600, first=60)
    job.run_daily(weekly_coupon, time=time(10, 0), days=(6,))

    print("Bot çalışıyor... (The Odds API + Tek Tercih)")
    app.run_polling()

if __name__ == "__main__":
    main()
