import aiohttp
import logging
from datetime import datetime
from config import API_FOOTBALL_KEY, THE_ODDS_API_KEY, FOOTYSTATS_KEY, ALLSPORTSAPI_KEY, SPORTSMONKS_KEY, ISPORTSAPI_KEY

log = logging.getLogger(__name__)

async def fetch_all_matches():
    all_matches = []

    async with aiohttp.ClientSession() as session:
        # ---------- API-FOOTBALL ----------
        try:
            url = "https://v3.football.api-sports.io/fixtures?live=all"
            headers = {"x-apisports-key": API_FOOTBALL_KEY}
            async with session.get(url, headers=headers, timeout=10) as resp:
                data = await resp.json()
                fixtures = data.get("response", [])
                for f in fixtures:
                    fix = f.get("fixture", {})
                    teams = f.get("teams", {})
                    home = teams.get("home", {}).get("name", "Bilinmiyor")
                    away = teams.get("away", {}).get("name", "Bilinmiyor")
                    date = fix.get("date", datetime.utcnow().isoformat())
                    all_matches.append({
                        "id": fix.get("id", hash(f"{home}-{away}-{date}")),
                        "home": home,
                        "away": away,
                        "date": date,
                        "sport": "futbol",
                        "live": fix.get("status", {}).get("short", "") not in ("NS", "FT"),
                        "home_country": "Global",
                        "away_country": "Global",
                    })
                log.info(f"✅ API-Football'dan {len(fixtures)} maç çekildi.")
        except Exception as e:
            log.warning(f"⚠️ API-Football hata: {e}")

        # ---------- THE ODDS API ----------
        try:
            url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?regions=eu&apiKey={THE_ODDS_API_KEY}"
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if isinstance(data, list):
                    for m in data:
                        home = m.get("home_team", "Bilinmiyor")
                        away = m.get("away_team", "Bilinmiyor")
                        commence_time = m.get("commence_time", datetime.utcnow().isoformat())
                        all_matches.append({
                            "id": hash(str(m)),
                            "home": home,
                            "away": away,
                            "date": commence_time,
                            "sport": "futbol",
                            "live": False,
                            "home_country": "Global",
                            "away_country": "Global",
                            "odds": m.get("bookmakers", [])
                        })
                    log.info(f"✅ The Odds API'den {len(data)} maç çekildi.")
                else:
                    log.warning("⚠️ The Odds API beklenmedik veri döndürdü.")
        except Exception as e:
            log.warning(f"⚠️ The Odds API hata: {e}")

        # ---------- FOOTYSTATS ----------
        try:
            url = f"https://api.footystats.org/live-scores?key={FOOTYSTATS_KEY}"
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                matches = data.get("data", [])
                for m in matches:
                    all_matches.append({
                        "id": m.get("id", hash(m.get("home_name", ""))),
                        "home": m.get("home_name", "Bilinmiyor"),
                        "away": m.get("away_name", "Bilinmiyor"),
                        "date": m.get("match_start_iso", datetime.utcnow().isoformat()),
                        "sport": "futbol",
                        "live": True,
                        "home_country": m.get("country", "Global"),
                        "away_country": m.get("country", "Global"),
                    })
                log.info(f"✅ FootyStats API'den {len(matches)} maç çekildi.")
        except Exception as e:
            log.warning(f"⚠️ FootyStats hata: {e}")

        # ---------- ALLSPORTSAPI ----------
        try:
            url = f"https://allsportsapi2.p.rapidapi.com/api/football/matches/live"
            headers = {
                "x-rapidapi-host": "allsportsapi2.p.rapidapi.com",
                "x-rapidapi-key": ALLSPORTSAPI_KEY
            }
            async with session.get(url, headers=headers, timeout=10) as resp:
                data = await resp.json()
                matches = data.get("result", [])
                for m in matches:
                    all_matches.append({
                        "id": m.get("event_key", hash(m.get("event_home_team", ""))),
                        "home": m.get("event_home_team", "Bilinmiyor"),
                        "away": m.get("event_away_team", "Bilinmiyor"),
                        "date": m.get("event_date_start", datetime.utcnow().isoformat()),
                        "sport": "futbol",
                        "live": True,
                        "home_country": "Global",
                        "away_country": "Global",
                    })
                log.info(f"✅ AllSportsAPI'den {len(matches)} maç çekildi.")
        except Exception as e:
            log.warning(f"⚠️ AllSportsAPI hata: {e}")

        # ---------- SPORTSMONKS ----------
        try:
            url = f"https://api.sportsmonks.com/v3/football/livescores?api_token={SPORTSMONKS_KEY}"
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                matches = data.get("data", [])
                for m in matches:
                    home = m.get("home_name", "Bilinmiyor")
                    away = m.get("away_name", "Bilinmiyor")
                    all_matches.append({
                        "id": m.get("id", hash(home+away)),
                        "home": home,
                        "away": away,
                        "date": m.get("starting_at", datetime.utcnow().isoformat()),
                        "sport": "futbol",
                        "live": True,
                        "home_country": "Global",
                        "away_country": "Global",
                    })
                log.info(f"✅ SportsMonks'tan {len(matches)} maç çekildi.")
        except Exception as e:
            log.warning(f"⚠️ SportsMonks hata: {e}")

        # ---------- iSPORTSAPI ----------
        try:
            url = f"https://api.isportsapi.com/sport/football/livescores?api_key={ISPORTSAPI_KEY}"
            async with session.get(url, timeout=10, ssl=False) as resp:
                data = await resp.json()
                matches = data.get("data", [])
                for m in matches:
                    all_matches.append({
                        "id": m.get("matchId", hash(str(m))),
                        "home": m.get("homeTeamName", "Bilinmiyor"),
                        "away": m.get("awayTeamName", "Bilinmiyor"),
                        "date": m.get("matchTime", datetime.utcnow().isoformat()),
                        "sport": "futbol",
                        "live": True,
                        "home_country": "Global",
                        "away_country": "Global",
                    })
                log.info(f"✅ iSportsAPI'den {len(matches)} maç çekildi.")
        except Exception as e:
            log.warning(f"⚠️ iSportsAPI hata: {e}")

    if not all_matches:
        log.warning("❌ Hiçbir API veri döndürmedi.")
        return None

    log.info(f"🎯 Toplam çekilen maç: {len(all_matches)}")
    return all_matches
