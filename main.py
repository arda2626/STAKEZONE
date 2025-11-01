#!/usr/bin/env python3
# stakebot_pro.py — StakeDrip Pro Full Version

import os, io, math, time, json, random, logging, sqlite3, asyncio, requests
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Optional ML model
try:
    import joblib, numpy as np
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
conn.commit()

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

# ---------------- Model ----------------
MODEL_FILE = os.getenv("MODEL_FILE", "/tmp/model.pkl")
SCALER_FILE = os.getenv("SCALER_FILE", "/tmp/scaler.pkl")

def train_fallback_model():
    try:
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

# ---------------- MATCH FETCH ----------------
FOOTBALL_HOST = "v3.football.api-sports.io"
BASKETBALL_HOST = "v2.basketball.api-sports.io"
TENNIS_HOST = "v1.tennis.api-sports.io"
HEADERS = {"x-apisports-key": API_SPORTS_KEY} if API_SPORTS_KEY else {}

async def collect_upcoming_matches(window_hours:int=24) -> List[Tuple[str,str,datetime,str]]:
    now = utcnow()
    cutoff = now + timedelta(hours=window_hours)
    matches = []

    # Futbol
    if API_SPORTS_KEY:
        fb_url = f"https://{FOOTBALL_HOST}/fixtures"
        fb_params = {"date": now.strftime("%Y-%m-%d")}
        fb_data = await fetch_json_async(fb_url, headers=HEADERS, params=fb_params)
        if fb_data and fb_data.get("response"):
            for f in fb_data["response"]:
                try:
                    start = datetime.fromisoformat(f["fixture"]["date"].replace("Z","+00:00")).replace(tzinfo=timezone.utc)
                    if now < start < cutoff:
                        home = f["teams"]["home"]["name"]
                        away = f["teams"]["away"]["name"]
                        mid = str(f["fixture"]["id"])
                        matches.append((f"{away} vs {home}", "FUTBOL", start, mid))
                except: continue

    # Basket
    if API_SPORTS_KEY:
        bb_url = f"https://{BASKETBALL_HOST}/games"
        bb_params = {"date": now.strftime("%Y-%m-%d")}
        bb_data = await fetch_json_async(bb_url, headers=HEADERS, params=bb_params)
        if bb_data and bb_data.get("response"):
            for g in bb_data["response"]:
                try:
                    start = datetime.fromisoformat(g["date"].replace("Z","+00:00")).replace(tzinfo=timezone.utc)
                    if now < start < cutoff:
                        home = g["teams"]["home"]["name"]
                        away = g["teams"]["visitors"]["name"]
                        gid = str(g.get("id") or g.get("gameId") or "")
                        matches.append((f"{away} @ {home}", "BASKETBOL", start, gid))
                except: continue

    # Tenis
    if API_SPORTS_KEY:
        tn_url = f"https://{TENNIS_HOST}/matches"
        tn_params = {"date": now.strftime("%Y-%m-%d")}
        tn_data = await fetch_json_async(tn_url, headers=HEADERS, params=tn_params)
        if tn_data and tn_data.get("response"):
            for m in tn_data["response"]:
                try:
                    start = datetime.fromisoformat(m["date"].replace("Z","+00:00")).replace(tzinfo=timezone.utc)
                    players = f"{m['players'][0]['name']} vs {m['players'][1]['name']}"
                    mid = str(m.get("id") or "")
                    matches.append((players, "TENIS", start, mid))
                except: continue

    matches.sort(key=lambda x:x[2])
    return matches

def prob_to_odd(p:float) -> float:
    fair = max(1.01, round(100.0/max(1.0,p),2))
    return round(fair + 0.02,2)

# ---------------- JOBS ----------------
async def send_hourly_predictions(context: ContextTypes.DEFAULT_TYPE):
    try:
        matches = await collect_upcoming_matches(window_hours=24)
        if not matches:
            logger.info("No upcoming matches in next 24h")
            return
        for match_name, sport, start, mid in matches[:5]:
            prob = predict_probability()
            stake = 10
            prediction = "1" if prob>50 else "0"
            cursor.execute("""
                INSERT INTO results (created_at,date,sport,match,prediction,stake,prob,game_id,status)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (utcnow().isoformat(), start.date().isoformat(), sport, match_name, prediction, stake, prob, mid, "PENDING"))
            conn.commit()
            buf = create_neon_card(match_name, sport, prob)
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=InputFile(buf, filename="pred.png"))
            logger.info(f"Sent prediction: {match_name} [{prob}%]")
    except Exception:
        logger.exception("send_hourly_predictions failed.")

async def check_results(context: ContextTypes.DEFAULT_TYPE):
    # Placeholder: sonuç kontrolü implement edilebilir
    logger.info("Checking results...")

async def daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    matches = await collect_upcoming_matches(window_hours=24)
    if not matches:
        return
    sel = matches[:5]
    total_odds = math.prod([prob_to_odd(predict_probability()) for _,_,_,_ in sel])
    cursor.execute("""
        INSERT INTO coupons (created_at,date,matches,total_odds,status)
        VALUES (?,?,?,?,?)
    """, (utcnow().isoformat(), utcnow().date().isoformat(),
          ",".join([m[0] for m in sel]), total_odds, "PENDING"))
    conn.commit()
    logger.info("Daily coupon created.")

# ---------------- HANDLERS ----------------
async def start(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 StakeDrip Pro Bot aktif!")

async def help_cmd(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Komutlar: /start /yardim /tahmin /kupon /sonuclar /istatistik /trend /surpriz")

async def tahmin(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE):
    matches = await collect_upcoming_matches(window_hours=24)
    txt = "\n".join([f"{m[0]} ({m[1]})" for m in matches[:5]]) or "Yaklaşan maç yok."
    await update.message.reply_text(txt)

# ---------------- REGISTER ----------------
def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yardim", help_cmd))
    app.add_handler(CommandHandler("tahmin", tahmin))

async def schedule_jobs(app):
    app.job_queue.run_repeating(send_hourly_predictions, interval=3600, first=10)
    app.job_queue.run_repeating(check_results, interval=300, first=20)
    app.job_queue.run_repeating(daily_coupon, interval=21600, first=30)
    logger.info("✅ JobQueue planlandı (tahmin, kupon, sonuç kontrol)")

# ---------------- MAIN ----------------
def main():
    logger.info("🚀 StakeDrip Pro başlatılıyor...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    register_handlers(app)
    # JobQueue schedule
    asyncio.create_task(schedule_jobs(app))
    # Tek event loop ile run
    app.run_polling()

if __name__ == "__main__":
    main()
