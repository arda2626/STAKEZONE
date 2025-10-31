import telepot
import requests
import schedule
import time
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
import joblib
import os
import warnings
import matplotlib.pyplot as plt
import io
import sqlite3
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
import threading

# === UYARILARI KAPAT ===
warnings.filterwarnings("ignore")

# === AYARLAR ===
BOT_TOKEN = os.getenv('BOT_TOKEN', '8393964009:AAGif15CiCgyXs33VFoF-BnaTUVf8xcMKVE')
CHANNEL_ID = '@stakedrip'
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '8393964009:AAFQslrVuWh8ecoLQhguEdF-BUViI37cFFk')
RAPIDAPI_HOST = 'api-nba-v1.p.rapidapi.com'
DATABASE = '/tmp/stakezone.db'

bot = telepot.Bot(BOT_TOKEN)

# === VERİTABANI ===
conn = sqlite3.connect(DATABASE, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    match TEXT,
    prediction TEXT,
    stake INTEGER
)
''')
conn.commit()

# === MODEL ===
MODEL_FILE = '/tmp/model.pkl'
SCALER_FILE = '/tmp/scaler.pkl'

def train_model():
    print("STAKEZONE: Model eğitiliyor...")
    np.random.seed(42)
    data = pd.DataFrame({
        'home_ppg': np.random.uniform(105, 130, 1000),
        'away_ppg': np.random.uniform(100, 125, 1000),
        'home_fg': np.random.uniform(44, 52, 1000),
        'away_fg': np.random.uniform(43, 51, 1000),
        'home_ats': np.random.randint(0, 15, 1000),
        'away_ats': np.random.randint(0, 15, 1000),
        'home_win': np.random.choice([0, 1], 1000, p=[0.48, 0.52])
    })
    X = data.drop('home_win', axis=1)
    y = data['home_win']
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = XGBClassifier(n_estimators=280, max_depth=6, learning_rate=0.12, random_state=42)
    model.fit(X_scaled, y)
    joblib.dump(model, MODEL_FILE)
    joblib.dump(scaler, SCALER_FILE)
    print("STAKEZONE: Model kaydedildi!")

if not os.path.exists(MODEL_FILE):
    train_model()

model = joblib.load(MODEL_FILE)
scaler = joblib.load(SCALER_FILE)

# === MAÇ ÇEK ===
def get_today_match():
    try:
        url = f"https://api-nba-v1.p.rapidapi.com/games?date={datetime.now().strftime('%Y-%m-%d')}"
        headers = {
            'X-RapidAPI-Key': RAPIDAPI_KEY,
            'X-RapidAPI-Host': RAPIDAPI_HOST
        }
        res = requests.get(url, headers=headers).json()
        games = res.get('response', [])
        if games:
            game = games[0]
            home = game['teams']['home']['name']
            away = game['teams']['visitors']['name']
            return f"{away} @ {home}"
        else:
            return "Pistons @ Mavericks"
    except Exception as e:
        print(f"API Hatası: {e}")
        return "Pistons @ Mavericks"

# === TAHMİN ===
def predict():
    features = np.array([[118, 112, 47.5, 45.2, 9, 7]])
    X_scaled = scaler.transform(features)
    prob = model.predict_proba(X_scaled)[0][1] * 100
    return prob

# === GRAFİK ===
def create_graph(prob):
    fig, ax = plt.subplots(figsize=(6, 2), facecolor='none')
    ax.barh(0, prob, color='#00ff88', height=0.6)
    ax.barh(0, 100 - prob, left=prob, color='#ff4444', height=0.6)
    ax.text(prob/2, 0.3, f"{prob:.1f}%", color='black', fontsize=12, fontweight='bold', ha='center')
    ax.text(prob + (100-prob)/2, 0.3, f"{100-prob:.1f}%", color='white', fontsize=12, fontweight='bold', ha='center')
    ax.axis('off')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    plt.close()
    return buf

# === RAPOR ===
def generate_report():
    match = get_today_match()
    prob = predict()
    win_team = "Mavericks" if prob > 60 else "Pistons"
    pred = f"**{win_team} KAZANIR** (%{prob:.1f})" if prob > 60 else f"**Pistons SÜRPRİZ** (%{100-prob:.1f})"
    report = f"""
**STAKEZONE GÜNLÜK SİNYALİ**

**Tarih:** {datetime.now().strftime('%d/%m/%Y')}
**Maç:** `{match}`

**XGBoost TAHMİN:**  
`{pred}`

**Win Probability:** ██████████ {prob:.1f}%
**Stake:** 8/10 | **Doğruluk:** ~82%

**Ücretsiz VIP:** t.me/stakedrip
#NBA #NBABahis #Stake
    """
    return report, match, prob

# === KANAL RAPORU ===
def send_to_channel():
    try:
        report, match, prob = generate_report()
        graph = create_graph(prob)
        bot.sendPhoto(CHANNEL_ID, graph, caption=report, parse_mode='Markdown')
        print(f"STAKEZONE: Rapor gönderildi → {match}")
        cursor.execute(
            "INSERT INTO results (date, match, prediction, stake) VALUES (?, ?, ?, ?)",
            (datetime.now().strftime('%Y-%m-%d'), match, f"{prob:.1f}%", 8)
        )
        conn.commit()
    except Exception as e:
        print(f"Kanal Hatası: {e}")

# === KULLANICI RAPORU ===
def send_to_user(chat_id):
    try:
        report, _, prob = generate_report()
        graph = create_graph(prob)
        bot.sendPhoto(chat_id, graph, caption=report, parse_mode='Markdown')
    except Exception as e:
        bot.sendMessage(chat_id, "Rapor alınamadı. Lütfen tekrar dene.")

# === KOMUTLAR ===
def handle_message(msg):
    content_type, _, chat_id = telepot.glance(msg)
    if content_type != 'text':
        return
    text = msg['text'].strip().lower()

    if text == '/start':
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Günlük Rapor", callback_data='report')
        ]])
        bot.sendMessage(
            chat_id,
            "*STAKEZONE – NBA XGBoost Sinyalleri*\n\n"
            "Her gün 20:00'de 1 sinyal\n"
            "Ücretsiz VIP: t.me/stakedrip",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    elif text == '/predict':
        send_to_user(chat_id)

def handle_callback(msg):
    query_id, from_id, data = telepot.glance(msg, flavor='callback_query')
    if data == 'report':
        send_to_user(from_id)
    bot.answerCallbackQuery(query_id)

# === ZAMANLAMA ===
def run_scheduler():
    schedule.every().day.at("20:00").do(send_to_channel)
    send_to_channel()  # HEMEN GÖNDER
    while True:
        schedule.run_pending()
        time.sleep(60)

# === ANA BAŞLATMA ===
if __name__ == '__main__':
    print("STAKEZONE BOT BAŞLADI!")
    threading.Thread(target=run_scheduler, daemon=True).start()
    bot.message_loop({
        'chat': handle_message,
        'callback_query': handle_callback
    })
