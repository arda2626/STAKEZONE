# odds.py
import aiohttp
import logging
from config import API_KEYS

log = logging.getLogger(__name__)

async def fetch_odds():
    odds_data = {}
    async with aiohttp.ClientSession() as session:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?regions=eu&apiKey={API_KEYS['THE_ODDS_API']}"
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if isinstance(data, list):
                    for m in data:
                        match_id = hash(str(m))
                        odds_data[match_id] = m.get("bookmakers", [{}])[0].get("markets", [])
                    log.info(f"✅ The Odds API: {len(data)} maç oranları çekildi")
                else:
                    log.warning("⚠️ The Odds API beklenmedik veri yapısı döndürdü")
        except Exception as e:
            log.warning(f"⚠️ The Odds API hata: {e}")
    return odds_data
