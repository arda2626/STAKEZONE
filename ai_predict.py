# ai_predict.py
import aiohttp
import logging
from config import AI_API_KEY

log = logging.getLogger(__name__)

async def get_ai_prediction(match):
    """
    match: dict
    return: dict => {"suggestion": "MS1", "confidence": 70, "explanation": "..." }
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = f"Maç analizi yap ve tahmin ver: {match['home']} - {match['away']}"

    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 300
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=15) as resp:
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                # Örnek parse
                return {"suggestion": "MS1", "confidence": 70, "explanation": content}
    except Exception as e:
        log.warning(f"⚠️ AI tahmin hatası: {e}")
        return {"suggestion": "AI analiz hatası", "confidence": 0, "explanation": str(e)}
