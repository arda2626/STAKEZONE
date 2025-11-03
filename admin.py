# admin.py
# small admin command handlers (if you want to hook into telegram.ext handlers)
from telegram.ext import CommandHandler, ContextTypes
from telegram import Update

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot running.")

def get_handlers():
    return [CommandHandler("status", cmd_status)]
