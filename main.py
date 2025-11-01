#!/usr/bin/env python3
# main.py — StakeDrip Pro with admin alerts, extended leagues, and conflict-free polling
import os
import io
import math
import time
import json
import random
import logging
import sqlite3
import asyncio
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# optional model libs
try:
    import joblib
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBClassifier
    MODEL_AVAILABLE = True
except Exception:
    MODEL_AVAILABLE = False

from telegram import InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_SPORTS_KEY = os.getenv("API_SPORTS_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@stakedrip")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Arxen26")
DB_PATH = os.getenv("DB_PATH", "/tmp/stakezone_pro.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
TIMEZONE = os.getenv("TIMEZONE", "UTC")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN environment variable is required!")

# ---------------- Logging ----------------
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("stakedrip")

# ---------------- Database ----------------
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
    status TEXT,
    alt_ust TEXT,
    karsi_gol TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    date TEXT,
    matches TEXT,
    total_odds REAL,
    status TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT,
    team TEXT
)
""")
conn.commit()

# ---------------- Model ----------------
MODEL_FILE = os.getenv("MODEL_FILE", "/tmp/model.pkl")
SCALER_FILE = os.getenv("SCALER_FILE", "/tmp/scaler.pkl")

def train_fallback_model():
    try:
        import numpy as np
        from sklearn.preprocessing import StandardScaler
        from xgboost import XGBClassifier
        np.random.seed(42)
        X = np.column_stack([
            np.random.uniform(100,140,900),
            np.random.uniform(95,135,900),
            np.random.uniform(40,55,900),
            np.random.uniform(38,53,900),
            np.random.randint(0,20,900),
            np.random.randint(0,20,900),
        ])
        y = (X[:,0] - X[:,1] + np.random.randn(900)*5 > 0).astype(int)
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        model = XGBClassifier(n_estimators=100, max_depth=4, use_label_encoder=False, eval_metric='logloss')
        model.fit(Xs, y)
        joblib.dump(model, MODEL_FILE)
        joblib.dump(scaler, SCALER_FILE)
        logger.info("Fallback model trained.")
        return True
    except Exception:
        logger.exception("Fallback model train failed.")
        return False

if MODEL_AVAILABLE:
    try:
        if not (os.path.exists(MODEL_FILE) and os.path.exists(SCALER_FILE)):
            ok = train_fallback_model()
            if not ok:
                MODEL_AVAILABLE = False
        if MODEL_AVAILABLE:
            model = joblib.load(MODEL_FILE)
            scaler = joblib.load(SCALER_FILE)
            logger.info("Model loaded.")
    except Exception:
        logger.exception("Loading model failed.")
        MODEL_AVAILABLE = False

def predict_probability(features: Optional[List[float]] = None) -> float:
    try:
        if MODEL_AVAILABLE:
            if features is None:
                features = [118,112,47.5,45.2,9,7]
            X = np.array([features])
            Xs = scaler.transform(X)
            p = model.predict_proba(Xs)[0][1] * 100
            return float(round(p,1))
    except Exception:
        logger.exception("Model failed; fallback.")
    base = 50 + (math.sin(datetime.utcnow().hour/24*2*math.pi) * 10)
    jitter = random.uniform(-8,8)
    return round(max(1, min(99, base + jitter)), 1)

# ---------------- Helpers ----------------
def utcnow():
    return datetime.utcnow().replace(tzinfo=timezone.utc)

async def fetch_json_async(url: str, headers: dict=None, params: dict=None, timeout: int=10):
    loop = asyncio.get_event_loop()
    def _get():
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            return r.status_code, r.text
        except Exception as e:
            return None, str(e)
    status, text = await loop.run_in_executor(None, _get)
    if status != 200:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None

# ---------------- Visual ----------------
ASSET_FONT = os.path.join(os.path.dirname(__file__), "assets", "neon.ttf")
def create_neon_card(title: str, subtitle: str, prob: float, footer: str="") -> io.BytesIO:
    W, H = 1200, 520
    bg = Image.new("RGBA", (W,H), (6,6,10,255))
    txt = Image.new("RGBA", (W,H), (0,0,0,0))
    draw = ImageDraw.Draw(txt)
    try:
        fbig = ImageFont.truetype(ASSET_FONT, 72)
        fmed = ImageFont.truetype(ASSET_FONT, 32)
    except Exception:
        try:
            fbig = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
            fmed = ImageFont.truetype("DejaVuSans.ttf", 32)
        except Exception:
            fbig = ImageFont.load_default()
            fmed = ImageFont.load_default()
    x,y = 60,60
    for o,a in [(16,28),(8,90),(4,200)]:
        draw.text((x+o,y+o), title, font=fbig, fill=(60,160,255,a))
    draw.text((x,y), title, font=fbig, fill=(190,240,255,255))
    draw.text((x, y+110), subtitle, font=fmed, fill=(230,200,255,255))
    bar_x, bar_y = x, H-140
    bar_w = 820
    filled = int(bar_w * (prob/100.0))
    draw.rectangle([bar_x, bar_y, bar_x+filled, bar_y+36], fill=(0,220,150,255))
    draw.rectangle([bar_x+filled, bar_y, bar_x+bar_w, bar_y+36], fill=(255,80,80,160))
    draw.text((bar_x+bar_w+20, bar_y-2), f"{prob}%", font=fmed, fill=(240,240,240,255))
    if footer:
        draw.text((x, H-60), footer, font=fmed, fill=(180,180,200,200))
    glow = txt.filter(ImageFilter.GaussianBlur(4))
    combined = Image.alpha_composite(bg, glow)
    combined = Image.alpha_composite(combined, txt)
    buf = io.BytesIO()
    combined.convert("RGB").save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf

# ---------------- Helpers for odds ----------------
def prob_to_odd(p: float) -> float:
    fair = max(1.01, round(100.0 / max(1.0, p), 2))
    return round(fair + 0.02, 2)

# ---------------- Match Collection ----------------
async def collect_upcoming_matches(window_hours: int=24) -> List[Tuple[str,str,datetime,str]]:
    now = utcnow()
    cutoff = now + timedelta(hours=window_hours)
    matches = []

    # --- Football ---
    if API_SPORTS_KEY:
        url = f"https://v3.football.api-sports.io/fixtures"
        params = {"date": now.strftime("%Y-%m-%d")}
        fb = await fetch_json_async(url, headers={"x-apisports-key": API_SPORTS_KEY}, params=params)
        if fb and fb.get("response"):
            for f in fb["response"]:
                try:
                    start = datetime.fromisoformat(f["fixture"]["date"].replace("Z","+00:00")).replace(tzinfo=timezone.utc)
                    if now < start < cutoff:
                        home = f["teams"]["home"]["name"]
                        away = f["teams"]["away"]["name"]
                        mid = str(f["fixture"]["id"])
                        league = f["league"]["name"]
                        if league in ["Premier League","La Liga","Serie A","Bundesliga","Ligue 1","Süper Lig","1. Lig","2. Lig"]:
                            matches.append((f"{away} vs {home}", "FUTBOL", start, mid))
                except Exception:
                    continue

    matches.sort(key=lambda x: x[2])
    return matches

# ---------------- Send Predictions ----------------
async def send_hourly_predictions(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Hourly prediction job running...")
    try:
        matches = await collect_upcoming_matches(window_hours=24)
        if not matches:
            logger.info("No upcoming matches.")
            return
        now = utcnow()
        for match_str, sport, start_dt, game_id in matches:
            delta = start_dt - now
            if timedelta(minutes=25) < delta <= timedelta(minutes=35):
                date_str = start_dt.strftime("%Y-%m-%d")
                existing = cursor.execute("SELECT 1 FROM results WHERE match=? AND date=?", (match_str, date_str)).fetchone()
                if existing:
                    continue
                prob = predict_probability()
                stake = min(10, max(1, int(prob/10)))
                altust = "ÜST" if random.random() < 0.5 else "ALT"
                karsi_gol = "VAR" if random.random() < 0.5 else "YOK"
                winner = match_str.split(" vs ")[1] if " vs " in match_str else match_str
                tag = "KAZANIR" if prob > 60 else "SÜRPRİZ"
                pred_text = f"{winner} {tag}"
                sent_time = datetime.utcnow().strftime("%H:%M")
                cursor.execute("""INSERT INTO results (created_at, date, sport, match, prediction, stake, prob, sent_time, game_id, status, alt_ust, karsi_gol)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                               (utcnow().isoformat(), date_str, sport, match_str, pred_text, stake, prob, sent_time, game_id, "BEKLENIYOR", altust, karsi_gol))
                conn.commit()
                if prob >= 50:
                    card = create_neon_card("StakeDrip Tahmin", match_str, prob, footer="t.me/stakedrip")
                    caption = (f"<b>STAKEZONE TAHMİNİ</b>\nMaç: <code>{match_str}</code>\nTahmin: <b>{pred_text}</b>\nWin Rate: <code>{prob}%</code>\nStake: <code>{stake}/10</code>\nAlt/Üst: <code>{altust}</code>\nKarşılıklı Gol: <code>{karsi_gol}</code>\nZaman: <code>{start_dt.strftime('%H:%M UTC')}</code>")
                    try:
                        await context.bot.send_photo(CHANNEL_ID, photo=InputFile(card, filename="stake_card.png"), caption=caption, parse_mode="HTML")
                        logger.info("Sent prediction for %s", match_str)
                    except Exception:
                        logger.exception("Failed to send photo for %s", match_str)
                break
    except Exception:
        logger.exception("Hourly predictions job failed.")

# ---------------- Daily Coupon ----------------
def create_daily_coupon_min2() -> Optional[dict]:
    today = utcnow().strftime("%Y-%m-%d")
    rows = cursor.execute("SELECT match, prob FROM results WHERE date=? AND prob>65 AND status='BEKLENIYOR'", (today,)).fetchall()
    if not rows:
        return None
    rows_sorted = sorted(rows, key=lambda x: x[1], reverse=True)
    selected = rows_sorted[:3]
    odds = [prob_to_odd(p) for _, p in selected]
    total = round(math.prod(odds), 2)
    if total >= 2.0:
        matches_str = " | ".join([m for m,_ in selected])
        cursor.execute("INSERT INTO coupons (created_at, date, matches, total_odds, status) VALUES (?, ?, ?, ?, ?)",
                       (utcnow().isoformat(), today, matches_str, total, "BEKLENIYOR"))
        conn.commit()
        return {"matches": matches_str, "total": total}
    return None

async def send_daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    coupon = create_daily_coupon_min2()
    if not coupon:
        logger.info("No coupon created.")
        return
    text = (f"<b>GÜNLÜK KUPON</b>\n\n<code>{coupon['matches']}</code>\nToplam Oran: <code>{coupon['total']}</code>")
    try:
        await context.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        logger.info("Daily coupon sent.")
    except Exception:
        logger.exception("Failed to send daily coupon.")

# ---------------- Result Update ----------------
def update_match_results_from_api():
    logger.info("Checking results for BEKLENIYOR matches...")
    rows = cursor.execute("SELECT id, match, game_id FROM results WHERE status='BEKLENIYOR'").fetchall()
    for rid, match_str, game_id in rows:
        if not game_id:
            continue
        try:
            url = f"https://v3.football.api-sports.io/fixtures"
            params = {"id": game_id}
            r = requests.get(url, headers={"x-apisports-key": API_SPORTS_KEY}, params=params, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if data.get("response"):
                    f = data["response"][0]
                    status = f["fixture"]["status"]["short"]
                    if status in ("FT","AET","PEN"):
                        home_goals = f["goals"]["home"]
                        away_goals = f["goals"]["away"]
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
                        pred_row = cursor.execute("SELECT prediction FROM results WHERE id=?", (rid,)).fetchone()
                        pred = pred_row[0] if pred_row else ""
                        result_status = "KAYBETTI"
                        if winner != "BERABERE" and winner in pred:
                            result_status = "KAZANDI"
                        cursor.execute("UPDATE results SET status=? WHERE id=?", (result_status, rid))
                        conn.commit()
            time.sleep(0.3)
        except Exception:
            logger.exception("Error checking fixture %s", game_id)

# ---------------- TELEGRAM COMMANDS ----------------
async def start_cmd(update, context):
    txt = "⚡️ StakeDrip Pro aktif.\nKomutlar:\n/tahmin /kupon /sonuclar /istatistik /trend /surpriz"
    await update.message.reply_text(txt)

# ... (manuel komutlar tahmin, kupon, sonuclar, istatistik, trend, surpriz) aynı şekilde devam ediyor

# ---------------- REGISTER HANDLERS ----------------
def register_handlers(app):
    app.add_handler(CommandHandler("start", start_cmd))
    # diğer komutlar buraya eklenecek: tahmin_cmd, kupon_cmd, sonuclar_cmd vs.

# ---------------- JOB SCHEDULER ----------------
def seconds_until_next_hour() -> int:
    try:
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        seconds = (next_hour - now).total_seconds()
        return max(1, int(seconds))
    except Exception:
        logger.exception("seconds_until_next_hour hatası!")
        return 3600

async def schedule_jobs(app):
    jq = getattr(app, "job_queue", None)
    if not jq:
        logger.warning("⚠️ JobQueue başlatılamadı — tahmin planlayıcısı devre dışı.")
        return
    try:
        first_hour = seconds_until_next_hour()
        jq.run_repeating(send_hourly_predictions, interval=3600, first=first_hour)
        jq.run_repeating(send_daily_coupon, interval=60*60*6, first=10)
        jq.run_repeating(lambda ctx: asyncio.get_running_loop().run_in_executor(None, update_match_results_from_api),
                         interval=300, first=30)
        logger.info("✅ JobQueue planlandı (tahmin, kupon, sonuç kontrol)")
    except Exception:
        logger.exception("❌ schedule_jobs içinde hata oluştu.")

# ---------------- MAIN ----------------
async def start_bot():
    # Webhook conflict önleme
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    register_handlers(app)
    app.job_queue.run_once(lambda ctx: asyncio.create_task(schedule_jobs(app)), 1)
    logger.info("✅ Bot başlatıldı ve tek instance çalışıyor")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(start_bot())
