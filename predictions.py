import random
from utils import EMOJI

# ================== ÖRNEK PREDİKSİYON ÜRET ==================
def generate_prediction(sport="futbol"):
    """
    sport: futbol, nba, tenis
    """
    if sport == "futbol":
        choices = ["1", "2", "X", "KG", "Üst", "Alt"]
    elif sport == "nba" or sport == "basketball":
        choices = ["1", "2", "Üst", "Alt"]
    elif sport == "tenis":
        choices = ["1", "2", "Üst", "Alt"]
    else:
        choices = ["1", "2", "X"]
    
    prediction = random.choice(choices)
    odds = round(random.uniform(1.50, 2.50), 2)
    return {"prediction": prediction, "odds": odds, "sport": sport}
