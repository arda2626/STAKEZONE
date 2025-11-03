import aiohttp
import logging

log = logging.getLogger("stakedrip")

# ================== API KEYS ==================
API_FOOTBALL_KEY = "3838237ec41218c2572ce541708edcfd"
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"
THE_ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"

SPORT_ENDPOINTS = {
    "football": f"{API_FOOTBALL_BASE}/fixtures?live=all",
    "basketball": "https://v1.basketball.api-sports.io/games?live=all",
    "tennis": "https://v1.tennis.api-sports.io/games?live=all"
}

# ================== FETCH CORE ==================
async def fetch_api(session, url, api_key, sport):
    headers = {"x-apisports-key": api_key} if sport != "theodds" else {}
    try:
        async with session.get(url, headers=headers, timeout=15) as r:
            if r.status != 200:
                log.warning(f"{sport} fetch failed: {r.status}")
                return []
            data = await r.json()
            if not data:
                return []

            matches = []
            for item in data.get("response", data):
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
                    elif sport == "theodds":
                        matches.append({
                            "id": item.get("id"),
                            "sport": "football",
                            "league": item.get("league", "Bilinmeyen Lig"),
                            "country": item.get("home_team_country", ""),
                            "home": item.get("home_team", "?"),
                            "away": item.get("away_team", "?"),
                            "minute": None,
                            "odds": 1.5,
                            "live": True,
                        })
                except Exception as e:
                    log.warning(f"{sport} parse error: {e}")
            return matches
    except Exception as e:
        log.error(f"{sport} fetch_api exception: {e}")
        return []

# ================== MAIN FETCH FUNCTION ==================
async def fetch_all_matches():
    async with aiohttp.ClientSession() as session:
        all_matches = []

        # 1️⃣ Futbol
        football_matches = await fetch_api(session, SPORT_ENDPOINTS["football"], API_FOOTBALL_KEY, "football")
        log.info(f"Fetched {len(football_matches)} football matches from API-Football.")

        if not football_matches:
            url = f"{THE_ODDS_API_BASE}/soccer/odds/?apiKey={THE_ODDS_API_KEY}&regions=all&markets=h2h,totals,spreads"
            football_matches = await fetch_api(session, url, THE_ODDS_API_KEY, "theodds")
            log.info(f"Fetched {len(football_matches)} football matches from The Odds API (fallback).")
        all_matches.extend(football_matches)

        # 2️⃣ Basketbol ve Tenis
        for sport in ["basketball", "tennis"]:
            matches = await fetch_api(session, SPORT_ENDPOINTS[sport], API_FOOTBALL_KEY, sport)
            all_matches.extend(matches)
            log.info(f"Fetched {len(matches)} {sport} matches.")

        return all_matches
