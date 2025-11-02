# prediction.py
import random
from utils import ensure_min_odds, calc_form_score, combine_confidence, utcnow

NBA_PLAYERS = [
    "LeBron James","Stephen Curry","Jayson Tatum","Giannis Antetokounmpo",
    "Luka Doncic","Kevin Durant","Devin Booker","Nikola Jokic","Shai Gilgeous-Alexander"
]

def ai_for_match(ev):
    """
    ev: dict with keys: sport, league, home, away, stats(optional), recent(optional list)
    Returns: prediction dict {event_id, source, sport, league, home, away, bet, odds, prob}
    """
    sport = (ev.get("sport") or "").lower()
    home = ev.get("home") or ev.get("strHomeTeam") or "Home"
    away = ev.get("away") or ev.get("strAwayTeam") or "Away"
    event_id = ev.get("id") or ev.get("idEvent") or ev.get("strEvent")
    league = ev.get("league") or ev.get("strLeague") or "Unknown"

    # compute simple form scores
    home_hist = ev.get("home_recent") or []
    away_hist = ev.get("away_recent") or []
    home_form = calc_form_score(home_hist)
    away_form = calc_form_score(away_hist)
    base_conf = combine_confidence(home_form, away_form)

    # default odds
    odds = ensure_min_odds(ev.get("odds", 1.5))
    prob = ev.get("confidence", base_conf)

    # ---------------- FOOTBALL ----------------
    if "football" in sport or "soccer" in sport:
        avg_for_home = ev.get("home_avg_for") or random.uniform(0.7,1.6)
        avg_for_away = ev.get("away_avg_for") or random.uniform(0.6,1.5)
        avg_total = avg_for_home + avg_for_away

        if avg_total >= 2.6 and random.random() < 0.7:
            bet = "ÜST 2.5"
            odds = ensure_min_odds(1.4 + (avg_total-2.6)*0.5)
            prob = min(92, int(base_conf*0.7 + (avg_total-2.6)*20))
        elif avg_for_home>1.1 and avg_for_away>1.1 and random.random() < 0.5:
            bet = "KG VAR"
            odds = ensure_min_odds(1.55)
            prob = min(90, int(base_conf*0.65)+5)
        else:
            diff = home_form - away_form
            if diff > 8:
                bet = "Ev Sahibi Kazanır"
                prob = 70
            elif diff < -8:
                bet = "Deplasman Kazanır"
                prob = 70
            else:
                bet = random.choice(["Ev Sahibi Kazanır","Beraberlik","Deplasman Kazanır"])
                prob = random.randint(52,68)
            odds = ensure_min_odds(random.uniform(1.45,2.6))

        # ekstra fırsatlar
        if random.random() < 0.12:
            extra = random.choice(["1.5 ÜST","3.5 ÜST","Korner ÜST 8.5","Kart 3+"])
            bet = extra
            odds = ensure_min_odds(random.uniform(1.5,3.2))
            prob = int(base_conf*0.55)

        return {
            "event_id": str(event_id) if event_id else None,
            "source":"thesportsdb",
            "sport":"futbol",
            "league":league,
            "home":home,
            "away":away,
            "bet":bet,
            "odds":odds,
            "prob":prob
        }

    # ---------------- BASKETBALL / NBA ----------------
    if "basket" in sport or "nba" in sport:
        if random.random() < 0.35:
            player = random.choice(NBA_PLAYERS)
            bet = f"{player} 20+ Sayı"
            odds = ensure_min_odds(random.uniform(1.6,2.6))
            prob = min(92, int(base_conf*0.7)+5)
        else:
            if random.random() < 0.5:
                bet = random.choice(["Toplam ÜST 212.5","Toplam ALT 212.5","Ev Sahibi 110.5 ÜST"])
                odds = ensure_min_odds(random.uniform(1.45,2.4))
                prob = int(base_conf*0.6)
            else:
                bet = random.choice(["Ev Sahibi Kazanır","Deplasman Kazanır","İlk Yarı Ev 1","İlk Yarı Deplasman 2"])
                odds = ensure_min_odds(random.uniform(1.4,2.3))
                prob = int(base_conf*0.65)

        return {
            "event_id": str(event_id) if event_id else None,
            "source":"thesportsdb",
            "sport":"nba",
            "league":league,
            "home":home,
            "away":away,
            "bet":bet,
            "odds":odds,
            "prob":prob
        }

    # ---------------- TENNIS ----------------
    if "tennis" in sport or "atp" in sport or "wta" in sport:
        if random.random() < 0.45:
            bet = "Tie-break Var"
            odds = ensure_min_odds(random.uniform(1.8,3.2))
            prob = int(base_conf*0.55)
        else:
            bet = random.choice(["Toplam Oyun ÜST 22.5","1. Set 9.5 ÜST","Maç 3. Sete Gider","Favori Kazanır"])
            odds = ensure_min_odds(random.uniform(1.6,2.6))
            prob = int(base_conf*0.6)

        return {
            "event_id": str(event_id) if event_id else None,
            "source":"thesportsdb",
            "sport":"tenis",
            "league":league,
            "home":home,
            "away":away,
            "bet":bet,
            "odds":odds,
            "prob":prob
        }

    # ---------------- FALLBACK ----------------
    return {
        "event_id": str(event_id) if event_id else None,
        "source":"thesportsdb",
        "sport":sport or "unknown",
        "league":league,
        "home":home,
        "away":away,
        "bet":"1X2",
        "odds":odds,
        "prob":prob
    }
