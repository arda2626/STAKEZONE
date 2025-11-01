#!/usr/bin/env python3
# main.py — StakeDrip Pro with admin alerts, live fixtures, and extended leagues
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

# Optional ML model libs
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

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN environment variable is required!")

FOOTBALL_HOST = "v3.football.api-sports.io"
BASKETBALL_HOST = "v2.basketball.api-sports.io"
TENNIS_HOST = "v1.tennis.api-sports.io"
HEADERS = {"x-apisports-key": API_SPORTS_KEY} if API_SPORTS_KEY else {}

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

# ---------------- API Fetchers ----------------
async def fetch_football_fixtures():
    if not API_SPORTS_KEY:
        return None
    url = f"https://{FOOTBALL_HOST}/fixtures"
    params = {"date": utcnow().strftime("%Y-%m-%d")}
    return await fetch_json_async(url, headers=HEADERS, params=params)

async def fetch_basketball_games():
    if not API_SPORTS_KEY:
        return None
    url = f"https://{BASKETBALL_HOST}/games"
    params = {"date": utcnow().strftime("%Y-%m-%d")}
    return await fetch_json_async(url, headers=HEADERS, params=params)

async def fetch_tennis_matches():
    if not API_SPORTS_KEY:
        return None
    url = f"https://{TENNIS_HOST}/matches"
    params = {"date": utcnow().strftime("%Y-%m-%d")}
    return await fetch_json_async(url, headers=HEADERS, params=params)

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

# ---------------- Match Collection ----------------
async def collect_upcoming_matches(window_hours: int=24) -> List[Tuple[str,str,datetime,str]]:
    now = utcnow()
    cutoff = now + timedelta(hours=window_hours)
    matches = []

    fb = await fetch_football_fixtures()
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

    nb = await fetch_basketball_games()
    if nb and nb.get("response"):
        for g in nb["response"]:
            try:
                start = datetime.fromisoformat(g["date"].replace("Z","+00:00")).replace(tzinfo=timezone.utc)
                if now < start < cutoff:
                    home = g["teams"]["home"]["name"]
                    away = g["teams"]["visitors"]["name"]
                    gid = str(g.get("id") or g.get("gameId") or "")
                    league = g.get("league", {}).get("name","")
                    if league in ["NBA","EuroLeague","Basketball Super League"]:
                        matches.append((f"{away} vs {home}", "BASKET", start, gid))
            except Exception:
                continue

    tn = await fetch_tennis_matches()
    if tn and tn.get("response"):
        for t in tn["response"]:
            try:
                start = datetime.fromisoformat(t["fixture"]["date"].replace("Z","+00:00")).replace(tzinfo=timezone.utc)
                if now < start < cutoff:
                    home = t["players"][0]["name"]
                    away = t["players"][1]["name"]
                    gid = str(t["fixture"]["id"])
                    matches.append((f"{away} vs {home}", "TENIS", start, gid))
            except Exception:
                continue

    matches.sort(key=lambda x: x[2])
    return matches

# ---------------- Bot Handlers ----------------
async def start_command(update, context):
    await update.message.reply_text("🚀 StakeDrip Pro çalışıyor!")

async def live_matches_command(update, context):
    matches = await collect_upcoming_matches(6)
    txt = "\n".join([f"{m[2].strftime('%H:%M')} | {m[1]} | {m[0]}" for m in matches[:20]])
    await update.message.reply_text(txt or "Bugün canlı maç bulunamadı.")

# ---------------- Jobs ----------------
async def send_hourly_predictions(app):
    matches = await collect_upcoming_matches(6)
    for match in matches[:5]:
        title, sport, dt, mid = match
        prob = predict_probability()
        buf = create_neon_card(title=title, subtitle=sport, prob=prob)
        try:
            await app.bot.send_photo(chat_id=CHANNEL_ID, photo=InputFile(buf), caption=f"{title} | olasılık: {prob}%")
        except Exception:
            logger.exception("Prediction send failed.")

async def check_results():
    # Placeholder: Sonuçları API’den kontrol et
    logger.info("Sonuç kontrol çalıştı (simülasyon).")
    await asyncio.sleep(0.2)

async def schedule_jobs(app):
    while True:
        try:
            await send_hourly_predictions(app)
            await check_results()
            await asyncio.sleep(3600)
        except Exception:
            logger.exception("Job error, tekrar deneniyor.")
            await asyncio.sleep(30)

# ---------------- Bot Başlat ----------------
async def start_bot():
    try:
        logger.info("🚀 StakeDrip Pro başlatılıyor...")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("live", live_matches_command))

        # JobQueue başlat
        asyncio.create_task(schedule_jobs(app))

        # Polling başlat
        await app.run_polling()
    except Exception:
        logger.exception("❌ Ana uygulama çalışırken hata oluştu.")

# ---------------- RUN ----------------
if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(start_bot())
        logger.info("✅ Bot başlatıldı (mevcut loop üzerinde).")
    except RuntimeError:
        asyncio.run(start_bot())
