# fetch_matches.py
import aiohttp
import logging
from datetime import datetime, timedelta
from config import API_KEYS, TIME_DELTA

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
                    date_utc = fix.get("date", datetime.utcnow().isoformat())
                    try:
                        date = datetime.fromisoformat(date_utc.replace("Z","")).replace(tzinfo=None) + timedelta(hours=TIME_DELTA)
                        date_str = date.strftime("%H:%M")
                    except:
                        date_str = "Bilinmiyor"
                    all_matches.append({
                        "id": fix.get("id", hash(f"{home}-{away}-{date_str}")),
                        "home": home,
                        "away": away,
                        "date": date_str,
                        "sport": "futbol",
                        "live": fix.get("status", {}).get("short", "") not in ("NS", "FT"),
                        "odds": f.get("odds", {}),
                        "home_country": "Global",
                        "away_country": "Global",
                    })
                log.info(f"✅ API-Football'dan {len(fixtures)} maç çekildi.")
        except Exception as e:
            log.warning(f"⚠️ API-Football hata: {e}")

        # ---------- iSPORTSAPI ----------
        try:
            url = f"https://api.isportsapi.com/sport/football/livescores?api_key={API_KEYS['ISPORTSAPI']}"
            async with session.get(url, timeout=10, ssl=False) as resp:
                data = await resp.json()
                matches = data.get("data", [])
                for m in matches:
                    date_utc = m.get("matchTime", datetime.utcnow().isoformat())
                    try:
                        date = datetime.fromisoformat(date_utc.replace("Z","")).replace(tzinfo=None) + timedelta(hours=TIME_DELTA)
                        date_str = date.strftime("%H:%M")
                    except:
                        date_str = "Bilinmiyor"
                    all_matches.append({
                        "id": m.get("matchId", hash(str(m))),
                        "home": m.get("homeTeamName", "Bilinmiyor"),
                        "away": m.get("awayTeamName", "Bilinmiyor"),
                        "date": date_str,
                        "sport": "futbol",
                        "live": True,
                        "odds": m.get("odds", {}),
                        "home_country": "Global",
                        "away_country": "Global",
                    })
                log.info(f"✅ iSportsAPI'den {len(matches)} maç çekildi.")
        except Exception as e:
            log.warning(f"⚠️ iSportsAPI hata: {e}")

    if not all_matches:
        log.warning("❌ Hiçbir API veri döndürmedi — kupon iptal.")
        return None

    log.info(f"🎯 Toplam çekilen maç: {len(all_matches)}")
    return all_matches
