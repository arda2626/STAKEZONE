# scheduler.py
import asyncio
from datetime import datetime, timedelta, timezone
import aiohttp
import os
import logging

from prediction import ai_for_match
from utils import utcnow, save_prediction, mark_prediction, get_pending_predictions, day_summary_between, build_live_text

# Logging ayarları
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# API key
THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY", "457761c3fe3072466a8899578fefc5e4")
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}"

# Ayarlar
MAX_LIVE_PICKS = 3
MIN_ODDS = 1.2
CHANNEL_ID = os.getenv("CHANNEL_ID", "YOUR_CHANNEL_ID")

# ----------------------- CANLI MAÇ -----------------------
async def hourly_live(ctx, matches):
    live_matches = [m for m in matches if m.get("live")][:MAX_LIVE_PICKS]
    predictions = [ai_for_match(m) for m in live_matches if m.get("odds", 0) >= MIN_ODDS]
    log.info(f"Hourly live predictions: {predictions}")
    for pred in predictions:
        if ctx and hasattr(ctx, "bot"):
            text = build_live_text([pred])
            sent = await ctx.bot.send_message(CHANNEL_ID, text, parse_mode="Markdown")
            save_prediction({**pred, "created_at": utcnow().isoformat(), "msg_id": sent.message_id})
    return predictions

# ----------------------- GÜNLÜK KUpon -----------------------
async def daily_coupon(ctx, matches):
    now = datetime.now(timezone.utc)
    upcoming = [m for m in matches if m.get("start_time") < now + timedelta(hours=24)]
    predictions = [ai_for_match(m) for m in upcoming]
    log.info(f"Daily coupon predictions: {predictions}")
    return predictions

# ----------------------- HAFTALIK KUpon -----------------------
async def weekly_coupon(ctx, matches):
    now = datetime.now(timezone.utc)
    upcoming = [m for m in matches if m.get("start_time") < now + timedelta(days=7)]
    predictions = [ai_for_match(m) for m in upcoming]
    log.info(f"Weekly coupon predictions: {predictions}")
    return predictions

# ----------------------- KASA KUpon -----------------------
async def kasa_coupon(ctx, matches):
    now = datetime.now(timezone.utc)
    upcoming = [m for m in matches if m.get("start_time") < now + timedelta(hours=48)]
    sorted_matches = sorted(upcoming, key=lambda x: x.get("confidence", 0), reverse=True)
    predictions = [ai_for_match(m) for m in sorted_matches[:3]]
    log.info(f"Kasa coupon predictions: {predictions}")
    return predictions

# ----------------------- MAÇ SONUÇLARI -----------------------
async def check_results(ctx):
    pending = get_pending_predictions()
    if not pending:
        return
    async with aiohttp.ClientSession() as session:
        for row in pending:
            pred_id, event_id, source, sport, league, home, away, bet_text, odds = row
            if not event_id:
                mark_prediction(pred_id, "unknown", "no_event")
                continue
            try:
                res = await session.get(f"{TSDB_BASE}/lookupevent.php?id={event_id}", timeout=12)
                if res.status != 200:
                    continue
                data = await res.json()
                events = data.get("events")
                if not events:
                    continue
                m = events[0]
                home_score = int(m.get("intHomeScore") or 0)
                away_score = int(m.get("intAwayScore") or 0)
                won = None
                bet_lower = (bet_text or "").lower()
                if "üst" in bet_lower:
                    import re
                    nums = re.findall(r"[\d\.]+", bet_text)
                    t = float(nums[-1]) if nums else 2.5
                    won = (home_score + away_score) > t
                elif "kg" in bet_lower:
                    won = home_score > 0 and away_score > 0
                elif "ev" in bet_lower:
                    won = home_score > away_score
                else:
                    won = None

                if won is True:
                    mark_prediction(pred_id, "won", f"{home_score}-{away_score}")
                elif won is False:
                    mark_prediction(pred_id, "lost", f"{home_score}-{away_score}")
                else:
                    mark_prediction(pred_id, "unknown", f"{home_score}-{away_score}")
            except Exception as e:
                log.debug(f"check_results lookup error: {e}")

# ----------------------- GÜNLÜK ÖZET -----------------------
async def daily_summary(ctx):
    now_tr = datetime.now(timezone.utc) + timedelta(hours=3)
    start_tr = now_tr.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = (start_tr - timedelta(hours=3)).isoformat()
    end_utc = (now_tr - timedelta(hours=3)).isoformat()
    rows = day_summary_between(start_utc, end_utc)
    counts = {"won":0,"lost":0,"pending":0,"unknown":0}
    for st,cnt in rows:
        counts[st] = cnt
    total = sum(counts.values())
    lines = [
        "═"*38,
        "📊 GÜNLÜK PERFORMANS ÖZETİ",
        f"📅 Tarih: {now_tr.strftime('%Y-%m-%d')}",
        "═"*38,
        f"Toplam tahmin: {total}",
        f"✅ Kazandı: {counts.get('won',0)}",
        f"❌ Kaybetti: {counts.get('lost',0)}",
        f"⏳ Değerlendirilemeyen: {counts.get('unknown',0)}",
        f"🕒 Hala beklemede: {counts.get('pending',0)}",
        "═"*38
    ]
    if ctx and hasattr(ctx, "bot"):
        await ctx.bot.send_message(CHANNEL_ID, "\n".join(lines), parse_mode="Markdown")
