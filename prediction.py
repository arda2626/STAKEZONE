# prediction.py
# Single entry ai_predict(match) that returns consistent dict:
# { "id","home","away","sport","league","bet","odds","confidence","prob" }

import random
from utils import ensure_min_odds, calc_form_score

NBA_PLAYERS = ["LeBron James","Stephen Curry","Jayson Tatum","Giannis Antetokounmpo","Luka Doncic","Kevin Durant","Devin Booker","Nikola Jokic","Shai Gilgeous-Alexander"]

def ai_predict(ev: dict) -> dict:
    """
    ev: match dict with keys home, away, sport, league, start_time, minute, raw
    returns prediction dict
    """
    sport_raw = (ev.get("sport") or "").lower()
    home = ev.get("home") or ev.get("strHomeTeam") or ev.get("homeTeam")
    away = ev.get("away") or ev.get("strAwayTeam") or ev.get("awayTeam")
    league = ev.get("league") or ev.get("strLeague") or ""
    event_id = ev.get("id") or ev.get("idEvent")

    # naive form estimates from any provided 'form' keys
    home_hist = ev.get("home_recent") or ev.get("form_home") or []
    away_hist = ev.get("away_recent") or ev.get("form_away") or []
    hf = calc_form_score(home_hist)
    af = calc_form_score(away_hist)
    base_conf = (hf + (1-af)) / 2  # crude: higher home form + lower away gives higher

    # choose bet depending on sport
    if "football" in sport_raw or "soccer" in sport_raw or sport_raw == "futbol":
        avg_for_home = ev.get("home_avg_for") or random.uniform(0.7,1.6)
        avg_for_away = ev.get("away_avg_for") or random.uniform(0.6,1.5)
        avg_total = avg_for_home + avg_for_away
        if avg_total >= 2.6 and random.random() < 0.8:
            bet = "ÜST 2.5"
            odds = ensure_min_odds(1.4 + (avg_total-2.6)*0.5)
            prob = min(92, int(60 + (avg_total-2.6)*18))
            confidence = min(0.95, 0.65 + (avg_total-2.6)*0.1)
        elif avg_for_home>1.1 and avg_for_away>1.1 and random.random() < 0.6:
            bet = "KG VAR"
            odds = ensure_min_odds(1.55)
            prob = 68
            confidence = 0.68
        else:
            # 1X2
            diff = hf - af
            if diff > 0.12:
                bet = "Ev Sahibi Kazanır"
                prob = 68 + int(diff*30)
            elif diff < -0.12:
                bet = "Deplasman Kazanır"
                prob = 68 + int(-diff*30)
            else:
                bet = random.choice(["Ev Sahibi Kazanır","Beraberlik","Deplasman Kazanır"])
                prob = random.randint(52,68)
            odds = ensure_min_odds(random.uniform(1.45,2.6))
            confidence = min(0.92, 0.55 + prob/200)

        # sometimes corners/cards/1.5/3.5
        if random.random() < 0.12:
            extra = random.choice(["1.5 ÜST","3.5 ÜST","Korner ÜST 8.5","Kart 3+"])
            bet = extra
            odds = ensure_min_odds(random.uniform(1.5,3.2))
            prob = int(prob*0.7)
            confidence = max(0.5, confidence*0.8)

        return {
            "id": event_id, "home": home, "away": away, "sport":"futbol", "league": league,
            "bet": bet, "odds": round(odds,2), "prob": prob, "confidence": round(confidence,2)
        }

    if "basket" in sport_raw or "nba" in sport_raw:
        if random.random() < 0.35:
            player = random.choice(NBA_PLAYERS)
            bet = f"{player} 20+ Sayı"
            odds = ensure_min_odds(random.uniform(1.6,2.6))
            prob = random.randint(60,88)
            confidence = 0.6 + prob/300
        else:
            bet = random.choice(["Toplam Sayı ÜST 212.5","Toplam Sayı ALT 212.5","Ev Sahibi Kazanır"])
            odds = ensure_min_odds(random.uniform(1.45,2.4))
            prob = int(55 + random.random()*30)
            confidence = 0.55 + prob/200
        return {"id": event_id, "home":home, "away":away, "sport":"nba", "league":league, "bet":bet, "odds":round(odds,2), "prob":prob, "confidence":round(confidence,2)}

    if "tennis" in sport_raw or "atp" in sport_raw or "wta" in sport_raw:
        if random.random() < 0.45:
            bet = "Tie-break Var"
            odds = ensure_min_odds(random.uniform(1.8,3.2))
            prob = random.randint(55,78)
        else:
            bet = random.choice(["Toplam Oyun ÜST 22.5","1. Set 9.5 ÜST","Maç 3. Sete Gider","Favori Kazanır"])
            odds = ensure_min_odds(random.uniform(1.6,2.6))
            prob = random.randint(55,82)
        confidence = 0.5 + prob/200
        return {"id": event_id, "home":home, "away":away, "sport":"tenis", "league":league, "bet":bet, "odds":round(odds,2), "prob":prob, "confidence":round(confidence,2)}

    # fallback generic
    odds = ensure_min_odds(ev.get("odds",1.5))
    prob = random.randint(55,75)
    conf = 0.5 + prob/200
    return {"id": event_id, "home":home, "away":away, "sport": ev.get("sport","unknown"), "league":league, "bet":"Favori Kazanır", "odds":odds, "prob":prob, "confidence":round(conf,2)}
