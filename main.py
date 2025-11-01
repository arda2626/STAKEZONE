import asyncio
import logging
from datetime import datetime, timedelta, time
import aiohttp
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio

# ----------------- Konfigürasyon -----------------
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"  # Telegram bot token
API_SPORTS_KEY = "YOUR_API_KEY"    # API-Sports key
CHANNEL_ID = "@your_channel"       # Kanal kullanıcı adı veya ID

# ----------------- Logging -----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------- API -----------------
BASE_URL = "https://v3.football.api-sports.io/"
HEADERS = {
    "x-rapidapi-key": API_SPORTS_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

# ----------------- ML Model -----------------
class SportsMLPredictor:
    def __init__(self):
        self.model = LogisticRegression()
        self.is_trained = False

    async def fetch_historical_data(self, league=39, days=30):
        """Tarihi maç verilerini API'den çek (eğitim için)."""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}fixtures", params={
                'league': league,
                'season': datetime.now().year,
                'from': start_date,
                'to': end_date
            }, headers=HEADERS) as resp:
                data = await resp.json()
                df = pd.DataFrame(data.get('response', []))
                if df.empty:
                    return pd.DataFrame()
                df['home_goals_avg'] = df['goals'].apply(lambda x: x['home'])
                df['away_goals_avg'] = df['goals'].apply(lambda x: x['away'])
                df['outcome'] = np.where(df['home_goals_avg'] > df['away_goals_avg'], 1,
                                         np.where(df['home_goals_avg'] == df['away_goals_avg'], 0, 2))
                return df[['home_goals_avg', 'away_goals_avg', 'outcome']]

    def train(self, df):
        if len(df) < 10:
            logger.warning("Yeterli veri yok, model eğitilemiyor.")
            return
        X = df[['home_goals_avg', 'away_goals_avg']]
        y = df['outcome']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
        self.model.fit(X_train, y_train)
        self.is_trained = True
        acc = accuracy_score(y_test, self.model.predict(X_test))
        logger.info(f"ML Model Doğruluğu: {acc:.2f}")

    def predict(self, home_avg, away_avg, total_line=2.5):
        if not self.is_trained:
            return {"1X2": "1", "AltUst": "Üst", "KG": "Var", "Oran": 2.1}
        pred = self.model.predict([[home_avg, away_avg]])[0]
        prob = self.model.predict_proba([[home_avg, away_avg]])[0]
        total_goals = home_avg + away_avg
        kg_prob = 1 - (np.exp(-home_avg) * np.exp(-away_avg))
        alt_ust = "Alt" if total_goals < total_line else "Üst"
        return {
            "1X2": {1: "1", 0: "X", 2: "2"}[pred],
            "AltUst": alt_ust,
            "KG": "Var" if kg_prob > 0.5 else "Yok",
            "Oran": max(prob) * 2
        }

predictor = SportsMLPredictor()

# ----------------- API Fonksiyonları -----------------
async def get_upcoming_matches(hours=24):
    end_time = (datetime.now() + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%S')
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}fixtures", params={
            'from': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'to': end_time
        }, headers=HEADERS) as resp:
            data = await resp.json()
            return data.get('response', [])

async def get_odds(match_id):
    # Şimdilik dummy oranlar
    return {"1": 2.0, "X": 3.0, "2": 2.5, "Over2.5": 1.8, "KGVar": 1.9}

# ----------------- Bot Komutları -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merhaba! Spor tahmin botuyum. Günlük kupon ve saatlik tahminler kanalında paylaşılıyor.")

# ----------------- Görevler -----------------
async def daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    matches = await get_upcoming_matches(hours=24)
    if not matches:
        return
    coupon_matches = []
    total_odds = 1.0
    for match in matches[:3]:
        try:
            home_team = match['teams']['home']['name']
            away_team = match['teams']['away']['name']
        except KeyError:
            continue
        pred = predictor.predict(1.5, 1.2)
        odds = await get_odds(match['fixture']['id'])
        selected_bet = pred["1X2"]
        odd = odds.get(selected_bet, 1.5)
        total_odds *= odd
        if total_odds >= 2.0:
            coupon_matches.append(f"{home_team} vs {away_team}: {selected_bet} @ {odd} (AI: {pred['Oran']:.1f})")
    message = f"🤑 **Günlük Kupon ({datetime.now().strftime('%Y-%m-%d')}):**\n" + "\n".join(coupon_matches) + f"\nToplam Oran: {total_odds:.2f}"
    await context.bot.send_message(CHANNEL_ID, message, parse_mode='Markdown')

async def hourly_prediction(context: ContextTypes.DEFAULT_TYPE):
    matches = await get_upcoming_matches(hours=2)
    if not matches:
        return
    match = matches[0]
    try:
        home_team = match['teams']['home']['name']
        away_team = match['teams']['away']['name']
    except KeyError:
        return
    pred = predictor.predict(1.8, 1.3)
    odds = await get_odds(match['fixture']['id'])
    message = f"⏰ **Saatlik Tahmin ({datetime.now().strftime('%H:00')}):**\n{home_team} vs {away_team}\n" \
              f"1X2: {pred['1X2']} | Alt/Üst: {pred['AltUst']} | KG: {pred['KG']}\n" \
              f"AI Destekli Oran: {pred['Oran']:.2f} | Gerçek Oran: {odds['1']}"
    await context.bot.send_message(CHANNEL_ID, message, parse_mode='Markdown')

# ----------------- Ana Fonksiyon -----------------
async def main():
    nest_asyncio.apply()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    job_queue = app.job_queue
    job_queue.run_daily(daily_coupon, time=time(hour=9, minute=0))
    job_queue.run_repeating(hourly_prediction, interval=3600, first=0)

    df = await predictor.fetch_historical_data()
    if not df.empty:
        predictor.train(df)

    logger.info("Bot çalışıyor...")
    await app.run_polling()

# ----------------- Çalıştır -----------------
if __name__ == '__main__':
    asyncio.run(main())
