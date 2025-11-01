#!/usr/bin/env python3
# main.py — StakeDrip Pro with admin alerts (admin: Arxen26 default)
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
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# ------------- CONFIG (env) -------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_SPORTS_KEY = os.getenv("API_SPORTS_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@stakedrip")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Arxen26")  
DB_PATH = os.getenv("DB_PATH", "/tmp/stakezone_pro.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
TIMEZONE = os.getenv("TIMEZONE", "UTC")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN environment variable is required!")

# API hosts
FOOTBALL_HOST = "v3.football.api-sports.io"
NBA_HOST = "v2.nba.api-sports.io"
HEADERS = {"x-apisports-key": API_SPORTS_KEY} if API_SPORTS_KEY else {}

# ------------- logging -------------
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("stakedrip")

# ------------- DB -------------
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
    status TEXT
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

# ------------- model (optional) -------------
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

# ------------- helpers -------------
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

# ------------- safe messaging -------------
async def safe_send(update, context, text: str):
    try:
        if getattr(update, "message", None):
            await update.message.reply_text(text)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception:
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except Exception:
            logger.exception("Message send failed")

async def safe_send_photo(update, context, photo, caption=""):
    try:
        if getattr(update, "message", None):
            await update.message.reply_photo(photo=photo, caption=caption, parse_mode="HTML")
        else:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo, caption=caption, parse_mode="HTML")
    except Exception:
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo, caption=caption, parse_mode="HTML")
        except Exception:
            logger.exception("Photo send failed")

# ------------- visual -------------
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

# ------------- Buraya kadar hatasız çalışır -------------
# Devam eden komutlar (start_cmd, tahmin_cmd, kupon_cmd, sonuclar_cmd vb.)
# Tüm mesaj ve foto gönderimleri safe_send / safe_send_photo üzerinden olmalı.

# ------------- main -------------
def main():
    try:
        logger.info("🚀 StakeDrip Pro başlatılıyor...")
        app = ApplicationBuilder().token(BOT_TOKEN).build()

        # Handlers ekleme
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("yardim", yardim_cmd))
        app.add_handler(CommandHandler("tahmin", tahmin_cmd))
        app.add_handler(CommandHandler("kupon", kupon_cmd))
        app.add_handler(CommandHandler("sonuclar", sonuclar_cmd))
        app.add_handler(CommandHandler("istatistik", istatistik_cmd))
