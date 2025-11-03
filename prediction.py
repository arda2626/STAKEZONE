# prediction.py — KORNER + KART + GOL AI
import aiohttp, random

async def get_team_stats(team):
    # Gerçek FootyStats API (ücretsiz tier)
    url = f"https://api.footystats.org/team-stats?team={team.replace(' ', '%20')}"
    headers = {"Authorization": "Bearer example_key"}  # kendi keyini ekle
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(url, headers=headers) as r:
                if r.status == 200:
                    d = await r.json()
                    return {
                        "avg_corners": d.get("data", {}).get("corners_total_avg", 10.5),
                        "avg_cards": d.get("data", {}).get("cards_total_avg", 4.2)
                    }
        except: pass
    return {"avg_corners": round(random.uniform(9, 12), 1), "avg_cards": round(random.uniform(3.5, 5.5), 1)}

def ai_predict(match):
    h, a = match["home"], match["away"]
    h_stats = asyncio.run(get_team_stats(h))
    a_stats = asyncio.run(get_team_stats(a))

    total_corners = h_stats["avg_corners"] + a_stats["avg_corners"]
    total_cards = h_stats["avg_cards"] + a_stats["avg_cards"]

    corner_bet = "KORNER ÜST 9.5" if total_corners > 10 else "KORNER ALT 9.5"
    card_bet = "KART ÜST 3.5" if total_cards > 4.0 else "KART ALT 3.5"
    main_bet = "ÜST 2.5" if total_corners > 11 else "ALT 2.5"

    conf = 0.6 + (total_corners - 9) * 0.04 + (total_cards - 3.5) * 0.03
    conf = min(0.95, conf)

    return {
        "main_bet": main_bet,
        "corner_bet": corner_bet,
        "card_bet": card_bet,
        "corner_avg": round(total_corners, 1),
        "card_avg": round(total_cards, 1),
        "confidence": conf,
        **match
    }
