# ================== prediction.py — STAKEDRIP AI ULTRA v5.0+ ==================
import random

def generate_prediction(match):
    sport = match.get("sport", "football")
    home = match.get("home", "")
    away = match.get("away", "")

    # Basit model: spora göre rastgele tahmin varyasyonları
    if sport == "football":
        picks = ["2.5 ALT", "2.5 ÜST", "KG VAR", "KG YOK", "1", "2", "X"]
    elif sport == "basketball":
        picks = ["ÜST 170.5", "ALT 160.5", "1", "2"]
    elif sport == "tennis":
        picks = ["SET 2-0", "SET 2-1", "TOPLAM OYUN 22.5 ÜST", "TOPLAM OYUN ALT"]
    else:
        picks = ["1", "2"]

    prediction = random.choice(picks)
    confidence = round(random.uniform(0.7, 0.95), 2)
    odds = round(random.uniform(1.4, 2.5), 2)

    return {
        **match,
        "prediction": prediction,
        "confidence": confidence,
        "odds": odds
    }
