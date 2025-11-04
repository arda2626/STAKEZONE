# fetch_matches_free.py
import aiohttp
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# Sabit API key'ler (değiştirme)
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2"
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6"
FOOTYSTATS_KEY = "test85g57"
ALLSPORTSAPI_KEY = "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369"
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ"
ISPORTSAPI_KEY = "rCiLp0QXNSrfV5oc"

async def fetch_all_matches():
    all_matches = []

    async with aiohttp.ClientSession() as session:
        # API-Football
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
                    })
                log.info(f"✅ API-Football'dan {len(fixtures)} maç çekildi.")
        except Exception as e:
            log.warning(f"⚠️ API-Football hata: {e}")

        # iSportsAPI (örnek)
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
                    })
                log.info(f"✅ iSportsAPI'den {len(matches)} maç çekildi.")
        except Exception as e:
            log.warning(f"⚠️ iSportsAPI hata: {e}")

    log.info(f"🎯 Toplam çekilen maç: {len(all_matches)}")
    return all_matches
