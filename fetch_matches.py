# fetch_matches.py
# Primary: API-Football (live & upcoming). Fallback: TheSportsDB (limited).
import aiohttp
import logging
from datetime import datetime, timezone
from typing import List, Dict
from config import API_FOOTBALL_KEY, THESPORTSDB_KEY
from utils import utcnow

log = logging.getLogger(__name__)

AF_BASE = "https://v3.football.api-sports.io"
AF_HEADERS = {"x-apisports-key": API_FOOTBALL_KEY} if API_FOOTBALL_KEY else None
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}" if THESPORTSDB_KEY else None

async def _fetch_api_football_live() -> List[Dict]:
    if not API_FOOTBALL_KEY:
        return []
    url = AF_BASE + "/fixtures"
    params = {"live":"all"}
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(url, headers=AF_HEADERS, params=params, timeout=15) as r:
                if r.status != 200:
                    log.debug(f"AF live status {r.status}")
                    return []
                data = await r.json()
                res = data.get("response", [])
                matches = []
                for f in res:
                    fixture = f.get("fixture",{})
                    teams = f.get("teams",{})
                    matches.append({
                        "id": fixture.get("id"),
                        "league": f.get("league",{}).get("name"),
                        "home": teams.get("home",{}).get("name"),
                        "away": teams.get("away",{}).get("name"),
                        "sport": "futbol",
                        "live": True,
                        "minute": fixture.get("status",{}).get("elapsed"),
                        "start_time": datetime.fromisoformat(fixture.get("date").replace("Z","+00:00")) if fixture.get("date") else utcnow(),
                        "raw": f
                    })
                return matches
        except Exception as e:
            log.debug(f"_fetch_api_football_live error: {e}")
            return []

async def _fetch_tsdb_live() -> List[Dict]:
    if not TSDB_BASE:
        return []
    url = f"{TSDB_BASE}/eventslive.php"
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(url, timeout=12) as r:
                if r.status != 200:
                    log.debug("TSDB live status %s", r.status)
                    return []
                data = await r.json()
                events = data.get("event") or []
                matches = []
                for e in events:
                    matches.append({
                        "id": e.get("idEvent"),
                        "league": e.get("strLeague"),
                        "home": e.get("strHomeTeam"),
                        "away": e.get("strAwayTeam"),
                        "sport": (e.get("strSport") or "Soccer").lower(),
                        "live": True,
                        "minute": e.get("intRound") or e.get("strTime"),
                        "start_time": utcnow(),
                        "raw": e
                    })
                return matches
        except Exception as e:
            log.debug(f"_fetch_tsdb_live error: {e}")
            return []

async def fetch_all_matches(api_key: str = None) -> List[Dict]:
    """
    Returns combined list: live matches (football from API-Football preferred, fallback to TSDB),
    plus a limited set of upcoming football fixtures from API-Football (next 24h) where possible.
    """
    matches = []
    # live football from API-Football
    try:
        af = await _fetch_api_football_live()
        if af:
            matches.extend(af)
        else:
            # fallback
            ts = await _fetch_tsdb_live()
            matches.extend(ts)
    except Exception as e:
        log.debug(f"fetch_all_matches error: {e}")
    # upcoming (API-Football next day) - best effort
    if API_FOOTBALL_KEY:
        try:
            async with aiohttp.ClientSession() as s:
                url = AF_BASE + "/fixtures"
                params = {"from": datetime.now(timezone.utc).date().isoformat(), "to": (datetime.now(timezone.utc).date()).isoformat(), "next": 50}
                async with s.get(url, headers=AF_HEADERS, params=params, timeout=15) as r:
                    if r.status == 200:
                        data = await r.json()
                        for f in data.get("response",[]):
                            fixture = f.get("fixture", {})
                            teams = f.get("teams", {})
                            matches.append({
                                "id": fixture.get("id"),
                                "league": f.get("league",{}).get("name"),
                                "home": teams.get("home",{}).get("name"),
                                "away": teams.get("away",{}).get("name"),
                                "sport": "futbol",
                                "live": False,
                                "start_time": datetime.fromisoformat(fixture.get("date").replace("Z","+00:00")) if fixture.get("date") else utcnow(),
                                "raw": f
                            })
        except Exception as e:
            log.debug(f"fetch_all_matches upcoming error: {e}")
    return matches
