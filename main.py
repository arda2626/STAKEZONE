#!/usr/bin/env python3
# StakeDrip Pro — Tüm Modüller Aktif, Tek Dosya
import os, io, math, time, json, random, logging, sqlite3, asyncio, requests
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ML model optional
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

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_SPORTS_KEY = os.getenv("API_SPORTS_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@stakedrip")
DB_PATH = os.getenv("DB_PATH", "/tmp/stakezone_pro.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
TIMEZONE = os.getenv("TIMEZONE", "UTC")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN required!")

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
            if not train_fallback_model():
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
            return float(round(model.predict_proba(Xs)[0][1]*100,1))
    except Exception:
        logger.exception("Model fallback used.")
    base = 50 + (math.sin(datetime.utcnow().hour/24*2*math.pi)*10)
    jitter = random.uniform(-8,8)
    return round(max(1, min(99, base+jitter)),1)

# ---------------- Helpers ----------------
def utcnow():
    return datetime.utcnow().replace(tzinfo=timezone.utc)

async def fetch_json_async(url: str, headers=None, params=None, timeout: int=10):
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
    except:
        return None

# ---------------- API Fetchers ----------------
HEADERS = {"x-apisports-key": API_SPORTS_KEY} if API_SPORTS_KEY else {}
FOOTBALL_HOST = "v3.football.api-sports.io"
BASKETBALL_HOST = "v2.basketball.api-sports.io"
TENNIS_HOST = "v1.tennis.api-sports.io"

async def fetch_football_fixtures():
    if not API_SPORTS_KEY: return None
    url = f"https://{FOOTBALL_HOST}/fixtures"
    params = {"date": utcnow().strftime("%Y-%m-%d")}
    return await fetch_json_async(url, headers=HEADERS, params=params)

async def fetch_basketball_games():
    if not API_SPORTS_KEY: return None
    url = f"https://{BASKETBALL_HOST}/games"
    params = {"date": utcnow().strftime("%Y-%m-%d")}
    return await fetch_json_async(url, headers=HEADERS, params=params)

async def fetch_tennis_matches():
    if not API_SPORTS_KEY: return None
    url = f"https://{TENNIS_HOST}/matches"
    params = {"date": utcnow().strftime("%Y-%m-%d")}
    return await fetch_json_async(url, headers=HEADERS, params=params)

# ---------------- Visual ----------------
ASSET_FONT = os.path.join(os.path.dirname(__file__), "assets", "neon.ttf")
def create_neon_card(title: str, subtitle: str, prob: float, footer: str="") -> io.BytesIO:
    W,H = 1200,520
    bg = Image.new("RGBA",(W,H),(6,6,10,255))
    txt = Image.new("RGBA",(W,H),(0,0,0,0))
    draw = ImageDraw.Draw(txt)
    try:
        fbig = ImageFont.truetype(ASSET_FONT,72)
        fmed = ImageFont.truetype(ASSET_FONT,32)
    except:
        fbig = ImageFont.load_default()
        fmed = ImageFont.load_default()
    x,y=60,60
    draw.text((x+16,y+28), title, font=fbig, fill=(60,160,255,28))
    draw.text((x,y), title, font=fbig, fill=(190,240,255,255))
    draw.text((x,y+110), subtitle, font=fmed, fill=(230,200,255,255))
    bar_x, bar_y = x,H-140
    bar_w = 820
    filled = int(bar_w*(prob/100))
    draw.rectangle([bar_x,bar_y,bar_x+filled,bar_y+36], fill=(0,220,150,255))
    draw.rectangle([bar_x+filled,bar_y,bar_x+bar_w,bar_y+36], fill=(255,80,80,160))
    draw.text((bar_x+bar_w+20,bar_y-2), f"{prob}%", font=fmed, fill=(240,240,240,255))
    if footer: draw.text((x,H-60),footer,font=fmed,fill=(180,180,200,200))
    glow = txt.filter(ImageFilter.GaussianBlur(4))
    combined = Image.alpha_composite(bg, glow)
    combined = Image.alpha_composite(combined, txt)
    buf=io.BytesIO()
    combined.convert("RGB").save(buf,"PNG",optimize=True)
    buf.seek(0)
    return buf

# ---------------- Match Collection ----------------
async def collect_upcoming_matches(window_hours: int=24) -> List[Tuple[str,str,datetime,str]]:
    now = utcnow()
    cutoff = now+timedelta(hours=window_hours)
    matches=[]
    # --- Football ---
    fb = await fetch_football_fixtures()
    if fb and fb.get("response"):
        for f in fb["response"]:
            try:
                start = datetime.fromisoformat(f["fixture"]["date"].replace("Z","+00:00")).replace(tzinfo=timezone.utc)
                if now<start<cutoff:
                    home=f["teams"]["home"]["name"]
                    away=f["teams"]["away"]["name"]
                    mid=str(f["fixture"]["id"])
                    league=f["league"]["name"]
                    if league in ["Premier League","La Liga","Serie A","Bundesliga","Ligue 1","Süper Lig"]:
                        matches.append((f"{away} vs {home}","FUTBOL",start,mid))
            except: continue
    # --- Basketball ---
    nb = await fetch_basketball_games()
    if nb and nb.get("response"):
        for g in nb["response"]:
            try:
                start = datetime.fromisoformat(g["date"].replace("Z","+00:00")).replace(tzinfo=timezone.utc)
                if now<start<cutoff:
                    home=g["teams"]["home"]["name"]
                    away=g["teams"]["visitors"]["name"]
                    gid=str(g.get("id") or g.get("gameId") or "")
                    league=g.get("league",{}).get("name","")
                    if league in ["NBA","EuroLeague","BSL","Liga ACB"]:
                        matches.append((f"{away} @ {home}","BASKETBOL",start,gid))
            except: continue
    # --- Tennis ---
    tn = await fetch_tennis_matches()
    if tn and tn.get("response"):
        for m in tn["response"]:
            try:
                start = datetime.fromisoformat(m["date"].replace("Z","+00:00")).replace(tzinfo=timezone.utc)
                if now<start<cutoff:
                    players=f"{m['players'][0]['name']} vs {m['players'][1]['name']}"
                    mid=str(m.get("id") or "")
                    matches.append((players,"TENIS",start,mid))
            except: continue
    matches.sort(key=lambda x:x[2])
    return matches

# ---------------- Prediction ----------------
async def generate_predictions(matches: List[Tuple[str,str,datetime,str]]):
    results=[]
    for match,sport,start,mid in matches:
        prob = predict_probability()
        stake = random.choice([5,10,15])
        results.append((datetime.utcnow().isoformat(), start.isoformat(), sport, match, "1X2", stake, prob, None, mid,"PENDING","", ""))
    return results

# ---------------- Telegram ----------------
async def send_prediction(app, prediction):
    match, sport, prob, mid = prediction[3], prediction[2], prediction[6], prediction[9]
    card = create_neon_card(title=match, subtitle=sport, prob=prob, footer="StakeDrip Pro")
    await app.bot.send_photo(chat_id=CHANNEL_ID, photo=InputFile(card), caption=f"🎯 {match}\nTahmin: 1X2\nOlasılık: {prob}%")

# ---------------- Jobs ----------------
async def job_predictions(app):
    matches = await collect_upcoming_matches(24)
    predictions = await generate_predictions(matches)
    for pred in predictions:
        cursor.execute("""INSERT INTO results(created_at,date,sport,match,prediction,stake,prob,status,game_id,alt_ust,karsi_gol) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",pred)
        conn.commit()
        await send_prediction(app, pred)
    logger.info("✅ Tahminler gönderildi.")

# ---------------- Bot ----------------
async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 StakeDrip Pro aktif!")

async def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    # --- schedule jobs ---
    async def scheduler():
        while True:
            try:
                await job_predictions(app)
            except Exception: logger.exception("Job fail")
            await asyncio.sleep(60*60)
    asyncio.create_task(scheduler())
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except RuntimeError:
        logger.exception("❌ Ana uygulama çalışırken hata oluştu.")
