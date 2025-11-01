import os
import io
import asyncio
import requests
import joblib
import sqlite3
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from telegram import InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === AYARLAR (Railway: Env vars) ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@stakedrip")
API_KEY = os.getenv("API_SPORTS_KEY")  # "460ec2a..." şeklinde
NBA_HOST = "v2.nba.api-sports.io"
FOOTBALL_HOST = "v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

DATABASE = "/tmp/stakezone_pro.db"

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN missing")

# === DB ===
conn = sqlite3.connect(DATABASE, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY, date TEXT, sport TEXT, match TEXT, prediction TEXT, stake INTEGER, prob REAL, sent_time TEXT, game_id TEXT, result TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS coupons (id INTEGER PRIMARY KEY, date TEXT, matches TEXT, total_odds REAL, status TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, free_until TEXT)''')
conn.commit()

# === Basit model (senin model mantığın korunacak) ===
MODEL_FILE = "/tmp/model.pkl"
SCALER_FILE = "/tmp/scaler.pkl"

def train_dummy_model():
    if os.path.exists(MODEL_FILE) and os.path.exists(SCALER_FILE):
        return
    np.random.seed(42)
    data = pd.DataFrame({
        'home_ppg': np.random.uniform(100, 140, 2000),
        'away_ppg': np.random.uniform(95, 135, 2000),
        'home_fg': np.random.uniform(40, 55, 2000),
        'away_fg': np.random.uniform(38, 53, 2000),
        'home_ats': np.random.randint(0, 20, 2000),
        'away_ats': np.random.randint(0, 20, 2000),
        'home_win': np.random.choice([0,1], 2000, p=[0.47,0.53])
    })
    X = data.drop('home_win', axis=1)
    y = data['home_win']
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    model = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.1, use_label_encoder=False, eval_metric='logloss')
    model.fit(Xs, y)
    joblib.dump(model, MODEL_FILE)
    joblib.dump(scaler, SCALER_FILE)

train_dummy_model()
model = joblib.load(MODEL_FILE)
scaler = joblib.load(SCALER_FILE)

# === API çağrıları (basit) ===
def fetch_football_today():
    try:
        url = f"https://{FOOTBALL_HOST}/fixtures"
        today = datetime.utcnow().strftime("%Y-%m-%d")
        params = {"date": today}
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        return r.json()
    except Exception as e:
        return None

def fetch_nba_today():
    try:
        url = f"https://{NBA_HOST}/games"
        today = datetime.utcnow().strftime("%Y-%m-%d")
        params = {"date": today}
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        return r.json()
    except Exception as e:
        return None

# === Tahmin (dummy) ===
def predict():
    features = np.array([[118,112,47.5,45.2,9,7]])
    Xs = scaler.transform(features)
    prob = model.predict_proba(Xs)[0][1]*100
    return round(prob,1)

# === Görsel oluştur (neon-stil basit) ===
def create_neon_banner(title, subtitle, prob):
    W, H = 1200, 480
    bg = Image.new("RGBA", (W,H), (8,8,12,255))

    draw = ImageDraw.Draw(bg)
    # font (Railway: sunucuda uygun bir font yoksa repo'ya ttf koy)
    try:
        font_big = ImageFont.truetype("arial.ttf", 72)
        font_med = ImageFont.truetype("arial.ttf", 36)
    except:
        font_big = ImageFont.load_default()
        font_med = ImageFont.load_default()

    # neon glow: dibine blur'lu yazı katmanı ekle
    txt = Image.new("RGBA", (W,H), (0,0,0,0))
    d2 = ImageDraw.Draw(txt)
    x = 60
    y = 60
    # glow katmanları
    for offset,alpha in [(12,25),(8,60),(4,140)]:
        d2.text((x+offset, y+offset), title, font=font_big, fill=(40,160,255,alpha))
    d2.text((x, y), title, font=font_big, fill=(180,240,255,255))

    # alt yazı
    sy = y + 120
    d2.text((x, sy), subtitle, font=font_med, fill=(200,180,255,255))

    # prob bar
    bar_x, bar_y = x, H - 120
    bar_w = 800
    filled = int(bar_w * (prob/100))
    d2.rectangle([bar_x, bar_y, bar_x+filled, bar_y+30], fill=(0,255,180,255))
    d2.rectangle([bar_x+filled, bar_y, bar_x+bar_w, bar_y+30], fill=(255,80,80,200))
    d2.text((bar_x + bar_w + 20, bar_y), f"{prob}%", font=font_med, fill=(230,230,230,255))

    # glow blur
    glow = txt.filter(ImageFilter.GaussianBlur(4))
    combined = Image.alpha_composite(bg, glow)
    combined = Image.alpha_composite(combined, txt)

    buf = io.BytesIO()
    combined.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf

# === Gönderim fonksiyonu (her saat başı çalıştırılacak) ===
async def send_hourly_prediction(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow()
    # maç çek (örnek amaçlı; burada kendi mantığını ekle)
    fb = fetch_football_today()
    nba = fetch_nba_today()
    # Basit: eğer maç varsa, örnek bir match al
    match_title = "No Match Found"
    sport = None
    if fb and fb.get('response'):
        f = fb['response'][0]
        match_title = f"{f['teams']['away']['name']} vs {f['teams']['home']['name']}"
        sport = "FUTBOL"
        start = f['fixture']['date']
    elif nba and nba.get('response'):
        g = nba['response'][0]
        match_title = f"{g['teams']['visitors']['name']} @ {g['teams']['home']['name']}"
        sport = "NBA"
        start = g.get('date')
    else:
        # eğer maç yok, yine de bilgi atabiliriz ya da return
        return

    prob = predict()
    stake = min(10, max(1, int(prob/10)))
    win_team = match_title.split(" vs ")[1] if sport == "FUTBOL" and " vs " in match_title else match_title.split(" @ ")[1] if "@" in match_title else match_title
    prediction_text = f"{win_team} {'KAZANIR' if prob>60 else 'SÜRPRİZ'}"

    # DB kayıt
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    time_str = datetime.utcnow().strftime("%H:%M")
    cursor.execute("INSERT INTO results (date, sport, match, prediction, stake, prob, sent_time, game_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (date_str, sport or "GENEL", match_title, prediction_text, stake, prob, time_str, None))
    conn.commit()

    # görsel oluştur
    banner = create_neon_banner("StakeDrip Tahmin", match_title, prob)

    caption = f"<b>STAKEZONE TAHMİNİ</b>\nMaç: <code>{match_title}</code>\nTahmin: <b>{prediction_text}</b>\nWin Rate: <code>{prob}%</code>\nStake: <code>{stake}/10</code>\n\nt.me/stakedrip"
    try:
        await context.bot.send_photo(CHANNEL_ID, photo=InputFile(banner, filename="prob.png"), caption=caption, parse_mode="HTML")
        print("Tahmin gönderildi:", match_title, prob)
    except Exception as e:
        print("Gönderim hatası:", e)

# === Komutlar ===
async def start(update, context):
    await context.bot.send_message(update.effective_chat.id, "StakeDrip Bot aktif. Otomatik tahminler saat başı gönderilecek.")

async def bugun(update, context):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    rows = cursor.execute("SELECT match, prediction, prob, stake FROM results WHERE date = ?", (today,)).fetchall()
    if rows:
        text = ""
        for m,p,pr,s in rows:
            text += f"{m} → {p} ({pr}%) | Stake {s}/10\n"
        await context.bot.send_message(update.effective_chat.id, text)
    else:
        await context.bot.send_message(update.effective_chat.id, "Bugün tahmin yok.")

# === MAIN ===
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bugun", bugun))

    # JobQueue: saat başı (her 3600 saniyede bir), ama first param ile align etmeyiz.
    # Railway'de çalıştırırken process uyanık kalırsa bu yeterli. Daha kesin align istersen
    # aşağıdaki mantıkla “tam saat başı” olarak ayarlanabilir.
    jq = app.job_queue
    # ilk çalışmayı hemen yap
    jq.run_repeating(send_hourly_prediction, interval=3600, first=10)

    print("Bot çalışıyor...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
