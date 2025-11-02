import random
from utils import EMOJI, utcnow

NBA_PLAYERS = ["LeBron James","Stephen Curry","Jayson Tatum","Giannis Antetokounmpo","Luka Doncic","Kevin Durant","Devin Booker","Nikola Jokic","Shai Gilgeous-Alexander"]

MIN_ODDS = 1.20

def ensure_min_odds(x):
    return max(round(x,2), MIN_ODDS)

async def make_prediction(ev):
    sport = ev.get("sport")
    home = ev.get("home")
    away = ev.get("away")
    event_id = ev.get("id")
    league = ev.get("league","")

    if sport=="futbol":
        bet = random.choice(["Ev Sahibi Kazanır","Beraberlik","Deplasman Kazanır","ÜST 2.5","KG VAR"])
        odds = ensure_min_odds(random.uniform(1.2,2.5))
        prob = random.randint(55,92)
    elif sport=="nba":
        bet = random.choice(["Maç Sonucu","Toplam ÜST 212.5","Q1 ÜST 54.5", f"{random.choice(NBA_PLAYERS)} 20+ Sayı"])
        odds = ensure_min_odds(random.uniform(1.2,2.6))
        prob = random.randint(60,90)
    elif sport=="tenis":
        bet = random.choice(["Maç Sonucu","Toplam Oyun ÜST 22.5","Tie-break Var"])
        odds = ensure_min_odds(random.uniform(1.2,3.2))
        prob = random.randint(55,85)
    else:
        return None

    return {"event_id": str(event_id), "source":"tsdb","sport":sport,"league":league,"home":home,"away":away,"bet":bet,"odds":odds,"prob":prob}
