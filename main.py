# main.py
import asyncio
import random
import aiohttp
from datetime import datetime, timedelta
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === Environment Variables (Railway'de ekle) ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")
CHANNEL = os.getenv("CHANNEL", "@ai_tahmin_kanali")  # Varsayılan

# API-Sports (Futbol, Basketbol, Tenis)
SPORTS = {
    "football": {
        "name": "Futbol",
        "url": "https://v3.football.api-sports.io",
        "league": 140  # Süper Lig (39=Premier Lig, 61=La Liga)
    },
    "basketball": {
        "name": "Basketbol",
        "url": "https://v3.basketball.api-sports.io",
        "league": 12  # NBA
    },
    "tennis": {
        "name": "Tenis",
        "url": "https://v3.tennis.api-sports.io",
        "league": 1  # ATP
    }
}

HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"  # Futbol varsayılan
}

# AI Tahmin (Poisson + Basit Olasılık)
def ai_predict(home_goals=1.6, away_goals=1.2):
    total = home_goals + away_goals
    p_home = home_goals / total if total > 0 else 0.4
    p_draw = 0.25
    p_away = 1 - p_home - p_draw

    result = "1" if p_home > 0.45 else "X" if p_draw > 0.35 else "2"
    over25 = total > 2.5
    kg = (home_goals > 0.8 and away_goals > 0.8)

    oran = round(max(p_home, p_away, p_draw) * 2.8 + random.uniform(-0.3, 0.4), 2)
    return {
        "1X2": result,
        "AltUst": "Üst 2.5" if over25 else "Alt 2.5",
        "KG": "KG Var" if kg else "KG Yok",
        "Oran": oran
    }

# 24 saatlik maçları çek
async def get_matches(sport_key="football", hours=24):
    sport = SPORTS[sport_key]
    url = f"{sport['url']}/fixtures"
    params = {
        "league": sport["league"],
        "season": datetime.now().year,
        "from": datetime.now().strftime("%Y-%m-%d"),
        "to": (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d"),
        "timezone": "Europe/Istanbul"
    }
    headers = HEADERS.copy()
    headers["x-rapidapi-host"] = sport["url"].split("://")[1].split("/")[0]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", [])
    except Exception as e:
        print(f"API Hatası ({sport_key}): {e}")
    return []

# Saatlik Tahmin
async def hourly_prediction(context: ContextTypes.DEFAULT_TYPE):
    sport = random.choice(["football", "basketball"])
    matches = await get_matches(sport, 3)
    if not matches:
        return
    match = random.choice(matches)
    home = match['teams']['home']['name']
    away = match['teams']['away']['name']
    pred = ai_predict(1.7, 1.3)

    msg = f"**{datetime.now().strftime('%H:%M')} CANLI TAHMİN**\n\n" \
          f"**{home} vs {away}**\n" \
          f"**{pred['1X2']}** | {pred['AltUst']} | {pred['KG']}\n" \
          f"Oran: **{pred['Oran']}** (AI)"
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

# Günlük Kupon
async def daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    matches = []
    for sport in ["football", "basketball"]:
        ms = await get_matches(sport, 24)
        if ms:
            matches.extend(ms[:2])

    if len(matches) < 2:
        return

    selected = random.sample(matches, 2)
    lines = []
    total_odds = 1.0
    for m in selected:
        home = m['teams']['home']['name']
        away = m['teams']['away']['name']
        pred = ai_predict(1.8, 1.4)
        total_odds *= pred["Oran"]
        lines.append(f"**{home} vs {away}**\n{pred['1X2']} @ {pred['Oran']}")

    msg = f"**GÜNLÜK KUP
