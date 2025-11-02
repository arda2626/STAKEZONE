import os

# ---------------- CONFIG (ENV) ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002284350528"))

# Tahmin filtreleri
MIN_ODDS = float(os.getenv("MIN_ODDS", 1.20))
MAX_LIVE_PICKS = 3

# Zaman ayarları
DAILY_INTERVAL_HOURS = 12
WEEKLY_DAYS = 7
KASA_HOURS = 48
