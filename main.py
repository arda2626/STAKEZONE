# main.py - KATEGORİYE GÖRE EMOJI + RENKLİ + CANLI AYRI
import asyncio
import random
import aiohttp
import logging
from datetime import datetime, timedelta, time, timezone
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
    logger.error("HATA: ODDS_API_KEY eksik!")
    exit(1)

# ====================== SPOR KODLARI ======================
SPORTS = {
    "football": ["soccer_turkey_super_league", "soccer_epl", "soccer_spain_la_liga"],
    "basketball": ["basketball_nba", "basketball_euroleague"],
    "tennis": ["tennis_atp_singles"]
}

# ====================== EMOJI HARİTASI ======================
EMOJI = {
    "football": "Football",
    "basketball": "Basketball",
    "tennis": "Tennis",
    "live": "Fire",
    "upcoming": "Briefcase",
    "daily": "Ticket",
    "weekly": "Gem"
}

# ====================== ZAMAN (GMT+3) ======================
def get_time_info(match):
    try:
        dt = datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00"))
        dt_ist = dt.astimezone(timezone(timedelta(hours=3)))
        time_str = dt_ist.strftime("%H:%M")
    except:
        time_str = "??:??"

    now = datetime.now(timezone.utc)
    if dt <= now <= dt + timedelta(minutes=120):
        mins = int((now - dt).total_seconds() // 60)
        return f"`{mins}'` {EMOJI['live']}"
    else:
        return f"`{time_str}` {EMOJI['upcoming']}"

# ====================== API ======================
async def fetch_odds(sport: str):
    matches = []
    for code in SPORTS.get(sport, []):
        url = f"https://api.the-odds-api.com/v4/sports/{code}/odds"
        params = {"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "h2h,totals", "oddsFormat": "decimal"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for game in data:
                            game["sport"] = sport
                            game["league"] = game.get("sport_nice", code.split("_")[-1].title())
                            matches.append(game)
        except Exception as e:
            logger.error(f"{code} hatası: {e}")
    return matches

# ====================== TAHMİN ======================
def get_best_bet(match):
    book = match.get("bookmakers", [{}])[0]
    h2h = next((m for m in book.get("markets", []) if m["key"] == "h2h"), None)
    if not h2h: return None

    o = h2h["outcomes"]
    home = next((x for x in o if x["name"] == match["home_team"]), None)
    away = next((x for x in o if x["name"] == match["away_team"]), None)
    draw = next((x for x in o if x["name"] == "Draw"), None)

    p_home = 1 / home["price"] if home else 0
    p_away = 1 / away["price"] if away else 0
    p_draw = 1 / draw["price"] if draw else 0

    totals = next((m for m in book.get("markets", []) if m["key"] == "totals"), None)
    p_over = p_under = 0
    if totals:
        over = next((x for x in totals["outcomes"] if "Over" in x["name"]), None)
        under = next((x for x in totals["outcomes"] if "Under" in x["name"]), None)
        p_over = 1 / over["price"] if over else 0
        p_under = 1 / under["price"] if under else 0

    p_kg_var = 0.6 if p_home > 0.3 and p_away >
