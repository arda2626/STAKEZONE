# fetch_matches.py
import aiohttp
import logging
from datetime import datetime
from config import API_KEYS

log = logging.getLogger(__name__)

async def fetch_all_matches():
    all_matches = []

    async with aiohttp.ClientSession() as session:
        # ---------- API-FOOTBALL ----------
        try:
            url = "https://v3.football.api-sports.io/fixtures?live=all"
            headers = {"x-apisports-key": API_KEYS["API_FOOTBALL"]}
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
                log.info(f"✅ API-Football: {len(fixtures)} maç çekildi")
        except Exception as e:
            log.warning(f"⚠️ API-Football hata: {e}")

        # ---------- iSPORTSAPI ----------
        try:
            url = f"https://api.isportsapi.com/sport/football/livescores?api_key={API_KEYS['ISPORTSAPI']}"
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
                log.info(f"✅ iSportsAPI: {len(matches)} maç çekildi")
        except Exception as e:
            log.warning(f"⚠️ iSportsAPI hata: {e}")

    if not all_matches:
        log.warning("❌ Hiç maç çekilemedi")
        return None

    log.info(f"🎯 Toplam çekilen maç: {len(all_matches)}")
    return all_matches
