# prediction.py — KORNER + KART + GOL TAHMİN
import aiohttp, random

async def get_team_stats(team):
    # FootyStats ücretsiz endpoint (gerçek veri)
    url = f"https://api.footystats.org/team-stats?key=example_key&team={team}"
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(url) as r:
                if r.status == 200:
                    data = await r.json()
                    return {
                        "avg_corners": data.get("avg_corners_total", 10.5),
                        "avg_cards": data.get("avg_cards_total", 4.2),
                        "ppda": data.get("ppda", 11.0)
                    }
        except: pass
    # Yedek ortalama
    return {"avg_corners": 10.5, "avg_cards": 4.2, "ppda": 11.0}

def ai_predict(match):
    home, away = match["home"], match["away"]
    h_stats = asyncio.run(get_team_stats(home))
    a_stats = asyncio.run(get_team_stats(away))

    total_corners = (h_stats["avg_corners"] + a_stats["avg_corners"])
    total_cards = (h_stats["avg_cards"] + a_stats["avg_cards"])

    # Korner tahmin
    corner_bet = "KORNER ÜST 9.5" if total_corners > 10 else "KORNER ALT 9.5"
    corner_conf = min(0.95, 0.6 + (total_corners - 9) * 0.05)

    # Kart tahmin
    card_bet = "KART ÜST 3.5" if total_cards > 4.0 else "KART ALT 3.5"
    card_conf = min(0.92, 0.6 + (total_cards - 3.5) * 0.06)

    # Gol (xG yedeği)
    goal_bet = "ÜST 2.5" if total_corners > 11 else "ALT 2.5"
    goal_conf = 0.75

    return {
        "main_bet": goal_bet,
        "corner_bet": corner_bet,
        "card_bet": card_bet,
        "confidence": max(goal_conf, corner_conf, card_conf),
        "corner_avg": round(total_corners, 1),
        "card_avg": round(total_cards, 1),
        **match
    }
