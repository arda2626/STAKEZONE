import random

def generate_prediction(match):
    sport = match["sport"]
    if sport == "Soccer":
        outcomes = ["1", "X", "2", "Alt", "Üst", "KG Var"]
    elif sport == "Basketball":
        outcomes = ["1", "2", "Alt", "Üst", "Handikap"]
    elif sport == "Tennis":
        outcomes = ["1", "2", "Alt", "Üst", "Tiebreak"]
    else:
        outcomes = ["1", "2"]
    
    return random.choice(outcomes)
