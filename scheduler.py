import asyncio
import datetime
from datetime import datetime, timezone, timedelta
import aiohttp
import os
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY", "457761c3fe3072466a8899578fefc5e4")
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"

import logging
from prediction import ai_for_match

# Logging ayarları
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def hourly_live(matches):
    live_matches = [m for m in matches if m.get("live")][:3]
    predictions = [ai_for_match(m) for m in live_matches if m.get("odds", 0) >= 1.2]
    log.info(f"Hourly live predictions: {predictions}")
    return predictions

async def daily_coupon(matches):
    upcoming = [m for m in matches if m.get("start_time") < datetime.datetime.utcnow() + datetime.timedelta(hours=24)]
    predictions = [ai_for_match(m) for m in upcoming]
    log.info(f"Daily coupon predictions: {predictions}")
    return predictions

async def weekly_coupon(matches):
    upcoming = [m for m in matches if m.get("start_time") < datetime.datetime.utcnow() + datetime.timedelta(days=7)]
    predictions = [ai_for_match(m) for m in upcoming]
    log.info(f"Weekly coupon predictions: {predictions}")
    return predictions

async def kasa_coupon(matches):
    upcoming = [m for m in matches if m.get("start_time") < datetime.datetime.utcnow() + datetime.timedelta(hours=48)]
    sorted_matches = sorted(upcoming, key=lambda x: x.get("confidence", 0), reverse=True)
    predictions = [ai_for_match(m) for m in sorted_matches[:3]]
    log.info(f"Kasa coupon predictions: {predictions}")
    return predictions

async def check_results(matches):
    finished = [m for m in matches if m.get("finished")]
    log.info(f"Finished matches: {finished}")
    return finished

async def daily_summary(predictions):
    summary = {
        "tahmin_sayısı": len(predictions),
        "ortalama_güven": sum(p["confidence"] for p in predictions)/len(predictions) if predictions else 0
    }
    log.info(f"Daily summary: {summary}")
    return summary
    
log = logging.getLogger(__name__)

TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"

async def hourly_live(ctx):
    async with aiohttp.ClientSession() as session:
        try:
            data = await fetch_live_events()
            events = data.get("event") if data else []
            candidates = []
            if events:
                for e in events:
                    ev = {
                        "id": e.get("idEvent"),
                        "sport": (e.get("strSport") or "").lower(),
                        "league": e.get("strLeague"),
                        "home": e.get("strHomeTeam"),
                        "away": e.get("strAwayTeam"),
                        "minute": e.get("intRound") or e.get("strTime") or None
                    }
                    pred = ai_for_match(ev)
                    if pred and pred["odds"] >= MIN_ODDS:
                        pred["minute"] = ev.get("minute")
                        candidates.append(pred)
            # unique filter by league+home+away
            uniq = {}
            for c in candidates:
                key = f"{(c.get('league') or '').lower()}|{(c.get('home') or '').lower()}|{(c.get('away') or '').lower()}"
                if key not in uniq or (c.get("prob",0) > uniq[key].get("prob",0)):
                    uniq[key] = c
            candidates = list(uniq.values())
            if not candidates:
                log.info("hourly_live: uygun canlı aday (istatistik yok ya da filtre) bulunamadı — sessiz geçiliyor")
                return
            selected = sorted(candidates, key=lambda x: x["prob"], reverse=True)[:MAX_LIVE_PICKS]
            text = build_live_text(selected)
            sent = await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="Markdown")
            for p in selected:
                save_prediction({**p, "created_at": utcnow().isoformat(), "msg_id": sent.message_id})
            log.info(f"{len(selected)} canlı tahmin gönderildi")
        except Exception as e:
            log.debug(f"hourly_live error: {e}")

async def daily_coupon(ctx):
    async with aiohttp.ClientSession() as session:
        try:
            # get upcoming events via league endpoints could be heavy; use generic search of next 24h using eventsnextleague or search
            # Simplified: use eventslive for live and eventsnext/lookup by popular leagues is left for expandability
            # For now: fetch upcoming by searching next 24h via many leagues is not available in single call; best-effort: use eventslive + some next endpoints
            # We'll create a fallback that picks non-live events from last 48h and filters by start time (approx)
            # NOTE: This is a best-effort implementation because TheSportsDB doesn't provide a global "next 24h" in one call.
            resp = await session.get(f"{TSDB_BASE}/eventslive.php", timeout=12)
            data = await resp.json() if resp.status == 200 else {}
            events = data.get("event", []) if data else []
            picks = []
            # also attempt popular leagues next events if you want (not implemented exhaustive)
            for e in events:
                # prefer upcoming (non-live) not present in live results; skip if already live
                continue
            # As a fallback, we will not produce if no reliable 24h upcoming list found
            # In practice user should configure league-specific calls (eventsnextleague.php?id=LEAGUEID) for richer daily picks.
            log.info("daily_coupon: event fetch fallback - no global next24h available, sessiz geçiliyor")
            return
        except Exception as e:
            log.debug(f"daily_coupon error: {e}")

async def weekly_coupon(ctx):
    # Similar note: for robust weekly coupon, call league-specific endpoints; here we attempt a placeholder
    log.info("weekly_coupon: placeholder - implement league-specific upcoming fetch for weekly kupon")

async def kasa_coupon(ctx):
    # Kasa: try to find highest confidence upcoming within 48h via league-specific endpoints
    log.info("kasa_coupon: placeholder - implement league-specific upcoming fetch for kasa kupon")

async def check_results(ctx):
    pending = get_pending_predictions()
    if not pending:
        return
    async with aiohttp.ClientSession() as session:
        for row in pending:
            pred_id, event_id, source, sport, league, home, away, bet_text, odds = row
            resolved = False
            if event_id:
                try:
                    res = await session.get(f"{TSDB_BASE}/lookupevent.php?id={event_id}", timeout=12)
                    if res.status == 200:
                        data = await res.json()
                        events = data.get("events")
                        if events:
                            m = events[0]
                            status = (m.get("strStatus") or "").lower()
                            # check finished
                            if any(k in status for k in ["ft","full time","finished","final"]) or m.get("intHomeScore") is not None:
                                # attempt simple eval for some bets
                                home_score = m.get("intHomeScore")
                                away_score = m.get("intAwayScore")
                                # simple rules
                                if "üst" in (bet_text or "").lower():
                                    import re
                                    nums = re.findall(r"[\d\.]+", bet_text); t = float(nums[-1]) if nums else 2.5
                                    won = (int(home_score or 0) + int(away_score or 0)) > t
                                elif "kg" in (bet_text or "").lower():
                                    won = (int(home_score or 0)>0 and int(away_score or 0)>0)
                                elif "ev sahibi" in (bet_text or "").lower() or "ev" in (bet_text or "").lower():
                                    won = int(home_score or 0) > int(away_score or 0)
                                else:
                                    won = None
                                if won is True:
                                    mark_prediction(pred_id, "won", f"{home_score}-{away_score}")
                                    await ctx.bot.send_message(CHANNEL_ID, f"✅ KAZANDI • {bet_text} • {home} {home_score} - {away_score} {away}")
                                    resolved=True
                                elif won is False:
                                    mark_prediction(pred_id, "lost", f"{home_score}-{away_score}")
                                    await ctx.bot.send_message(CHANNEL_ID, f"❌ KAYBETTİ • {bet_text} • {home} {home_score} - {away_score} {away}")
                                    resolved=True
                                else:
                                    mark_prediction(pred_id, "unknown", f"{home_score}-{away_score}")
                                    await ctx.bot.send_message(CHANNEL_ID, f"⏳ DEĞERLENDİRME GEREKİYOR • {bet_text} • {home} - {away}")
                                    resolved=True
                except Exception as e:
                    log.debug(f"check_results lookup error: {e}")
            else:
                mark_prediction(pred_id, "unknown", "no_event")

async def daily_summary(ctx):
    now_tr = datetime.now(timedelta(hours=3))
    start_tr = now_tr.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = (start_tr - timedelta(hours=3)).isoformat()
    end_utc = (now_tr - timedelta(hours=3)).isoformat()
    rows = day_summary_between(start_utc, end_utc)
    counts = {"won":0,"lost":0,"pending":0,"unknown":0}
    for st,cnt in rows:
        counts[st] = cnt
    total = sum(counts.values())
    lines = ["═"*38, "📊 GÜNLÜK PERFORMANS ÖZETİ", f"📅 Tarih: {now_tr.strftime('%Y-%m-%d')}", "═"*38,
             f"Toplam tahmin: {total}", f"✅ Kazandı: {counts.get('won',0)}", f"❌ Kaybetti: {counts.get('lost',0)}",
             f"⏳ Değerlendirilemeyen: {counts.get('unknown',0)}", f"🕒 Hala beklemede: {counts.get('pending',0)}", "═"*38]
    await ctx.bot.send_message(CHANNEL_ID, "\n".join(lines), parse_mode="Markdown")
