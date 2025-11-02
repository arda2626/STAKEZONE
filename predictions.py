# prediction.py
import random
from utils import EMOJI

NBA_PLAYERS = ["LeBron James","Stephen Curry","Jayson Tatum","Giannis Antetokounmpo","Luka Doncic",
               "Kevin Durant","Devin Booker","Nikola Jokic","Shai Gilgeous-Alexander"]

def generate_prediction(sport="futbol"):
    if sport == "futbol":
        choices = ["1", "X", "2", "KG", "ÜST", "ALT"]
    elif sport in ["nba","basketball"]:
        choices = ["1", "2", "ÜST", "ALT", f"{random.choice(NBA_PLAYERS)} 20+ Sayı"]
    elif sport in ["tenis","atp","wta"]:
        choices = ["1", "2", "ÜST", "ALT","Tie-break Var"]
    else:
        choices = ["1", "X", "2"]
    
    prediction = random.choice(choices)
    odds = round(random.uniform(1.50, 2.50), 2)
    return {"prediction": prediction, "odds": odds, "sport": sport}
