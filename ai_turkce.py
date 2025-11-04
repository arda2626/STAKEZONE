from openai import OpenAI
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

async def ai_turkce_analiz(match_data: str) -> str:
    """
    Maç verisini alır, GPT-4o ile kısa Türkçe analiz döndürür.
    match_data: Örnek -> "Galatasaray vs Fenerbahçe - Son 5 maçta Galatasaray 4 galibiyet aldı."
    """
    try:
        prompt = f"""
        Sen bir spor analisti olarak hareket et.
        Aşağıda bir maç bilgisi var:
        {match_data}

        Bu maçı 2 cümleyi geçmeyecek şekilde Türkçe analiz et.
        Tahmin yapma, sadece veriye dayalı kısa bir gözlem yaz.
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Sen deneyimli bir Türk spor analistisin."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=40,
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("AI analiz hatası:", e)
        return "Analiz oluşturulamadı."
