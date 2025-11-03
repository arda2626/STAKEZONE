# fetch_matches.py
import aiohttp
import os
from datetime import datetime, timezone, timedelta

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "<d2e6d7d3d4826877927ded6da40e278e>")
ALLSPORTSAPI_KEY = "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369"
url = f"https://api.allsportsapi.com/football/live?key={ALLSPORTSAPI_KEY}"

async def fetch_football_matches():
    url = f"https://v3.football.api-sports.io/fixtures?next=50"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            fixtures = data.get("response", [])
            matches = []
            for f in fixtures:
                m = {
                    "id": f["fixture"]["id"],
                    "league": f["league"]["name"],
                    "home": f["teams"]["home"]["name"],
                    "away": f["teams"]["away"]["name"],
                    "sport": "futbol",
                    "live": f["fixture"]["status"]["short"] in ["1H","2H"],
                    "odds": f.get("odds", {}).get("home_win", 1.2),
                    "confidence": 0.7,
                    "start_time": datetime.fromisoformat(f["fixture"]["date"].replace("Z","+00:00"))
                }
                matches.append(m)
            return matches

async def fetch_nba_matches():
    url = f"{TSDB_BASE}/livescore.php?s=Basketball"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            events = data.get("event", [])
            matches = []
            for e in events:
                m = {
                    "id": e.get("idEvent"),
                    "league": e.get("strLeague"),
                    "home": e.get("strHomeTeam"),
                    "away": e.get("strAwayTeam"),
                    "sport": "nba",
                    "live": True,
                    "odds": 1.2,
                    "confidence": 0.7,
                    "start_time": datetime.utcnow().replace(tzinfo=timezone.utc)
                }
                matches.append(m)
            return matches

async def fetch_tennis_matches():
    url = f"{TSDB_BASE}/livescore.php?s=Tennis"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            events = data.get("event", [])
            matches = []
            for e in events:
                m = {
                    "id": e.get("idEvent"),
                    "league": e.get("strLeague"),
                    "home": e.get("strHomeTeam"),
                    "away": e.get("strAwayTeam"),
                    "sport": "tenis",
                    "live": True,
                    "odds": 1.2,
                    "confidence": 0.7,
                    "start_time": datetime.utcnow().replace(tzinfo=timezone.utc)
                }
                matches.append(m)
            return matches

async def fetch_all_matches():
    football = await fetch_football_matches()
    nba = await fetch_nba_matches()
    tennis = await fetch_tennis_matches()
    return football + nba + tennis
