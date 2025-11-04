# fetch_matches_free.py
import aiohttp
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# Tek fonksiyon: tüm kaynakları dener
async def fetch_all_matches():
    urls = {
        "theodds": "https://api.the-odds-api.com/v4/sports/soccer/odds/?regions=eu",
        "apifootball": "https://v3.football.api-sports.io/fixtures?live=all",
        "sportsmonks": "https://api.sportsmonks.com/v3/football/livescores",
    }

    all_matches = []

    async with aiohttp.ClientSession() as session:
        for name, url in urls.items():
            try:
                async with session.get(url, timeout=10) as resp:
                    data = await resp.json()

                    # Liste mi geldi sözlük mü kontrol et
                    if isinstance(data, list):
                        raw = data
                    elif isinstance(data, dict):
                        raw = data.get("data") or data.get("response") or []
                    else:
                        raw = []

                    # Standart forma çevir
                    for item in raw:
                        match = {
                            "id": item.get("id") or item.get("fixture", {}).get("id") or hash(str(item)),
                            "home": item.get("home_team") or item.get("teams", {}).get("home", {}).get("name") or item.get("home") or "Bilinmiyor",
                            "away": item.get("away_team") or item.get("teams", {}).get("away", {}).get("name") or item.get("away") or "Bilinmiyor",
                            "date": item.get("date") or item.get("fixture", {}).get("date") or datetime.utcnow().isoformat(),
                            "sport": "futbol",
                            "live": "live" in str(item).lower() or item.get("live") is True,
                            "home_country": "Türkiye",
                            "away_country": "Türkiye",
                        }
                        all_matches.append(match)

                    log.info(f"{name} API'den {len(raw)} maç alındı.")
            except Exception as e:
                log.warning(f"{name} API hata: {e}")

    if not all_matches:
        log.warning("Hiç maç alınamadı, dummy veri yükleniyor.")
        all_matches = [
            {"id": 1, "home": "Galatasaray", "away": "Fenerbahçe", "date": "2025-11-03T20:00:00Z", "sport": "futbol", "live": False},
            {"id": 2, "home": "Real Madrid", "away": "Barcelona", "date": "2025-11-03T17:30:00Z", "sport": "futbol", "live": True},
        ]

    return all_matches
