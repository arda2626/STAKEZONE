import asyncio
import logging
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# === TOKENLAR ===
BOT_TOKEN = "8393964009:AAGif15CiCgyXs33VFoF-BnaTUVf8xcMKVE"
RAPID_API_KEY = "460ec2a26e2178f365e61e063bb6b487"
CHAT_ID = "@stakedrip"  # Kanal kullanıcı adı veya numeric ID (örnek: -1001234567890)

# === LOG AYARI ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === /start KOMUTU ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💧 StakeDrip aktif! Saat başı tahminleri gönderiyorum ⚡️")

# === TAHMİN ÇEKME ===
def get_predictions():
    url = "https://api-football-v1.p.rapidapi.com/v3/predictions"
    params = {"league": "1", "season": "2024"}  # Premier League örnek
    headers = {"x-apisports-key": RAPID_API_KEY}

    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if "response" not in data or not data["response"]:
            return "⚠️ Şu anda tahmin bulunamadı."

        match = data["response"][0]
        teams = match["teams"]
        predictions = match["predictions"]

        text = (
            f"⚽️ *StakeDrip Tahmini*\n\n"
            f"{teams['home']['name']} 🆚 {teams['away']['name']}\n"
            f"🏆 Kazanan: *{predictions['winner']['name']}*\n"
            f"📈 Olasılık: *{predictions['percent']['home']} - {predictions['percent']['away']}*\n"
            f"🕐 Güncelleme: {datetime.now().strftime('%H:%M')}"
        )
        return text

    except Exception as e:
        logging.error(f"Prediction fetch error: {e}")
        return "❌ Tahmin alınamadı."

# === MESAJ ATMA ===
async def send_prediction(app):
    text = get_predictions()
    if text:
        try:
            await app.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Message send error: {e}")

# === SAAT BAŞI PAYLAŞIM ===
async def prediction_loop(app):
    while True:
        await send_prediction(app)
        await asyncio.sleep(3600)  # 1 saatte bir gönderir

# === ANA FONKSİYON ===
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    asyncio.create_task(prediction_loop(app))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
