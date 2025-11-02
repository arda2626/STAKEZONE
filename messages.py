from telegram import Bot
from config import TELEGRAM_TOKEN, CHANNEL_ID
from utils import banner, league_to_flag

bot = Bot(token=TELEGRAM_TOKEN)

async def post_prediction(pred):
    league_flag = league_to_flag(pred.get("league"))
    text = f"{banner(pred.get('sport'))}\n{league_flag} {pred.get('home')} vs {pred.get('away')}\nTahmin: {pred.get('bet')} {pred.get('odds')}\n{pred.get('prob')}%"
    msg = await bot.send_message(chat_id=CHANNEL_ID, text=text)
    return msg.message_id
