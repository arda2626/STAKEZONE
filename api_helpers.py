import aiohttp
from config import API_FOOTBALL_KEY, API_BASKETBALL_KEY, API_TENNIS_KEY

HEADERS = {
    "X-RapidAPI-Key": API_FOOTBALL_KEY,
    "X-RapidAPI-Host": "v3.football.api-sports.io"
}

async def fetch_football(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as resp:
            return await resp.json()

async def fetch_basketball(url):
    headers = {"X-RapidAPI-Key": API_BASKETBALL_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json()

async def fetch_tennis(url):
    headers = {"X-RapidAPI-Key": API_TENNIS_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json()
