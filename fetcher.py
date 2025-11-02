# fetcher.py
import aiohttp
from config import THESPORTSDB_KEY
from utils import utcnow

TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"

async def fetch_live_events():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{TSDB_BASE}/eventslive.php", timeout=12) as r:
            if r.status == 200:
                return await r.json()
    return {}

async def fetch_events_next_league(league_id):
    # helper to get next events for a league id
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{TSDB_BASE}/eventsnextleague.php?id={league_id}", timeout=12) as r:
            if r.status == 200:
                return await r.json()
    return {}

async def lookup_event(event_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{TSDB_BASE}/lookupevent.php?id={event_id}", timeout=12) as r:
            if r.status == 200:
                return await r.json()
    return {}
