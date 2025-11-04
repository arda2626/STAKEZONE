import os
import asyncio
import json
from openai import AsyncOpenAI

# OpenAI istemcisi
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Ana analiz fonksiyonu
async def ai_turkce_analiz(match):
    """
    Verilen maç için Türkçe AI tahmini oluşturur.
    """
    try:
        # Rate limit hatalarına karşı kısa bekleme
        await asyncio.sleep(10)

        home = match.get("home", "Ev Sahibi")
        away = match.get("away", "Deplasman")
        sport = match.get("sport", "futbol")

        prompt = (
            f"{sport.capitalize()} maçı için kısa, istatistiksel ve tahmin odaklı bir analiz üret. "
            f"Maç: {home} vs {away}. "
            f"Sadece 2-3 cümlelik bir Türkçe açıklama yaz. "
            f"Sonuç olarak en olası bahis türünü (örnek: KG VAR, ÜST, 1X, 2) belirt. "
            f"JSON formatında yanıt ver:\n\n"
            f'{{"suggestion": "Tahmin", "confidence": "Yüzde", "explanation": "Kısa açıklama"}}'
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )

        content = response.choices[0].message.content.strip()

        # Yanıt JSON formatında mı kontrol et
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # JSON değilse düz metinden parçala
            data = {
                "suggestion": "AI yanıt parse edilemedi",
                "confidence": 50,
                "explanation": content,
            }

        return data

    except Exception as e:
        err = str(e).lower()

        # Rate limit hatası
        if "rate limit" in err or "rpm" in err:
            return {
                "suggestion": "⚠️ AI analiz sınırına ulaşıldı",
                "confidence": 0,
                "explanation": "Lütfen birkaç dakika sonra tekrar deneyin.",
            }

        # Diğer hatalar
        return {
            "suggestion": "AI analiz hatası",
            "confidence": 0,
            "explanation": f"Hata: {str(e)[:120]}",
        }
