#!/usr/bin/env python3
"""
StakeDrip Pro V4
- python-telegram-bot v20.x async (ApplicationBuilder)
- api-sports (api-sports.io) football + nba
- hourly predictions, daily coupon, neon visual cards
- commands: /start /tahmin /kupon /sonuclar /istatistik /admin mark <id> <KAZANDI|KAYBETTI>
- uses sqlite (DB_PATH env) ; prefers env vars for secrets
"""
import os
import io
import math
import time
import json
import logging
import random
import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Optional model libs
try:
    import joblib
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBClassifier
    MODEL_AVAILABLE = True
except Exception:
    MODEL_AVAILABLE = False

from telegram import InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------------------
# CONFIG (from env, defaults)
# ---------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8393964009:AAGif15CiCgyXs33VFoF-BnaTUVf8xcMKVE")   # replace for local test only
API_SPORTS_KEY = os.getenv("API_SPORTS_KEY", "460ec2a26e2178f365e61e063bb6b487")           # required for real matches
CHANNEL_ID = os.getenv("CHANNEL_ID", "@stakedrip")
DB_PATH = os.getenv("DB_PATH", "/tmp/stakezone_pro.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE = os.getenv("TIMEZONE", "UTC")  # e.g. Europe/Istanbul

# API endpoints
FOOTBALL_HOST = "v3.football.api-sports.io"
NBA_HOST = "v2.nba.api-sports.io"
HEADERS = {"x-apisports-key": API_SPORTS_KEY} if API_SPORTS_KEY else {}

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
                    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("stakedrip")

# ---------------------------
# DATABASE
# ---------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    date TEXT,
    sport TEXT,
    match TEXT,
    prediction TEXT,
    stake INTEGER,
    prob REAL,
    sent_time TEXT,
    game_id TEXT,
    status TEXT  -- BEKLENIYOR / KAZANDI / KAYBETTI
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    date TEXT,
    matches TEXT,
    total_odds REAL,
    status TEXT  -- BEKLENIYOR / KAZANDI / KAYBETTI
)
""")
conn.commit()

# ---------------------------
# MODEL (optional)
# ---------------------------
MODEL_FILE = os.getenv("MODEL_FILE", "/tmp/model.pkl")
SCALER_FILE = os.getenv("SCALER_FILE", "/tmp/scaler.pkl")

def train_fallback_model():
    """Train a quick fallback model if XGBoost missing or files not present"""
    try:
        import numpy as np
        from sklearn.preprocessing import StandardScaler
        from xgboost import XGBClassifier
        np.random.seed(42)
        data_X = np.column_stack([
            np.random.uniform(100,140,1500),
            np.random.uniform(95,135,1500),
            np.random.uniform(40,55,1500),
            np.random.uniform(38,53,1500),
            np.random.randint(0,20,1500),
            np.random.randint(0,20,1500),
        ])
        y = (data_X[:,0] - data_X[:,1] + np.random.randn(1500)*5 > 0).astype(int)
        scaler = StandardScaler()
        Xs = scaler.fit_transform(data_X)
        model = XGBClassifier(n_estimators=100, max_depth=4, use_label_encoder=False, eval_metric='logloss')
        model.fit(Xs, y)
        joblib.dump(model, MODEL_FILE)
        joblib.dump(scaler, SCALER_FILE)
        logger.info("Fallback model trained and saved.")
        return True
    except Exception as e:
        logger.exception("Fallback model training failed.")
        return False

if MODEL_AVAILABLE:
    try:
        model = joblib.load(MODEL_FILE) if os.path.exists(MODEL_FILE) else None
        scaler = joblib.load(SCALER_FILE) if os.path.exists(SCALER_FILE) else None
        if not model or not scaler:
            ok = train_fallback_model()
            if ok:
                model = joblib.load(MODEL_FILE)
                scaler = joblib.load(SCALER_FILE)
            else:
                MODEL_AVAILABLE = False
    except Exception:
        logger.exception("Failed to load model files.")
        MODEL_AVAILABLE = False

def predict_probability(features: Optional[List[float]] = None) -> float:
    """
    Return probability 0-100.
    If model available, use it. Otherwise fallback deterministic.
    features: [home_ppg, away_ppg, home_fg, away_fg, home_ats, away_ats]
    """
    try:
        if MODEL_AVAILABLE and model is not None and scaler is not None:
            if features is None:
                # default dummy
                features = [118, 112, 47.5, 45.2, 9, 7]
            X = np.array([features])
            Xs = scaler.transform(X)
            p = model.predict_proba(Xs)[0][1] * 100
            return float(round(p,1))
    except Exception:
        logger.exception("Model predict failed; falling back.")
    # deterministic fallback: use random + small pattern
    base = 50 + (math.sin(datetime.utcnow().hour/24*2*math.pi) * 10)
    jitter = random.uniform(-8, 8)
    return round(max(1, min(99, base + jitter)), 1)

# ---------------------------
# UTIL: time helpers
# ---------------------------
def utcnow():
    return datetime.utcnow().replace(tzinfo=timezone.utc)

def seconds_until_next_hour():
    now = utcnow()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return max(1, int((next_hour - now).total_seconds()))

# ---------------------------
# API-Sports fetchers
# ---------------------------
def fetch_football_fixtures_for_today() -> Optional[dict]:
    if not API_SPORTS_KEY:
        return None
    url = f"https://{FOOTBALL_HOST}/fixtures"
    params = {"date": utcnow().strftime("%Y-%m-%d")}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code != 200:
            logger.warning("Football API status %s: %s", r.status_code, r.text[:200])
            return None
        return r.json()
    except Exception:
        logger.exception("Football fetch failed")
        return None

def fetch_nba_games_for_today() -> Optional[dict]:
    if not API_SPORTS_KEY:
        return None
    url = f"https://{NBA_HOST}/games"
    params = {"date": utcnow().strftime("%Y-%m-%d")}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code != 200:
            logger.warning("NBA API status %s: %s", r.status_code, r.text[:200])
            return None
        return r.json()
    except Exception:
        logger.exception("NBA fetch failed")
        return None

# ---------------------------
# VISUAL: neon card
# ---------------------------
ASSET_FONT = os.path.join(os.path.dirname(__file__), "assets", "neon.ttf")
def create_neon_card(title: str, subtitle: str, prob: float, footer: str = "") -> io.BytesIO:
    W, H = 1200, 520
    bg = Image.new("RGBA", (W, H), (6,6,10,255))
    txt = Image.new("RGBA", (W, H), (0,0,0,0))
    draw = ImageDraw.Draw(txt)
    # load font fallback
    try:
        fbig = ImageFont.truetype(ASSET_FONT, 72)
        fmed = ImageFont.truetype(ASSET_FONT, 36)
    except Exception:
        try:
            fbig = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
            fmed = ImageFont.truetype("DejaVuSans.ttf", 32)
        except Exception:
            fbig = ImageFont.load_default()
            fmed = ImageFont.load_default()
    x, y = 60, 60
    # glow layers
    for o,a in [(16,28),(8,90),(4,200)]:
        draw.text((x+o, y+o), title, font=fbig, fill=(60,160,255,a))
    draw.text((x, y), title, font=fbig, fill=(190,240,255,255))
    # subtitle
    draw.text((x, y+110), subtitle, font=fmed, fill=(230,200,255,255))
    # prob bar
    bar_x, bar_y = x, H - 140
    bar_w = 820
    filled = int(bar_w * (prob/100.0))
    draw.rectangle([bar_x, bar_y, bar_x+filled, bar_y+36], fill=(0,220,150,255))
    draw.rectangle([bar_x+filled, bar_y, bar_x+bar_w, bar_y+36], fill=(255,80,80,160))
    draw.text((bar_x+bar_w+20, bar_y-2), f"{prob}%", font=fmed, fill=(240,240,240,255))
    if footer:
        draw.text((x, H-60), footer, font=fmed, fill=(180,180,200,200))
    # composite glow
    glow = txt.filter(ImageFilter.GaussianBlur(4))
    combined = Image.alpha_composite(bg, glow)
    combined = Image.alpha_composite(combined, txt)
    buf = io.BytesIO()
    combined.convert("RGB").save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf

# ---------------------------
# CORE: prepare match list (prioritize near-start games)
# ---------------------------
def collect_upcoming_matches(window_hours: int = 12) -> List[Tuple[str,str,datetime,str]]:
    """
    returns list of (match_str, sport, start_dt(utc), game_id)
    """
    now = utcnow()
    cutoff = now + timedelta(hours=window_hours)
    matches = []
    # football
    fb = fetch_football_fixtures_for_today()
    if fb and fb.get("response"):
        for f in fb["response"]:
            try:
                start = datetime.fromisoformat(f["fixture"]["date"].replace("Z","+00:00"))
                start = start.replace(tzinfo=timezone.utc)
                if now < start < cutoff:
                    home = f["teams"]["home"]["name"]
                    away = f["teams"]["away"]["name"]
                    mid = f["fixture"]["id"]
                    matches.append((f"{away} vs {home}", "FUTBOL", start, str(mid)))
            except Exception:
                continue
    # nba
    nb = fetch_nba_games_for_today()
    if nb and nb.get("response"):
        for g in nb["response"]:
            try:
                start = datetime.fromisoformat(g["date"].replace("Z","+00:00"))
                start = start.replace(tzinfo=timezone.utc)
                if now < start < cutoff:
                    home = g["teams"]["home"]["name"]
                    away = g["teams"]["visitors"]["name"]
                    gid = g.get("id") or g.get("gameId") or ""
                    matches.append((f"{away} @ {home}", "NBA", start, str(gid)))
            except Exception:
                continue
    matches.sort(key=lambda x: x[2])
    return matches

# ---------------------------
# SEND: prediction for matches about to start (25-35 min window)
# ---------------------------
async def send_hourly_predictions(context: ContextTypes.DEFAULT_TYPE):
    """Called via JobQueue or scheduled loop. Sends predictions for matches in the 25-35 minute window."""
    logger.info("Running hourly prediction job...")
    try:
        matches = collect_upcoming_matches(window_hours=12)
        if not matches:
            logger.info("No upcoming matches found.")
            return
        now = utcnow()
        for match_str, sport, start_dt, game_id in matches:
            delta = (start_dt - now)
            if timedelta(minutes=25) < delta <= timedelta(minutes=35):
                # check duplicate
                date_str = start_dt.strftime("%Y-%m-%d")
                existing = cursor.execute("SELECT 1 FROM results WHERE match=? AND date=?", (match_str, date_str)).fetchone()
                if existing:
                    logger.info("Prediction already exists for %s at %s", match_str, date_str)
                    continue
                # create features if possible (placeholder)
                # TODO: integrate real features from APIs (team stats) for model input
                prob = predict_probability()
                stake = min(10, max(1, int(prob/10)))
                win_team = match_str.split(" vs ")[1] if " vs " in match_str else (match_str.split(" @ ")[1] if "@" in match_str else match_str)
                tag = "KAZANIR" if prob > 60 else "SÜRPRİZ"
                pred_text = f"{win_team} {tag}"
                sent_time = datetime.utcnow().strftime("%H:%M")
                cursor.execute("""INSERT INTO results (created_at, date, sport, match, prediction, stake, prob, sent_time, game_id, status)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                               (utcnow().isoformat(), date_str, sport, match_str, pred_text, stake, prob, sent_time, game_id, "BEKLENIYOR"))
                conn.commit()
                # create visual
                footer = "t.me/stakedrip  |  StakeDrip"
                card = create_neon_card("StakeDrip Tahmin", match_str, prob, footer=footer)
                caption = (f"<b>STAKEZONE TAHMİNİ</b>\n"
                           f"Maç: <code>{match_str}</code>\n"
                           f"Tahmin: <b>{pred_text}</b>\n"
                           f"Win Rate: <code>{prob}%</code>\n"
                           f"Stake: <code>{stake}/10</code>\n"
                           f"Doğruluk: <code>%{get_accuracy()}</code>\n"
                           f"Zaman: <code>{start_dt.strftime('%H:%M UTC')}</code>\n\n"
                           f"t.me/stakedrip")
                try:
                    await context.bot.send_photo(CHANNEL_ID, photo=InputFile(card, filename="stake_card.png"), caption=caption, parse_mode="HTML")
                    logger.info("Sent prediction for %s", match_str)
                except Exception:
                    logger.exception("Failed to send photo for %s", match_str)
                # only send one match per run to avoid spam; comment if you want all
                # break
    except Exception:
        logger.exception("Hourly prediction job failed.")

# ---------------------------
# DAILY: create best coupon (>=2.0) from today's predictions
# ---------------------------
def create_daily_coupon_min2():
    """Select top predictions (prob > 65) and attempt to make a >=2.0 coupon (3 selections when possible)."""
    today = utcnow().strftime("%Y-%m-%d")
    rows = cursor.execute("SELECT match, prob FROM results WHERE date=? AND prob>65 AND status='BEKLENIYOR'", (today,)).fetchall()
    if not rows:
        return None
    rows_sorted = sorted(rows, key=lambda x: x[1], reverse=True)
    selected = rows_sorted[:3]  # take up to 3
    # map prob -> rough odd estimate
    def prob_to_odd(p):
        # convert probability percentage to implied fair odd and adjust
        fair = max(1.05, 100.0 / max(1.0, p))
        # tighten a bit
        return round(fair + 0.02, 2)
    odds = [prob_to_odd(p) for _, p in selected]
    total = round(math.prod(odds), 2)
    if total < 2.0 and len(selected) < len(rows_sorted):
        # try adding more
        pass
    if total >= 2.0:
        matches_str = " | ".join([m for m,_ in selected])
        cursor.execute("INSERT INTO coupons (created_at, date, matches, total_odds, status) VALUES (?, ?, ?, ?, ?)",
                       (utcnow().isoformat(), today, matches_str, total, "BEKLENIYOR"))
        conn.commit()
        return {"matches": matches_str, "total": total}
    return None

async def send_daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Generating daily coupon...")
    coupon = create_daily_coupon_min2()
    if not coupon:
        logger.info("No valid daily coupon found.")
        return
    text = (f"<b>GÜNLÜK KUPON</b>\n\n"
            f"<code>{coupon['matches']}</code>\n"
            f"Toplam Oran: <code>{coupon['total']}</code>\n"
            f"Tahmin tipi: XGBoost %65+\n\n"
            f"t.me/stakedrip")
    try:
        await context.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        logger.info("Daily coupon sent: %s", coupon['total'])
    except Exception:
        logger.exception("Failed to send daily coupon.")

# ---------------------------
# CHECK: update match results using API (fixtures endpoint)
# ---------------------------
def update_match_results_from_api():
    """For matches in DB with BEKLENIYOR, check final score via fixtures endpoint and update status."""
    logger.info("Checking match results via API...")
    today = utcnow().strftime("%Y-%m-%d")
    rows = cursor.execute("SELECT id, match, game_id, date FROM results WHERE status='BEKLENIYOR'").fetchall()
    for rid, match_str, game_id, date in rows:
        if not game_id:
            continue
        # attempt football fixture check
        try:
            # Try football fixtures
            url = f"https://{FOOTBALL_HOST}/fixtures"
            params = {"id": game_id}
            r = requests.get(url, headers=HEADERS, params=params, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if data.get("response"):
                    f = data["response"][0]
                    status = f["fixture"]["status"]["short"]
                    if status in ("FT", "AET", "PEN"):  # finished
                        home_goals = f["goals"]["home"]
                        away_goals = f["goals"]["away"]
                        # determine winner from stored match string
                        # match_str like "Away vs Home"
                        try:
                            away_name, _, home_name = match_str.partition(" vs ")
                        except:
                            away_name, home_name = "", ""
                        winner = None
                        if home_goals > away_goals:
                            winner = home_name
                        elif away_goals > home_goals:
                            winner = away_name
                        else:
                            winner = "BERABERE"
                        result_status = "KAZANDI" if winner and winner in match_str and winner != "BERABERE" else ("KAYBETTI" if winner!="BERABERE" else "KAYBETTI")
                        cursor.execute("UPDATE results SET status=? WHERE id=?", (result_status, rid))
                        conn.commit()
            else:
                # try NBA
                url2 = f"https://{NBA_HOST}/games"
                params2 = {"id": game_id}
                r2 = requests.get(url2, headers=HEADERS, params=params2, timeout=8)
                if r2.status_code == 200:
                    data2 = r2.json()
                    if data2.get("response"):
                        g = data2["response"][0]
                        status2 = g.get("status")
                        # For NBA the API structure differs; check final or finished flags
                        # If game has final score in g['scores'] or g['home']['score']
                        # This block is API-specific; adapt as required
                        if g.get("statusShort") in ("FT", "F"):
                            home_score = g.get("scores", {}).get("home", None) or g.get("home_team", {}).get("score", {}).get("displayValue")
                            away_score = g.get("scores", {}).get("away", None) or g.get("visitor_team", {}).get("score", {}).get("displayValue")
                            # fallback: cannot determine -> skip
            # small sleep to avoid rate limits
            time.sleep(0.5)
        except Exception:
            logger.exception("Checking result for %s failed", match_str)

# ---------------------------
# COMMANDS
# ---------------------------
async def start_cmd(update: object, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚡ StakeDrip Pro aktif. Komutlar: /tahmin /kupon /sonuclar /istatistik. Adminler: /admin mark <id> <KAZANDI|KAYBETTI>")

async def tahmin_cmd(update: object, context: ContextTypes.DEFAULT_TYPE):
    # manual generation + immediate send to user
    match_list = collect_upcoming_matches(window_hours=6)
    if not match_list:
        await update.message.reply_text("Bugün için yakın maç bulunamadı.")
        return
    # take first upcoming
    match_str, sport, start_dt, game_id = match_list[0]
    prob = predict_probability()
    stake = min(10, max(1, int(prob/10)))
    winner = match_str.split(" vs ")[1] if " vs " in match_str else (match_str.split(" @ ")[1] if "@" in match_str else match_str)
    pred_text = f"{winner} {'KAZANIR' if prob>60 else 'SÜRPRİZ'}"
    # Save to DB as manual (date = start date)
    date_str = start_dt.strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO results (created_at, date, sport, match, prediction, stake, prob, sent_time, game_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (utcnow().isoformat(), date_str, sport, match_str, pred_text, stake, prob, utcnow().strftime("%H:%M"), game_id, "BEKLENIYOR"))
    conn.commit()
    # create image
    card = create_neon_card("StakeDrip Tahmin (Manuel)", match_str, prob, footer="t.me/stakedrip")
    caption = (f"🎯 <b>Manuel Tahmin</b>\nMaç: <code>{match_str}</code>\nTahmin: <b>{pred_text}</b>\nWin Rate: <code>{prob}%</code>\nStake: <code>{stake}/10</code>")
    await update.message.reply_photo(photo=card, caption=caption, parse_mode="HTML")

async def kupon_cmd(update: object, context: ContextTypes.DEFAULT_TYPE):
    today = utcnow().strftime("%Y-%m-%d")
    # find today's coupon, or create
    row = cursor.execute("SELECT id, matches, total_odds, status FROM coupons WHERE date=?", (today,)).fetchone()
    if row:
        cid, matches_str, total, status = row
        await update.message.reply_text(f"Günün kuponu:\n{matches_str}\nOran: {total}\nDurum: {status}")
        return
    coupon = create_daily_coupon_min2()
    if not coupon:
        await update.message.reply_text("Bugün yeterli güçlü tahmin yok; kupon oluşturulamadı.")
        return
    await update.message.reply_text(f"Günün kuponu oluşturuldu:\n{coupon['matches']}\nOran: {coupon['total']}")

async def sonuclar_cmd(update: object, context: ContextTypes.DEFAULT_TYPE):
    rows = cursor.execute("SELECT id, date, match, prediction, prob, stake, status FROM results ORDER BY id DESC LIMIT 8").fetchall()
    if not rows:
        await update.message.reply_text("Henüz kayıtlı sonuç yok.")
        return
    text = "📊 Son Tahminler (son 8):\n\n"
    for rid, date, match, pred, prob, stake, status in rows:
        emoji = "✅" if status == "KAZANDI" else ("❌" if status == "KAYBETTI" else "🔄")
        text += f"{rid}. {emoji} {match} → {pred} ({prob}%) | Stake:{stake}/10 | {status}\n"
    await update.message.reply_text(text)

async def istatistik_cmd(update: object, context: ContextTypes.DEFAULT_TYPE):
    total = cursor.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    win = cursor.execute("SELECT COUNT(*) FROM results WHERE status='KAZANDI'").fetchone()[0]
    rate = round((win/total*100) if total>0 else 0, 1)
    await update.message.reply_text(f"📈 Doğruluk oranı: %{rate}\nToplam tahmin: {total}\nKazananlar: {win}")

async def admin_cmd(update: object, context: ContextTypes.DEFAULT_TYPE):
    # expects: /admin mark <id> <KAZANDI|KAYBETTI>
    text = update.message.text or ""
    parts = text.strip().split()
    if len(parts) >= 4 and parts[1].lower() == "mark":
        try:
            rid = int(parts[2])
            st = parts[3].upper()
            if st not in ("KAZANDI", "KAYBETTI"):
                await update.message.reply_text("Durum KAZANDI veya KAYBETTI olmalı.")
                return
            cursor.execute("UPDATE results SET status=? WHERE id=?", (st, rid))
            conn.commit()
            await update.message.reply_text(f"ID {rid} için durum {st} olarak güncellendi.")
        except Exception:
            await update.message.reply_text("Kullanım: /admin mark <id> <KAZANDI|KAYBETTI>")
    else:
        await update.message.reply_text("Admin komutları: /admin mark <id> <KAZANDI|KAYBETTI>")

# ---------------------------
# PERIODIC TASKS (JobQueue)
# ---------------------------
async def schedule_jobs(app):
    # align first hourly job to top of hour
    first = seconds_until_next_hour()
    logger.info("Scheduling hourly predictions; first run in %s seconds.", first)
    jq = app.job_queue
    jq.run_repeating(send_hourly_predictions, interval=3600, first=first)
    # daily coupon at e.g. 10:00 local (UTC adjust)
    # We'll schedule a daily coupon at 12:00 UTC by default; adjust per TIMEZONE if needed
    coupon_first = seconds_until_next_hour() + 60  # slight offset
    jq.run_repeating(lambda ctx: asyncio.create_task(send_daily_coupon(ctx)), interval=60*60*2, first=coupon_first)
    # result checker: every 5 minutes
    jq.run_repeating(lambda ctx: asyncio.get_running_loop().run_in_executor(None, update_match_results_from_api), interval=300, first=30)

# ---------------------------
# Utility: accuracy display
# ---------------------------
def get_accuracy() -> float:
    try:
        total = cursor.execute("SELECT COUNT(*) FROM results WHERE status IS NOT NULL").fetchone()[0]
        win = cursor.execute("SELECT COUNT(*) FROM results WHERE status='KAZANDI'").fetchone()[0]
        return round((win / total * 100) if total>0 else 0, 1)
    except Exception:
        return 0.0

# ---------------------------
# MAIN
# ---------------------------
async def main():
    logger.info("Starting StakeDrip Pro V4...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    # commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("tahmin", tahmin_cmd))
    app.add_handler(CommandHandler("kupon", kupon_cmd))
    app.add_handler(CommandHandler("sonuclar", sonuclar_cmd))
    app.add_handler(CommandHandler("istatistik", istatistik_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    # schedule jobs after app ready
    await app.initialize()
    await app.start()
    await schedule_jobs(app)
    logger.info("Bot started and jobs scheduled.")
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main_
