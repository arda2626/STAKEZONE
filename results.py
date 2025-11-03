# results.py
# Minimal results checker using API-Football or TSDB lookups (best-effort).
import aiohttp
import logging
from utils import utcnow
from config import API_FOOTBALL_KEY, THESPORTSDB_KEY, DB_PATH
from utils import mark_prediction, get_pending_predictions, day_summary_between
from datetime import datetime, timezone

log = logging.getLogger(__name__)
AF_BASE = "https://v3.football.api-sports.io"
AF_HEADERS = {"x-apisports-key": API_FOOTBALL_KEY} if API_FOOTBALL_KEY else None
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}" if THESPORTSDB_KEY else None

async def check_results(bot=None):
    pending = get_pending_predictions(DB_PATH)
    if not pending:
        return
    async with aiohttp.ClientSession() as s:
        for row in pending:
            pred_id, event_id, source, sport, league, home, away, bet_text, odds = row
            resolved = False
            # Try API-Football first
            try:
                if AF_HEADERS and event_id:
                    url = AF_BASE + "/fixtures"
                    params = {"id": int(event_id)}
                    async with s.get(url, headers=AF_HEADERS, params=params, timeout=12) as r:
                        if r.status == 200:
                            data = await r.json()
                            if data.get("response"):
                                m = data["response"][0]
                                status = m.get("fixture",{}).get("status",{}).get("short","").lower()
                                if status in ("ft","aet","pen"):
                                    # evaluate simple rules
                                    goals = m.get("goals",{})
                                    gh = goals.get("home"); ga = goals.get("away")
                                    total = (gh or 0) + (ga or 0)
                                    bt = (bet_text or "").lower()
                                    if "üst" in bt:
                                        import re
                                        nums = re.findall(r"[\d\.]+", bt); t = float(nums[-1]) if nums else 2.5
                                        won = total > t
                                    elif "kg" in bt:
                                        won = (gh or 0) > 0 and (ga or 0) > 0
                                    elif "ev" in bt or "home" in bt:
                                        won = (gh or 0) > (ga or 0)
                                    else:
                                        won = None
                                    if won is True:
                                        mark_prediction(DB_PATH, pred_id, "won", f"{gh}-{ga}")
                                        if bot: await bot.send_message(CHANNEL_ID, f"✅ KAZANDI • {bet_text} • {home} {gh} - {ga} {away}")
                                    elif won is False:
                                        mark_prediction(DB_PATH, pred_id, "lost", f"{gh}-{ga}")
                                        if bot: await bot.send_message(CHANNEL_ID, f"❌ KAYBETTİ • {bet_text} • {home} {gh} - {ga} {away}")
                                    else:
                                        mark_prediction(DB_PATH, pred_id, "unknown", f"{gh}-{ga}")
                                    resolved = True
                if resolved: continue
            except Exception as e:
                log.debug(f"results api-football lookup error: {e}")

            # fallback to TSDB
            try:
                if TSDB_BASE and event_id:
                    async with s.get(f"{TSDB_BASE}/lookupevent.php?id={event_id}", timeout=12) as r:
                        if r.status == 200:
                            data = await r.json()
                            events = data.get("events")
                            if events:
                                m = events[0]
                                home_score = int(m.get("intHomeScore") or 0)
                                away_score = int(m.get("intAwayScore") or 0)
                                bt = (bet_text or "").lower()
                                if "üst" in bt:
                                    import re
                                    nums = re.findall(r"[\d\.]+", bt); t = float(nums[-1]) if nums else 2.5
                                    won = (home_score + away_score) > t
                                elif "kg" in bt:
                                    won = home_score > 0 and away_score > 0
                                elif "ev" in bt:
                                    won = home_score > away_score
                                else:
                                    won = None
                                if won is True:
                                    mark_prediction(DB_PATH, pred_id, "won", f"{home_score}-{away_score}")
                                elif won is False:
                                    mark_prediction(DB_PATH, pred_id, "lost", f"{home_score}-{away_score}")
                                else:
                                    mark_prediction(DB_PATH, pred_id, "unknown", f"{home_score}-{away_score}")
                                resolved = True
                if resolved: continue
            except Exception as e:
                log.debug(f"results tsdb lookup error: {e}")
