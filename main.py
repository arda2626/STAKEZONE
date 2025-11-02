import os, asyncio, aiohttp, random
from telegram.ext import Application
from utils import utcnow, turkey_now, EMOJI, banner, league_to_flag
from db import init_db
from prediction import generate_prediction
from messages import format_match_message

# --- ENV VARS ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002284350528"))

# --- CANLI MAÇ ÇEKME (FUTBOL/BASKETBOL/TENİS) ---
async def fetch_live_matches(session, sport):
    """
    sport: 'football', 'basketball', 'tennis'
    """
    events = []
    try:
        if sport == "football":
            url = "https://v3.football.api-sports.io/fixtures?live=all"
            headers = {"x-apisports-key": os.getenv("API_FOOTBALL_KEY")}
        elif sport == "basketball":
            url = "https://v1.basketball.api-sports.io/games?live=all"
            headers = {"x-apisports-key": os.getenv("API_BASKETBALL_KEY")}
        elif sport == "tennis":
            url = "https://v1.tennis.api-sports.io/fixtures?status=LIVE"
            headers = {"x-apisports-key": os.getenv("API_TENNIS_KEY")}
        else:
            return []

        async with session.get(url, headers=headers, timeout=10) as r:
            res = await r.json()
            data = res.get("response", [])
            for e in data:
                events.append({
                    "league": e.get("league", {}).get("name") if sport!="tennis" else e.get("tournament", {}).get("name"),
                    "home_team": e.get("teams", {}).get("home", {}).get("name") if sport!="tennis" else e.get("players", {}).get("player1", {}).get("name"),
                    "away_team": e.get("teams", {}).get("away", {}).get("name") if sport!="tennis" else e.get("players", {}).get("player2", {}).get("name"),
                    "sport": sport,
                    "start_time": e.get("fixture", {}).get("date") if sport!="tennis" else e.get("time"),
                    "event_id": e.get("fixture", {}).get("id") if sport!="tennis" else e.get("fixture", {}).get("id"),
                })
    except Exception as ex:
        print(f"fetch_live_matches({sport}) error:", ex)
    return events

# --- CANLI TAHMİN VE GÖNDERME ---
async def hourly_live(app):
    async with aiohttp.ClientSession() as session:
        all_matches = []
        for sport in ["football", "basketball", "tennis"]:
            matches = await fetch_live_matches(session, sport)
            for m in matches:
                pred = generate_prediction(sport)
                m["prediction"] = pred["prediction"]
                m["odds"] = pred["odds"]
            all_matches.extend(matches)

        # Telegram’a gönder (max 3 maç)
        for match in all_matches[:3]:
            msg = format_match_message(match)
            try:
                await app.bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")
            except Exception as e:
                print("Telegram send error:", e)

# --- ANA ---
async def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    jq = app.job_queue

    # Her saat canlı kontrol
    jq.run_repeating(hourly_live, interval=3600, first=10, context=app)
    
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
