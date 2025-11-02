# stakedrip_full.py
import asyncio
import datetime
from datetime import datetime, timezone, timedelta
import aiohttp
import os
import logging
from random import uniform

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY", "457761c3fe3072466a8899578fefc5e4")
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"

MIN_ODDS = 1.2
MAX_LIVE_PICKS = 3

# ---------------- UTILS ----------------
def utcnow(): return datetime.now(timezone.utc)
def turkey_now(): return datetime.now(timezone(timedelta(hours=3)))

# ---------------- AI PREDICTION ----------------
def ai_for_match(match):
    home_form = sum(match.get("form_home",[0.7,0.7,0.7])) / max(len(match.get("form_home",[1])),1)
    away_form = sum(match.get("form_away",[0.7,0.7,0.7])) / max(len(match.get("form_away",[1])),1)
    base_prob = 0.5 + (home_form - away_form)/4
    base_prob = min(max(base_prob,0.05),0.95)
    odds = match.get("odds", 1.5)
    confidence = base_prob * (odds/2)
    return {
        "id": match.get("id"),
        "home": match.get("home"),
        "away": match.get("away"),
        "sport": match.get("sport"),
        "prob": round(base_prob,2),
        "confidence": round(confidence,2),
        "odds": odds,
        "start_time": match.get("start_time")
    }

# ---------------- FETCH MATCHES ----------------
async def fetch_matches(sport="Soccer", league_id=None):
    async with aiohttp.ClientSession() as session:
        url = f"{TSDB_BASE}/eventsnextleague.php?id={league_id}" if league_id else f"{TSDB_BASE}/livescore.php?s={sport}"
        try:
            resp = await session.get(url, timeout=15)
            if resp.status != 200:
                log.warning(f"fetch_matches {sport} status={resp.status}")
                return []
            data = await resp.json()
            events = data.get("events") or data.get("event") or []
            matches = []
            for e in events:
                matches.append({
                    "id": e.get("idEvent"),
                    "home": e.get("strHomeTeam"),
                    "away": e.get("strAwayTeam"),
                    "sport": sport.lower(),
                    "odds": uniform(1.2,2.0),  # dummy odds, TheSportsDB free version doesn't provide odds
                    "confidence": 0,
                    "live": e.get("strStatus","").lower() in ["live","in progress"],
                    "start_time": datetime.strptime(e.get("dateEvent","") + " " + (e.get("strTime","12:00:00")), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) if e.get("dateEvent") else utcnow(),
                    "form_home":[uniform(0.5,1) for _ in range(3)],
                    "form_away":[uniform(0.5,1) for _ in range(3)]
                })
            return matches
        except Exception as e:
            log.debug(f"fetch_matches error: {e}")
            return []

# ---------------- PREDICTION FUNCTIONS ----------------
async def hourly_live(matches):
    live_matches = [m for m in matches if m.get("live")][:MAX_LIVE_PICKS]
    predictions = [ai_for_match(m) for m in live_matches if m.get("odds", 0) >= MIN_ODDS]
    log.info(f"Hourly live predictions: {predictions}")
    return predictions

async def daily_coupon(matches):
    upcoming = [m for m in matches if m.get("start_time") < utcnow() + timedelta(hours=24)]
    predictions = [ai_for_match(m) for m in upcoming]
    log.info(f"Daily coupon predictions: {predictions}")
    return predictions

async def weekly_coupon(matches):
    upcoming = [m for m in matches if m.get("start_time") < utcnow() + timedelta(days=7)]
    predictions = [ai_for_match(m) for m in upcoming]
    log.info(f"Weekly coupon predictions: {predictions}")
    return predictions

async def kasa_coupon(matches):
    upcoming = [m for m in matches if m.get("start_time") < utcnow() + timedelta(hours=48)]
    sorted_matches = sorted(upcoming, key=lambda x: x.get("confidence",0), reverse=True)
    predictions = [ai_for_match(m) for m in sorted_matches[:3]]
    log.info(f"Kasa coupon predictions: {predictions}")
    return predictions

# ---------------- MAIN ----------------
async def main():
    # Futbol: Süper Lig, Premier, La Liga, Serie A, Bundesliga
    football_leagues = ["4328","4329","4335","4332","4331"]  # TSDB league IDs (example)
    nba_league = ["4387"]
    tennis_sports = ["Tennis"]  # no league IDs

    matches = []

    for lid in football_leagues:
        matches += await fetch_matches("Soccer", lid)
    for lid in nba_league:
        matches += await fetch_matches("Basketball", lid)
    for sport in tennis_sports:
        matches += await fetch_matches("Tennis")

    print("Hourly Live Predictions:")
    print(await hourly_live(matches))

    print("\nDaily Coupon Predictions:")
    print(await daily_coupon(matches))

    print("\nWeekly Coupon Predictions:")
    print(await weekly_coupon(matches))

    print("\nKasa Coupon Predictions:")
    print(await kasa_coupon(matches))

if __name__ == "__main__":
    asyncio.run(main())
