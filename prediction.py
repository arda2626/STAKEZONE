# prediction.py
import aiohttp, asyncio, random

async def get_team_stats(t):
    return {"avg_corners": round(random.uniform(9,13),1), "avg_cards": round(random.uniform(3,6),1)}

async def ai_predict(m):
    h, a = m["home"], m["away"]
    hs, a_s = await asyncio.gather(get_team_stats(h), get_team_stats(a))
    tc = hs["avg_corners"] + a_s["avg_corners"]
    tk = hs["avg_cards"] + a_s["avg_cards"]
    return {
        "main_bet": "ÜST 2.5" if tc > 11 else "ALT 2.5",
        "corner_bet": "KORNER ÜST 9.5" if tc > 10 else "KORNER ALT 9.5",
        "card_bet": "KART ÜST 3.5" if tk > 4 else "KART ALT 3.5",
        "corner_avg": round(tc,1),
        "card_avg": round(tk,1),
        "confidence": round(0.6 + (tc-9)*0.03 + (tk-3.5)*0.04, 2),
        **m
    }
