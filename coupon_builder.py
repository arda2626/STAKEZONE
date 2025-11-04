# coupon_builder.py
import logging
import random
log = logging.getLogger(__name__)

async def build_coupon(matches, title="CANLI AI TAHMİN", max_matches=5):
    if not matches:
        return None

    coupon_text = f"━━━━━━━━━━━\n{title}\n━━━━━━━━━━━\n"
    # En fazla max_matches kadar maç seç
    selected = sorted(matches, key=lambda x: x['date'])[:max_matches]

    for m in selected:
        home = m['home']
        away = m['away']
        date = m['date']
        # AI tahmin örnek (gerçek AI API çağırılacak)
        try:
            prediction = {"suggestion": "MS 1", "confidence": 70}  # Burada AI çağır
            suggestion = prediction.get("suggestion", "AI Hata")
            confidence = prediction.get("confidence", 0)
        except:
            suggestion = "AI Hata"
            confidence = 0

        # Oran ekle (varsa)
        odds = m.get("odds", {})
        odd_text = ""
        if odds:
            odd_val = odds.get("1") or odds.get("home") or 1.5
            odd_text = f" | Oran: {odd_val}"

        coupon_text += f"⚽ {home} - {away}\n{date}\n{suggestion} (%{confidence}){odd_text}\n\n"

    return coupon_text
