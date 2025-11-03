# fetch_matches.py
import aiohttp
from datetime import datetime, timezone
from utils import utcnow, ensure_min_odds
import os

API_FOOTBALL_KEY = "3838237ec41218c2572ce541708edcfd"  # Buraya API-Football keyini yaz
BASE_FOOTBALL_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_FOOTBALL_KEY
}

async def fetch_football_matches():
    url = f"{BASE_FOOTBALL_URL}/fixtures?live=all"
    matches = []
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=HEADERS, timeout=10) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                fixtures = data.get("response", [])
                for f in fixtures:
                    fixture = f["fixture"]
                    teams = f["teams"]
                    league = f["league"]["name"]
                    home = teams["home"]["name"]
                    away = teams["away"]["name"]
                    odds = ensure_min_odds(f.get("odds", {}).get("home_win", 1.2))
                    matches.append({
                        "id": fixture["id"],
                        "league": league,
                        "home": home,
                        "away": away,
                        "sport": "futbol",
                        "live": fixture["status"]["short"] in ["1H","2H","LIVE"],
                        "odds": odds,
                        "confidence": 0.7,
                        "start_time": datetime.fromisoformat(fixture["date"].replace("Z","+00:00"))
                    })
        except Exception as e:
            print(f"fetch_football_matches error: {e}")
    return matches

# Basketbol ve tenis API-Football tarafından resmi olarak desteklenmiyor
# Ancak istersen dummy canlı endpointleri veya başka API kullanabilirsin
# Aşağıda placeholder olarak bırakıyorum

async def fetch_nba_matches():
    # placeholder: kendi API veya TSDB kullanabilirsin
    return []

async def fetch_tennis_matches():
    # placeholder: kendi API veya TSDB kullanabilirsin
    return []

async def fetch_all_matches():
    football = await fetch_football_matches()
    nba = await fetch_nba_matches()
    tennis = await fetch_tennis_matches()
    return football + nba + tennis
