# coupon_builder.py
import asyncio
from fetch_matches import fetch_all_matches
from ai_predict import get_ai_prediction
import logging
from datetime import datetime

log = logging.getLogger(__name__)

async def build_coupon():
    matches = await fetch_all_matches()
    if not matches:
        return "❌ Maç bulunamadı."

    txt = "━━━━━━━━━━━\nCANLI AI TAHMİN\n━━━━━━━━━━━\n"
    for m in matches[:5]:  # Örnek: ilk 5 maç
        pred = await get_ai_prediction(m)
        match_time = datetime.fromisoformat(m["date"]).strftime("%H:%M")
        txt += f"⚽ {m['home']} - {m['away']}\n"
        txt += f"{match_time}\n"
        txt += f"{pred['suggestion']} (%{pred['confidence']})\n"
        txt += f"{pred['explanation']}\n\n"
    return txt
