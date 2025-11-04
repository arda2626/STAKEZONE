# coupon.py
import logging
from datetime import datetime
from ai_predict import ai_predict
from odds import fetch_odds

log = logging.getLogger(__name__)

async def build_coupon(matches):
    odds_data = await fetch_odds()
    coupon_text = "━━━━━━━━━━━\nCANLI AI TAHMİN\n━━━━━━━━━━━\n"
    for m in matches:
        # Tarih formatlama
        match_time = datetime.fromisoformat(m["date"]).strftime("%H:%M")
        # AI tahmini
        ai_result = await ai_predict(m)
        # Oran
        odds = odds_data.get(m["id"], [])
        ms_odds = odds[0]["outcomes"][0]["price"] if odds else "-"
        coupon_text += f"⚽ {m['home']} - {m['away']}\n{match_time}\n{ai_result['suggestion']} ({ai_result['confidence']}%) - Oran: {ms_odds}\n"
        coupon_text += f"{ai_result['explanation']}\n\n"
    return coupon_text
