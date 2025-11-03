# config.py
# --- DİKKAT ---
# "Env olarak yapma" demiştin; bu dosyaya API anahtarlarını koy.
# Deploy etmeden önce burayı kendi anahtarlarınla güncelle.

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"   # -> kendi token'ını buraya yapıştır
CHANNEL_ID = "@stakedrip"                                         # veya "-100..." channel id
API_FOOTBALL_KEY = "3838237ec41218c2572ce541708edcfd"             # -> kendi API-FOOTBALL key
THESPORTSDB_KEY = "457761c3fe3072466a8899578fefc5e4"              # optional fallback
DB_PATH = "data.db"

# Limits & tuning
MIN_ODDS = 1.2
MAX_LIVE_PICKS = 3
DAILY_INTERVAL_SECONDS = 3600 * 12   # 12 saatte bir günlük kupon
LIVE_INTERVAL_SECONDS = 3600         # saatlik canlı
RESULTS_CHECK_SECONDS = 300          # 5 dakika
WEEKLY_WINDOW_DAYS = 7
KASA_WINDOW_HOURS = 48

# Logging
LOG_LEVEL = "INFO"
