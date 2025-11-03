# prediction.py
import random

def ai_predict(match):
    bets = ["ÜST 2.5", "ALT 2.5", "KG VAR", "Home Win", "Away Win"]
    return {
        "bet": random.choice(bets),
        "confidence": random.uniform(0.5, 0.95),
        **match
    }
