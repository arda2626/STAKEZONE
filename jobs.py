from predictions import make_prediction
from api_helpers import fetch_football
import asyncio

async def hourly_live(context=None):
    matches = await fetch_football("https://api-football-v1.p.rapidapi.com/v3/fixtures?live=all")
    for m in matches.get("response", []):
        pred = {
            "event_id": str(m["fixture"]["id"]),
            "sport": "futbol",
            "league": m["league"]["name"],
            "home": m["teams"]["home"]["name"],
            "away": m["teams"]["away"]["name"],
            "bet": "KG",  # örnek
            "odds": 1.25,
            "prob": 70
        }
        await make_prediction(pred)

# gunluk_kupon, haftalik_kupon, kasa_kuponu, daily_summary için benzer yapı
