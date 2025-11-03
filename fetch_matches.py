# ================== fetch_matches.py — STAKEDRIP AI ULTRA v5.1 ==================
import aiohttp
import logging

log = logging.getLogger("stakedrip")

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

SPORT_ENDPOINTS = {
    "football": f"{API_FOOTBALL_BASE}/fixtures?live=all",
    "basketball": "https://v1.basketball.api-sports.io/games?live=all",
    "tennis": "https://v1.tennis.api-sports.io/games?live=all"
}


# ============ FETCH CORE ============ #
async def fetch_api(session, url, api_key, sport):
    headers = {"x-apisports-key": api_key}
    async with session.get(url, headers=headers, timeout=15) as r:
        if r.status != 200:
            log.warning(f"{sport} fetch failed: {r.status}")
            return []
        data = await r.json()
        if not data or "response" not in data:
            return []
        matches = []

        for item in data["response"]:
            try:
                if sport == "football":
                    fixture = item.get("fixture", {})
                    teams = item.get("teams", {})
                    league = item.get("league", {})

                    matches.append({
                        "id": fixture.get("id"),
                        "sport": "football",
                        "league": league.get("name", "Bilinmeyen Lig"),
                        "country": league.get("country", ""),
                        "home": teams.get("home", {}).get("name", "?"),
                        "away": teams.get("away", {}).get("name", "?"),
                        "minute": fixture.get("status", {}).get("elapsed"),
                        "odds": 1.5,
                        "live": True,
                    })

                elif sport == "basketball":
                    game = item.get("game", {})
                    teams = item.get("teams", {})
                    league = item.get("league", {})

                    matches.append({
                        "id": game.get("id"),
                        "sport": "basketball",
                        "league": league.get("name", "Basketbol Ligi"),
                        "country": league.get("country", ""),
                        "home": teams.get("home", {}).get("name", "?"),
                        "away": teams.get("away", {}).get("name", "?"),
                        "minute": None,
                        "odds": 1.6,
                        "live": True,
                    })

                elif sport == "tennis":
                    tournament = item.get("tournament", {})
                    event = item.get("event", {})
                    matches.append({
                        "id": event.get("id"),
                        "sport": "tennis",
                        "league": tournament.get("name", "Tenis Turnuvası"),
                        "country": tournament.get("country", ""),
                        "home": event.get("home", "?"),
                        "away": event.get("away", "?"),
                        "minute": None,
                        "odds": 1.7,
                        "live": True,
                    })

            except Exception as e:
                log.warning(f"{sport} parse error: {e}")
        return matches


# ============ MAIN FETCH FUNCTION ============ #
async def fetch_all_matches(api_key: str):
    async with aiohttp.ClientSession() as session:
        all_matches = []
        for sport, url in SPORT_ENDPOINTS.items():
            try:
                matches = await fetch_api(session, url, api_key, sport)
                all_matches.extend(matches)
                log.info(f"Fetched {len(matches)} {sport} matches.")
            except Exception as e:
                log.error(f"{sport} fetch_all_matches error: {e}")
        return all_matches
