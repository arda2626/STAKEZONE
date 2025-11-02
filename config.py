import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
API_BASKETBALL_KEY = os.getenv("API_BASKETBALL_KEY")
API_TENNIS_KEY = os.getenv("API_TENNIS_KEY")
THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002284350528"))
DB_PATH = os.getenv("DB_PATH", "data.db")
MIN_ODDS = float(os.getenv("MIN_ODDS", "1.20"))
