# ================== fetch_matches.py — STAKEDRIP AI ULTRA v5.0 ==================
import aiohttp
import logging
from datetime import datetime, timezone

log = logging.getLogger("stakedrip")

API_BASE = "https://v3.football.api-sports.io"

HEADERS_TEMPLATE = lambda key: {
    "x-rapidapi-host": "v3.football.api-sports.io",
    "x-rapidapi-key": key
}

async def fetch_api(url, key):
    try:
        async with aiohttp.ClientSession(headers=HEADERS_TEMPLATE(key)) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    log.warning(f"⚠️ API response {resp.status}: {await resp.text()}")
                    return []
                data = await resp.json()
                return data.get("response", [])
    except Exception as e:
        log.error(f"fetch_api error: {e}")
        return []

async def fetch_live_football(key):
    url = f"{API_BASE}/fixtures?live=all"
    data = await fetch_api(url, key)
    matches = []
    for m in data:
        try:
            matches.append({
                "sport": "football",
                "league": m["league"]["name"],
                "home": m["teams"]["home"]["name"],
                "away": m["teams"]["away"]["name"],
                "score": f"{m['goals']['home']}-{m['goals']['away']}",
                "minute": m.get("fixture", {}).get("status", {}).get("elapsed", 0),
                "live": True
            })
        except Exception:
            continue
    return matches

async def fetch_live_basketball(key):
    # Basketball endpoint
    url = "https://v1.basketball.api-sports.io/games?live=all"
    data = await fetch_api(url, key)
    matches = []
    for g in data:
        try:
            matches.append({
                "sport": "basketball",
                "league": g["league"]["name"],
                "home": g["teams"]["home"]["name"],
                "away": g["teams"]["away"]["name"],
                "score": f"{g['scores']['home']['total']}-{g['scores']['away']['total']}",
                "quarter": g["status"]["short"],
                "live": True
            })
        except Exception:
            continue
    return matches

async def fetch_live_tennis(key):
    # Tennis endpoint
    url = "https://v1.tennis.api-sports.io/matches?live=all"
    data = await fetch_api(url, key)
    matches = []
    for t in data:
        try:
            matches.append({
                "sport": "tennis",
                "league": t["tournament"]["name"],
                "home": t["teams"]["home"]["name"],
                "away": t["teams"]["away"]["name"],
                "score": f"{t['scores']['home']['sets']}-{t['scores']['away']['sets']}",
                "live": True
            })
        except Exception:
            continue
    return matches

async def fetch_all_matches(key):
    football = await fetch_live_football(key)
    basketball = await fetch_live_basketball(key)
    tennis = await fetch_live_tennis(key)
    all_matches = football + basketball + tennis
    log.info(f"Fetched {len(all_matches)} total live matches.")
    return all_matches
