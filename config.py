# config.py
import os

# Telegram / TheSportsDB
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or "PUT_YOUR_TELEGRAM_TOKEN_HERE"
THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY") or "PUT_YOUR_THESPORTSDB_KEY_HERE"
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002284350528"))

# Limits & filters
MIN_ODDS = float(os.getenv("MIN_ODDS", "1.20"))
MAX_LIVE_PICKS = int(os.getenv("MAX_LIVE_PICKS", "3"))

# Schedule settings
LIVE_INTERVAL_SECONDS = 3600       # hourly
DAILY_INTERVAL_HOURS = 12         # every 12 hours
WEEKLY_DAYS = 7
KASA_HOURS = 48

# DB path
DB_PATH = os.getenv("DB_PATH", "data.db")
