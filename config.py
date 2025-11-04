# config.py
import os

# Sadece AI Key env olarak
AI_KEY = os.getenv("AI_KEY", "")

# Sabit API anahtarları
API_KEYS = {
    "API_FOOTBALL": "bd1350bea151ef9f56ed417f0c0c3ea2",
    "THE_ODDS_API": "501ea1ade60d5f0b13b8f34f90cd51e6",
    "FOOTYSTATS": "test85g57",
    "ALLSPORTSAPI": "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369",
    "SPORTSMONKS": "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ",
    "ISPORTSAPI": "rCiLp0QXNSrfV5oc"
}

# Lokal saat farkı
TIME_DELTA = 3  # UTC+3 Türkiye
