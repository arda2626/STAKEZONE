import os
import asyncio
import requests
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# ----------------------
# 1. Telegram ve API Bilgileri
# ----------------------
API_TOKEN = os.getenv("API_TOKEN")  # Telegram bot token
CHAT_ID = os.getenv("CHAT_ID")      # Kanal veya kullanıcı ID
API_KEY = os.getenv("API_KEY")      # API-Football key

if not API_TOKEN or not CHAT_ID or not API_KEY:
    raise Exception("API_TOKEN, CHAT_ID ve API_KEY environment variable olarak ayarlanmalı!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ----------------------
# 2. Futbol Maçlarını API-Football’dan Çekme
# ----------------------
def fetch_football_matches():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = "https://v3.football.api-sports.io/fixtures"
        headers = {"X-RapidAPI-Key": API_KEY}
        params = {"date": today, "league":"39"}  # 39 = Premier League örnek
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        matches = []
        for m in data.get('response', []):
            matches.append({
                'sport':'football',
                'home': m['teams']['home']['name'],
                'away': m['teams']['away']['name'],
                'home_stats':[1,1,1,1,1],  # Simülasyon ML için
                'away_stats':[1,1,1,1,1],
                'odds': m.get('odds', {})
            })
        return matches
    except Exception as e:
        print("Futbol verisi çekilemedi:", e)
        return []

# ----------------------
# 3. ML Model Eğitimi
# ----------------------
def train_model():
    X = np.random.rand(200, 10)
    y = np.random.choice([0,1,2], size=200)
    model = RandomForestClassifier(n_estimators=100)
    model.fit(X, y)
    return model

ml_model = train_model()

async def ml_prediction(match):
    features = np.array(match['home_stats'] + match['away_stats']).reshape(1,-1)
    pred = ml_model.predict(features)[0]
    x12_map = {0:'1',1:'X',2:'2'}
    prediction = {"1X2":x12_map[pred], "Alt/Üst":np.random.choice(['Alt','Üst']), "KG":np.random.choice(['Var','Yok'])}
    return prediction

# ----------------------
# 4. Önemli Maçları Seçme
# ----------------------
def filter_important_matches(matches, top_n=3):
    for m in matches:
        m['importance'] = sum(m['home_stats']) + sum(m['away_stats'])
    matches.sort(key=lambda x: x['importance'], reverse=True)
    return matches[:top_n]

# ----------------------
# 5. Günlük Kupon
# ----------------------
async def send_daily_coupon():
    matches = fetch_football_matches()
    important = filter_important_matches(matches)
    if not important: return
    coupon = []
    for match in important:
        prediction = await ml_prediction(match)
        coupon.append(f"{match['home']} vs {match['away']} | 1X2:{prediction['1X2']} | Alt/Üst:{prediction['Alt/Üst']} | KG:{prediction['KG']}")
    text = "🎯 Günlük Kupon 🎯\n" + "\n".join(coupon)
    await bot.send_message(chat_id=CHAT_ID, text=text)
    print("Günlük kupon gönderildi!")

# ----------------------
# 6. Saatlik Tahmin
# ----------------------
async def send_hourly_prediction():
    matches = fetch_football_matches()
    important = filter_important_matches(matches, top_n=1)
    if not important: return
    match = important[0]
    prediction = await ml_prediction(match)
    text = f"⏰ Saatlik Tahmin ⏰\n{match['home']} vs {match['away']} | 1X2:{prediction['1X2']} | Alt/Üst:{prediction['Alt/Üst']} | KG:{prediction['KG']}"
    await bot.send_message(chat_id=CHAT_ID, text=text)
    print("Saatlik tahmin gönderildi!")

# ----------------------
# 7. Main
# ----------------------
async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_coupon, 'cron', hour=0, minute=0)
    scheduler.add_job(send_hourly_prediction, 'interval', hours=1)
    scheduler.start()
    print("Bot çalışıyor...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
