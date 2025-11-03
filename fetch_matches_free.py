# ================== fetch_matches_free.py ==================
import aiohttp
import logging
from datetime import datetime, timezone

log = logging.getLogger("stakedrip")

# ================== API KEYS / BASE URLS ==================
FOOTBALL_DATA_KEY = "70b1ee7a9db547649988d3898503771d"
FOOTBALL_BASE = "https://api.football-data.org/v4"

BASKETBALL_BASE = "https://www.balldontlie.io/api/v1/games"
TENNIS_BASE = "https://www.scorebat.com/video-api/v3/"

# ================== FETCH FUNCTIONS ==================
async def fetch_football():
    url = f"{FOOTBALL_BASE}/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as r:
                if r.status != 200:
                    log.warning(f"football fetch failed: {r.status}")
                    return []
                data = await r.json()
                matches = []
                for m in data.get("matches", []):
                    match_time = m.get("utcDate")
                    matches.append({
                        "id": m.get("id"),
                        "sport": "football",
                        "league": m.get("competition", {}).get("name", "Bilinmeyen Lig"),
                        "home": m.get("homeTeam", {}).get("name", "?"),
                        "away": m.get("awayTeam", {}).get("name", "?"),
                        "date": match_time,
                        "odds": 1.5,
                        "live": False
                    })
                return matches
    except Exception as e:
        log.error(f"football fetch exception: {e}")
        return []

async def fetch_basketball():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BASKETBALL_BASE, timeout=15) as r:
                if r.status != 200:
                    log.warning(f"basketball fetch failed: {r.status}")
                    return []
                data = await r.json()
                matches = []
                for m in data.get("data", []):
                    match_time = m.get("date")
                    matches.append({
                        "id": m.get("id"),
                        "sport": "basketball",
                        "league": "NBA",
                        "home": m.get("home_team", {}).get("full_name", "?"),
                        "away": m.get("visitor_team", {}).get("full_name", "?"),
                        "date": match_time,
                        "odds": 1.5,
                        "live": False
                    })
                return matches
    except Exception as e:
        log.error(f"basketball fetch exception: {e}")
        return []

async def fetch_tennis():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(TENNIS_BASE, timeout=15) as r:
                if r.status != 200:
                    log.warning(f"tennis fetch failed: {r.status}")
                    return []
                data = await r.json()
                matches = []
                for m in data.get("response", []):
                    matches.append({
                        "id": m.get("title"),
                        "sport": "tennis",
                        "league": m.get("competition", "Tenis Turnuvası"),
                        "home": m.get("side1", "?"),
                        "away": m.get("side2", "?"),
                        "date": m.get("date"),
                        "odds": 1.5,
                        "live": False
                    })
                return matches
    except Exception as e:
        log.error(f"tennis fetch exception: {e}")
        return []

# ================== MAIN FETCH FUNCTION ==================
async def fetch_all_matches():
    football = await fetch_football()
    basketball = await fetch_basketball()
    tennis = await fetch_tennis()
    all_matches = football + basketball + tennis
    log.info(f"Fetched {len(football)} football, {len(basketball)} basketball, {len(tennis)} tennis matches.")
    return all_matches
