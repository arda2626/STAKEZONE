# ai_predict.py
import json
import logging

log = logging.getLogger(__name__)

async def ai_predict(match):
    try:
        # örnek: AI API çağrısı, yanıt txt
        txt = '{"suggestion": "MS1", "confidence": 70, "explanation": "Tahmin başarılı"}'
        result = json.loads(txt)
        if not isinstance(result, dict):
            raise ValueError("AI yanıtı dict değil")
        return {
            "suggestion": result.get("suggestion", "Hata"),
            "confidence": result.get("confidence", 0),
            "explanation": result.get("explanation", "")
        }
    except Exception as e:
        log.warning(f"⚠️ AI tahmin hatası: {e}")
        return {"suggestion": "Hata", "confidence": 0, "explanation": str(e)}
