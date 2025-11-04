# ai_predict.py
import aiohttp
import logging
from config import AI_API

log = logging.getLogger(__name__)

async def get_ai_prediction(home, away, date):
    try:
        prompt = f"{home} vs {away} maçı için canlı tahmin ver. Oran, % başarı ve kısa açıklama dahil et."
        url = "https://api.ai-service.com/predict"
        headers = {"Authorization": f"Bearer {AI_API}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"prompt": prompt}, headers=headers, timeout=15) as resp:
                data = await resp.json()
                return {
                    "home": home,
                    "away": away,
                    "date": date,
                    "prediction": data.get("prediction", "Bilinmiyor"),
                    "confidence": data.get("confidence", 0),
                    "odds": data.get("odds", "1.0")
                }
    except Exception as e:
        log.warning(f"⚠️ AI tahmin hatası: {e}")
        return {"home": home, "away": away, "date": date, "prediction": "Hata", "confidence": 0, "odds": "1.0"}
