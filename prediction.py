# prediction.py — STAKEDRIP AI ULTRA v5.4
import random
from utils import ensure_min_odds, calc_form_score

NBA_PLAYERS = ["LeBron James","Stephen Curry","Jayson Tatum","Giannis Antetokounmpo","Luka Doncic",
               "Kevin Durant","Devin Booker","Nikola Jokic","Shai Gilgeous-Alexander"]

def ai_predict(ev: dict) -> dict:
    sport_raw = (ev.get("sport") or "").lower()
    home = ev.get("home") or ev.get("strHomeTeam") or ev.get("homeTeam") or "Ev Sahibi"
    away = ev.get("away") or ev.get("strAwayTeam") or ev.get("awayTeam") or "Deplasman"
    league = ev.get("league") or ev.get("strLeague") or "Bilinmeyen Lig"
    event_id = ev.get("id") or ev.get("idEvent") or f"{home}_{away}_{random.randint(1000,9999)}"

    # Form
    hf = calc_form_score(ev.get("home_recent") or ev.get("form_home") or [])
    af = calc_form_score(ev.get("away_recent") or ev.get("form_away") or [])
    base_conf = min(0.95, max(0.5, (hf + (1-af))/2))

    # --- Futbol / Soccer ---
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

        # Extra bets
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

    # --- Basket / NBA ---
    if "basket" in sport_raw or "nba" in sport_raw:
        if random.random() < 0.35:
            player = random.choice(NBA_PLAYERS)
            bet = f"{player} 20+ Sayı"
            odds = ensure_min_odds(random.uniform(1.6,2.6))
            prob = random.randint(60,88)
            confidence = min(0.95, 0.6 + prob/300)
        else:
            bet = random.choice(["Toplam Sayı ÜST 212.5","Toplam Sayı ALT 212.5","Ev Sahibi Kazanır"])
            odds = ensure_min_odds(random.uniform(1.45,2.4))
            prob = int(55 + random.random()*30)
            confidence = min(0.92, 0.55 + prob/200)
        return {"id": event_id, "home":home, "away":away, "sport":"nba", "league":league, "bet":bet, "odds":round(odds,2), "prob":prob, "confidence":round(confidence,2)}

    # --- Tennis ---
    if "tennis" in sport_raw or "atp" in sport_raw or "wta" in sport_raw:
        if random.random() < 0.45:
            bet = "Tie-break Var"
            odds = ensure_min_odds(random.uniform(1.8,3.2))
            prob = random.randint(55,78)
        else:
            bet = random.choice(["Toplam Oyun ÜST 22.5","1. Set 9.5 ÜST","Maç 3. Sete Gider","Favori Kazanır"])
            odds = ensure_min_odds(random.uniform(1.6,2.6))
            prob = random.randint(55,82)
        confidence = min(0.95, 0.5 + prob/200)
        return {"id": event_id, "home":home, "away":away, "sport":"tenis", "league":league, "bet":bet, "odds":round(odds,2), "prob":prob, "confidence":round(confidence,2)}

    # --- Generic fallback ---
    odds = ensure_min_odds(ev.get("odds",1.5))
    prob = random.randint(55,75)
    conf = min(0.95, 0.5 + prob/200)
    return {"id": event_id, "home":home, "away":away, "sport": ev.get("sport","unknown"), "league":league, "bet":"Favori Kazanır", "odds":round(odds,2), "prob":prob, "confidence":round(conf,2)}
