# ================== fetch_matches_free.py — STAKEDRIP AI ULTRA v5.6 ==================
import aiohttp
import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger("stakedrip")

# ================== API KEYS ==================
API_FOOTBALL_KEY = "70b1ee7a9db547649988d3898503771d"  # Football-Data.org
BASKETBALL_BASE = "https://www.balldontlie.io/api/v1/games"  # Ücretsiz NBA
# Tenis için örnek ücretsiz kaynak: https://www.scorebat.com/video-api/v3/

# ================== FETCH CORE ==================
async def fetch_football(session):
    url = "https://api.football-data.org/v4/matches?status=SCHEDULED"
    headers = {"X-Auth-Token": API_FOOTBALL_KEY}
    matches = []
    try:
        async with session.get(url, headers=headers, timeout=15) as r:
            if r.status != 200:
                log.warning(f"football fetch failed: {r.status}")
                return []
            data = await r.json()
            for m in data.get("matches", []):
                match_time = datetime.fromisoformat(m["utcDate"].replace("Z","+00:00"))
                # Sadece 24 saat içindeki maçlar
                if match_time <= datetime.now(timezone.utc) + timedelta(hours=24):
                    matches.append({
                        "id": m["id"],
                        "sport": "football",
                        "league": m["competition"]["name"],
                        "home": m["homeTeam"]["name"],
                        "away": m["awayTeam"]["name"],
                        "date": match_time.isoformat(),
                        "odds": 1.5,
                        "live": False
                    })
        log.info(f"Fetched {len(matches)} football matches from Football-Data.org.")
        return matches
    except Exception as e:
        log.error(f"football fetch_api exception: {e}")
        return []

async def fetch_basketball(session):
    # Sadece bugün ve yarınki maçları çekelim
    start = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"{BASKETBALL_BASE}?start_date={start}&end_date={end}"
    matches = []
    try:
        async with session.get(url, timeout=15) as r:
            if r.status != 200:
                log.warning(f"basketball fetch failed: {r.status}")
                return []
            data = await r.json()
            for m in data.get("data", []):
                matches.append({
                    "id": m["id"],
                    "sport": "basketball",
                    "league": "NBA",
                    "home": m["home_team"]["full_name"],
                    "away": m["visitor_team"]["full_name"],
                    "date": m["date"],
                    "odds": 1.6,
                    "live": False
                })
        log.info(f"Fetched {len(matches)} basketball matches from balldontlie.io.")
        return matches
    except Exception as e:
        log.error(f"basketball fetch_api exception: {e}")
        return []

async def fetch_tennis(session):
    # Tenis için Scorebat video API ücretsiz
    url = "https://www.scorebat.com/video-api/v3/feed/"
    matches = []
    try:
        async with session.get(url, timeout=15) as r:
            if r.status != 200:
                log.warning(f"tennis fetch failed: {r.status}")
                return []
            data = await r.json()
            for m in data.get("response", []):
                if "tennis" in m.get("competition", "").lower():
                    matches.append({
                        "id": m.get("id"),
                        "sport": "tennis",
                        "league": m.get("competition"),
                        "home": m.get("title", "?").split(" vs ")[0],
                        "away": m.get("title", "?").split(" vs ")[-1],
                        "date": m.get("date"),
                        "odds": 1.7,
                        "live": False
                    })
        log.info(f"Fetched {len(matches)} tennis matches from Scorebat API.")
        return matches
    except Exception as e:
        log.error(f"tennis fetch_api exception: {e}")
        return []

# ================== MAIN FETCH FUNCTION ==================
async def fetch_all_matches():
    async with aiohttp.ClientSession() as session:
        all_matches = []
        football_matches = await fetch_football(session)
        all_matches.extend(football_matches)

        basketball_matches = await fetch_basketball(session)
        all_matches.extend(basketball_matches)

        tennis_matches = await fetch_tennis(session)
        all_matches.extend(tennis_matches)

        return all_matches
