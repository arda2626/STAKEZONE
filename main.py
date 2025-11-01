import asyncio
import os
import requests
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ----------------------
# 1. Telegram Bilgileri
# ----------------------
API_TOKEN = os.getenv("API_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")  # Opsiyonel, canlı API için

if not API_TOKEN or not CHAT_ID:
    raise Exception("API_TOKEN ve CHAT_ID environment variable olarak ayarlanmalı!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ----------------------
# 2. Canlı Maç Verisi Çekme
# ----------------------
API_URL = "https://api.sportradar.com/your_endpoint"

async def fetch_live_matches():
    try:
        if API_KEY:
            # Canlı API isteği
            response = requests.get(API_URL, params={"api_key": API_KEY}).json()
            matches = []
            for m in response.get("matches", []):
                matches.append({
                    "sport": m["sport"],
                    "home": m["home_team"],
                    "away": m["away_team"],
                    "odds": m.get("odds", {}),
                    "home_stats": m.get("home_stats", [0.5]*5),
                    "away_stats": m.get("away_stats", [0.5]*5)
                })
        else:
            # Simülasyon veri
            matches = [
                {'sport':'football','home':'Team A','away':'Team B','odds':{'1':2.1,'X':3.2,'2':3.0}, 
                 'home_stats':[2.1,0.5,1.3,0.8,1.2], 'away_stats':[1.8,0.6,1.0,0.9,1.1]},
                {'sport':'basketball','home':'Team C','away':'Team D','odds':{'1':1.8,'2':2.0}, 
                 'home_stats':[1.9,0.7,0.8,0.6,1.0], 'away_stats':[1.7,0.6,0.9,0.5,1.1]},
                {'sport':'tennis','home':'Player A','away':'Player B','odds':{'1':1.9,'2':1.9}, 
                 'home_stats':[0.8,0.9,0.7,1.0,0.6], 'away_stats':[0.7,0.8,0.9,0.6,0.7]},
            ]
    except Exception as e:
        print("Canlı maç verisi çekilemedi:", e)
        matches = []
    return matches

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

    if match['sport'] == 'football':
        x12_map = {0:'1',1:'X',2:'2'}
        prediction = {"1X2":x12_map[pred],"Alt/Üst":np.random.choice(['Alt','Üst']),"KG":np.random.choice(['Var','Yok'])}
    elif match['sport'] == 'basketball':
        x12_map = {0:'1',2:'2'}
        prediction = {"1X2":x12_map.get(pred,'1'),"Alt/Üst":np.random.choice(['Alt','Üst']),"KG":"Yok"}
    else:  # tenis
        x12_map = {0:'1',2:'2'}
        prediction = {"1X2":x12_map.get(pred,'1'),"Alt/Üst":"Yok","KG":"Yok"}
    return prediction

# ----------------------
# 4. Önemli Maç Filtreleme
# ----------------------
def filter_important_matches(matches, top_n=3):
    for m in matches:
        m['importance'] = sum(m.get('home_stats',[])) + sum(m.get('away_stats',[]))
    matches.sort(key=lambda x: x['importance'], reverse=True)
    return matches[:top_n]

# ----------------------
# 5. Günlük Kupon
# ----------------------
async def send_daily_coupon():
    matches = await fetch_live_matches()
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
    matches = await fetch_live_matches()
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
