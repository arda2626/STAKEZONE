# main.py
import asyncio
import logging
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN, CHAT_ID
from coupon_builder import build_coupon

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    while True:
        try:
            coupon_text = await build_coupon()
            await bot.send_message(chat_id=CHAT_ID, text=coupon_text)
            log.info("✅ Kupon gönderildi.")
        except Exception as e:
            log.warning(f"⚠️ Kupon gönderim hatası: {e}")
        await asyncio.sleep(3600)  # Her saat kupon gönder

if __name__ == "__main__":
    asyncio.run(main())
