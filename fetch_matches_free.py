# fetch_matches_free.py — Güvenli fetch
import aiohttp
import logging
from datetime import datetime, timezone

log = logging.getLogger("stakedrip")

# ================== API CONFIG ==================
FOOTBALL_API_KEY = "70b1ee7a9db547649988d3898503771d"  # Football-Data.org
BASKETBALL_API = "https://www.balldontlie.io/api/v1/games"
TENNIS_API = "https://www.scorebat.com/video-api/v3/"

# ================== FETCH FUNCTIONS ==================
async def fetch_football(session):
    url = f"https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    try:
        async with session.get(url, headers=headers, timeout=15) as r:
            if r.status != 200:
                log.warning(f"football fetch failed: {r.status}")
                return []
            data = await r.json()
            matches = []
            for m in data.get("matches", []):
                match_time = m.get("utcDate")
                if match_time:
                    dt = datetime.fromisoformat(match_time.replace("Z", "+00:00"))
                    matches.append({
                        "id": m.get("id"),
                        "sport": "football",
                        "home": m.get("homeTeam", {}).get("name", "Unknown"),
                        "away": m.get("awayTeam", {}).get("name", "Unknown"),
                        "league": m.get("competition", {}).get("name", "Bilinmeyen Lig"),
                        "country": m.get("competition", {}).get("area", {}).get("name", ""),
                        "odds": 1.5,
                        "confidence": 0.5,
                        "date": dt.isoformat(),
                        "live": False,
                    })
            return matches
    except Exception as e:
        log.error(f"football fetch exception: {e}")
        return []

async def fetch_basketball(session):
    try:
        async with session.get(BASKETBALL_API, timeout=15) as r:
            if r.status != 200:
                log.warning(f"basketball fetch failed: {r.status}")
                return []
            data = await r.json()
            matches = []
            for m in data.get("data", []):
                try:
                    dt = datetime.fromisoformat(m.get("date") + "Z")
                    matches.append({
                        "id": m.get("id"),
                        "sport": "basketball",
                        "home": m.get("home_team", {}).get("full_name", "Unknown"),
                        "away": m.get("visitor_team", {}).get("full_name", "Unknown"),
                        "league": "NBA",
                        "country": "USA",
                        "odds": 1.6,
                        "confidence": 0.5,
                        "date": dt.isoformat(),
                        "live": False,
                    })
                except Exception as e_inner:
                    log.warning(f"Skipping basketball match due to parse error: {e_inner}")
            return matches
    except Exception as e:
        log.error(f"basketball fetch exception: {e}")
        return []

async def fetch_tennis(session):
    try:
        async with session.get(TENNIS_API, timeout=15) as r:
            if r.status != 200:
                log.warning(f"tennis fetch failed: {r.status}")
                return []
            data = await r.json()
            matches = []
            for m in data.get("response", []):
                try:
                    event = m.get("title", "").split(" vs ")
                    if len(event) != 2:
                        continue
                    matches.append({
                        "id": m.get("id"),
                        "sport": "tennis",
                        "home": event[0],
                        "away": event[1],
                        "league": m.get("competition", {}).get("name", "Tenis Turnuvası"),
                        "country": "",
                        "odds": 1.7,
                        "confidence": 0.5,
                        "date": datetime.now(timezone.utc).isoformat(),
                        "live": False,
                    })
                except Exception as e_inner:
                    log.warning(f"Skipping tennis match due to parse error: {e_inner}")
            return matches
    except Exception as e:
        log.error(f"tennis fetch exception: {e}")
        return []

# ================== MAIN FETCH FUNCTION ==================
async def fetch_all_matches():
    async with aiohttp.ClientSession() as session:
        football = await fetch_football(session)
        basketball = await fetch_basketball(session)
        tennis = await fetch_tennis(session)
        all_matches = football + basketball + tennis
        log.info(f"Fetched {len(football)} football, {len(basketball)} basketball, {len(tennis)} tennis matches.")
        return all_matches
