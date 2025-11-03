# ================== fetch_matches.py — STAKEDRIP AI ULTRA v5.2 ==================
import aiohttp
import logging

log = logging.getLogger("stakedrip")

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

SPORT_ENDPOINTS = {
    "football": f"{API_FOOTBALL_BASE}/fixtures?live=all",
    "basketball": "https://v1.basketball.api-sports.io/games?live=all",
    "tennis": "https://v1.tennis.api-sports.io/games?live=all"
}

# ---------- THESPORTSDB URL ----------
THESPORTSDB_FOOTBALL = "https://www.thesportsdb.com/api/v1/json/1/eventsnextleague.php?id=4328"  # Örnek Premier League


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


# ---------- THESPORTSDB FETCH ----------
async def fetch_thesportsdb(session):
    async with session.get(THESPORTSDB_FOOTBALL, timeout=15) as r:
        if r.status != 200:
            log.warning(f"TheSportsDB fetch failed: {r.status}")
            return []
        data = await r.json()
        matches = []
        for item in data.get("events", []):
            matches.append({
                "id": item.get("idEvent"),
                "sport": "football",
                "league": item.get("strLeague"),
                "country": item.get("strCountry"),
                "home": item.get("strHomeTeam"),
                "away": item.get("strAwayTeam"),
                "minute": None,
                "odds": 1.5,
                "live": False,
            })
        log.info(f"Fetched {len(matches)} football matches from TheSportsDB")
        return matches


# ============ MAIN FETCH FUNCTION ============ #
async def fetch_all_matches(api_key: str):
    async with aiohttp.ClientSession() as session:
        all_matches = []

        # ---------- ÖNCELİK: API-FOOTBALL ----------
        try:
            football_matches = await fetch_api(session, SPORT_ENDPOINTS["football"], api_key, "football")
            if football_matches:
                all_matches.extend(football_matches)
            else:
                raise ValueError("API-Football veri yok")
        except Exception as e:
            log.warning(f"API-Football çekilemedi: {e}, TheSportsDB den çekilecek...")
            try:
                thesports_matches = await fetch_thesportsdb(session)
                all_matches.extend(thesports_matches)
            except Exception as e2:
                log.error(f"TheSportsDB de çekilemedi: {e2}")

        # ---------- Basketbol ve Tenis ----------
        for sport in ["basketball", "tennis"]:
            try:
                matches = await fetch_api(session, SPORT_ENDPOINTS[sport], api_key, sport)
                all_matches.extend(matches)
                log.info(f"Fetched {len(matches)} {sport} matches.")
            except Exception as e:
                log.error(f"{sport} fetch_all_matches error: {e}")

        return all_matches
