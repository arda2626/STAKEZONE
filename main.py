import asyncio
import logging
import nest_asyncio  # Event loop hatası için (opsiyonel, Jupyter/Spyder'da faydalı)
from datetime import datetime, timedelta
import aiohttp
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Konfigürasyon (config.py'den import et veya buraya hardcode)
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"  # config.py'den
API_SPORTS_KEY = "YOUR_API_KEY"    # config.py'den
CHANNEL_ID = "@stakedrip"       # config.py'den

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API-Sports endpoint'leri (ücretsiz plan: 100 istek/gün)
BASE_URL = "https://v3.football.api-sports.io/"  # Futbol için; basket/tenis için uyarla: fixtures?league=...&sport=basketball vb.
HEADERS = {"x-rapidapi-key": API_SPORTS_KEY, "x-rapidapi-host": "v3.football.api-sports.io"}

# Basit ML Modeli: Tarihi verilerle eğit (örnek: futbol için gol/sonuç tahmini)
class SportsMLPredictor:
    def __init__(self):
        self.model = LogisticRegression()
        self.is_trained = False

    async def fetch_historical_data(self, sport='football', days=30):
        """Tarihi maç verilerini API'den çek (eğitim için)."""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}fixtures", params={
                'date': start_date, 'to': end_date, 'league': 39  # Ör: Premier Lig; basket/tenis için değiştir
            }, headers=HEADERS) as resp:
                data = await resp.json()
                df = pd.DataFrame(data['response'])
                if not df.empty:
                    # Özellikler: Ev sahibi gol ort., deplasman formu vb. (basitleştirilmiş)
                    df['home_goals_avg'] = df['goals']['home']  # Gerçekte ortalamala
                    df['away_goals_avg'] = df['goals']['away']
                    df['outcome'] = np.where(df['goals']['home'] > df['goals']['away'], 1,  # 1: Ev kazanır
                                             np.where(df['goals']['home'] == df['goals']['away'], 0, 2))  # 0: Berabere, 2: Deplasman
                    return df[['home_goals_avg', 'away_goals_avg', 'outcome']]
        return pd.DataFrame()

    def train(self, df):
        """ML modeli eğit (1X2 için)."""
        if len(df) < 10:
            return
        X = df[['home_goals_avg', 'away_goals_avg']]
        y = df['outcome']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
        self.model.fit(X_train, y_train)
        self.is_trained = True
        acc = accuracy_score(y_test, self.model.predict(X_test))
        logger.info(f"ML Model Doğruluğu: {acc:.2f}")

    def predict(self, home_avg, away_avg, total_line=2.5):
        """Tahmin: 1X2, Alt/Üst, KG olasılıkları (Poisson ile entegre)."""
        if not self.is_trained:
            return {"1X2": "1", "AltUst": "Üst", "KG": "Var", "Oran": 2.1}  # Varsayılan
        pred = self.model.predict([[home_avg, away_avg]])[0]
        prob = self.model.predict_proba([[home_avg, away_avg]])[0]
        # Poisson ile gol tahmini (basit)
        lambda_home = home_avg
        lambda_away = away_avg
        total_goals = lambda_home + lambda_away
        kg_prob = 1 - (np.exp(-lambda_home) * np.exp(-lambda_away))  # Her iki takım gol atar olasılığı
        alt_ust = "Alt" if total_goals < total_line else "Üst"
        return {
            "1X2": {1: "1", 0: "X", 2: "2"}[pred],
            "AltUst": alt_ust,
            "KG": "Var" if kg_prob > 0.5 else "Yok",
            "Oran": max(prob) * 2  # Basit oran tahmini
        }

predictor = SportsMLPredictor()

# API Fonksiyonları
async def get_upcoming_matches(sport='football', hours=24):
    """Yaklaşan maçları çek (canlı/güncel)."""
    end_time = (datetime.now() + timedelta(hours=hours)).strftime('%Y-%m-%d')
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}fixtures", params={
            'datetime': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), 'to': end_time
        }, headers=HEADERS) as resp:
            data = await resp.json()
            return data['response'] if 'response' in data else []

async def get_odds(match_id):
    """Maç oranlarını çek (1X2, Alt/Üst, KG)."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}odds", params={'fixture': match_id}, headers=HEADERS) as resp:
            data = await resp.json()
            # Basitleştir: Ortalama oranlar
            return {"1": 2.0, "X": 3.0, "2": 2.5, "Over2.5": 1.8, "KGVar": 1.9}  # Gerçek veriyi parse et

# Bot Komutları
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merhaba! Spor tahmin botuyum. Günlük kupon ve saatlik tahminler kanalında paylaşılıyor.")

# Görevler: Günlük/Saatlik
async def daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    """Günlük kupon: En az 2.0 oranlı 2-3 maçlık kupon."""
    matches = await get_upcoming_matches(hours=24)
    if not matches:
        return
    coupon_matches = []
    total_odds = 1.0
    for match in matches[:3]:  # İlk 3 önemli maç
        home_team = match['teams']['home']['name']
        away_team = match['teams']['away']['name']
        # ML tahmini
        pred = predictor.predict(1.5, 1.2)  # Örnek ortalamalar; gerçekte maç istatistiklerinden
        odds = await get_odds(match['fixture']['id'])
        bet_type = "1X2"  # Rastgele: 1X2, AltÜst, KG
        selected_bet = pred["1X2"] if bet_type == "1X2" else pred[bet_type.replace("/", "")]
        odd = odds.get(selected_bet, 1.5)
        total_odds *= odd
        if total_odds >= 2.0:
            coupon_matches.append(f"{home_team} vs {away_team}: {selected_bet} @ {odd} (AI: {pred['Oran']:.1f} olasılık)")
    message = f"🤑 **Günlük Kupon ({datetime.now().strftime('%Y-%m-%d')}):**\n" + "\n".join(coupon_matches) + f"\nToplam Oran: {total_odds:.2f}"
    await context.bot.send_message(CHANNEL_ID, message, parse_mode='Markdown')

async def hourly_prediction(context: ContextTypes.DEFAULT_TYPE):
    """Saatlik tahmin: 1 önemli maç tahmini."""
    matches = await get_upcoming_matches(hours=2)
    if not matches:
        return
    match = matches[0]  # En yakını
    home_team = match['teams']['home']['name']
    away_team = match['teams']['away']['name']
    pred = predictor.predict(1.8, 1.3)  # Gerçek istatistiklerle değiştir
    odds = await get_odds(match['fixture']['id'])
    message = f"⏰ **Saatlik Tahmin ({datetime.now().strftime('%H:00')}):**\n{home_team} vs {away_team}\n" \
              f"1X2: {pred['1X2']} | Alt/Üst: {pred['AltUst']} | KG: {pred['KG']}\n" \
              f"AI Destekli Oran: {pred['Oran']:.2f} | Gerçek Oran: {odds['1']}"
    await context.bot.send_message(CHANNEL_ID, message, parse_mode='Markdown')

# Ana Fonksiyon
async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    # JobQueue: Günlük (09:00) ve saatlik
    job_queue = app.job_queue
    job_queue.run_daily(daily_coupon, time=datetime.time(hour=9, minute=0))
    job_queue.run_repeating(hourly_prediction, interval=3600, first=0)  # Her saat

    # ML Model Eğitimi (Başlangıçta)
    df = await predictor.fetch_historical_data()
    if not df.empty:
        predictor.train(df)

    # Bot Başlat
    await app.initialize()
    await app.start()
    await app.updater.start_polling()  # Event loop hatasız polling
    logger.info("Bot çalışıyor...")

if __name__ == '__main__':
    nest_asyncio.apply()  # Opsiyonel: Event loop hatası için
    asyncio.run(main())
