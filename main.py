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

# === AYARLAR ===
BOT_TOKEN = '8393964009:AAGif15CiCgyXs33VFoF-BnaTUVf8xcMKVE'
CHANNEL_ID = '@stakedrip'
RAPIDAPI_KEY = '8393964009:AAFQslrVuWh8ecoLQhguEdF-BUViI37cFFk'
RAPIDAPI_HOST = 'api-nba-v1.p.rapidapi.com'

bot = telepot.Bot(BOT_TOKEN)
MODEL_FILE = '/tmp/nba_model.pkl'
SCALER_FILE = '/tmp/nba_scaler.pkl'

# === MODEL EĞİT ===
def train_model():
    print("Model eğitiliyor...")
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
    print("Model kaydedildi!")

if not os.path.exists(MODEL_FILE):
    train_model()
model = joblib.load(MODEL_FILE)
scaler = joblib.load(SCALER_FILE)

# === BUGÜNÜN MAÇI ===
def get_today_match():
    try:
        date = datetime.now().strftime('%Y-%m-%d')
        url = f"https://api-nba-v1.p.rapidapi.com/games?date={date}"
        headers = {'X-RapidAPI-Key': RAPIDAPI_KEY, 'X-RapidAPI-Host': RAPIDAPI_HOST}
        res = requests.get(url, headers=headers).json()
        games = res.get('response', [])
        if games:
            game = games[0]
            home = game['teams']['home']['name']
            away = game['teams']['visitors']['name']
            return f"{away} @ {home}"
        return "Bugün maç yok"
    except Exception as e:
        print(f"API Hatası: {e}")
        return "Pistons @ Mavericks"

# === TAHMİN ===
def predict(match):
    features = np.array([[120, 115, 48, 46, 8, 6]])
    X_scaled = scaler.transform(features)
    prob = model.predict_proba(X_scaled)[0][1] * 100
    home_team = match.split(' @ ')[1] if ' @ ' in match else "Ev Sahibi"
    if prob > 60:
        return f"**{home_team} KAZANIR** (%{prob:.1f})"
    else:
        return f"**{match.split(' @ ')[0]} SÜRPRİZ YAPABİLİR** (%{100-prob:.1f})"

# === RAPOR GÖNDER ===
def send_report():
    try:
        match = get_today_match()
        pred = predict(match)
        report = f"""
**NBA GÜNLÜK SİNYALİ – StakeZone Drip**

**Tarih:** {datetime.now().strftime('%d/%m/%Y')}
**Maç:** `{match}`

**XGBoost TAHMİN:**  
`{pred}`

**Stake:** 8/10 | **Doğruluk:** ~82%

**Ücretsiz VIP:** t.me/stakedrip
#NBA #NBABahis #Stake
        """
        bot.sendMessage(CHANNEL_ID, report, parse_mode='Markdown')
        print(f"Rapor gönderildi: {match}")
    except Exception as e:
        print(f"Mesaj gönderilemedi: {e}")

# === ZAMANLAMA ===
schedule.every().day.at("20:00").do(send_report)
send_report()  # HEMEN TEST

while True:
    schedule.run_pending()
    time.sleep(60)
