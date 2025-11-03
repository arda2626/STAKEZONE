# ================== utils.py — STAKEDRIP AI ULTRA v5.2 ==================
import random
from datetime import datetime, timezone

# ================== EMOJİ VE SİMGELER ==================
EMOJI = {
    "goal": "⚽",
    "win": "✅",
    "lose": "❌",
    "draw": "🤝",
    "clock": "⏱️",
    "fire": "🔥",
    "ai": "🤖",
    "star": "⭐",
    "trend": "📈",
    "earth": "🌍",
    "light": "💡",
}

EMOJI_MAP = {
    "Over 2.5": "🔥",
    "Under 2.5": "🧊",
    "BTTS": "⚽⚽",
    "Home Win": "🏠✅",
    "Away Win": "✈️✅",
    "Draw": "🤝",
}

# ================== LİG BAYRAKLARI ==================
LEAGUE_FLAGS = {
    "England": "🏴",
    "Germany": "🇩🇪",
    "Spain": "🇪🇸",
    "Italy": "🇮🇹",
    "France": "🇫🇷",
    "Turkey": "🇹🇷",
    "Portugal": "🇵🇹",
    "Netherlands": "🇳🇱",
    "Belgium": "🇧🇪",
    "Brazil": "🇧🇷",
    "Argentina": "🇦🇷",
    "USA": "🇺🇸",
    "Japan": "🇯🇵",
    "Korea Republic": "🇰🇷",
    "Scotland": "🏴",
    "Norway": "🇳🇴",
    "Sweden": "🇸🇪",
    "Greece": "🇬🇷",
    "Denmark": "🇩🇰",
    "Switzerland": "🇨🇭",
    "Austria": "🇦🇹",
    "Croatia": "🇭🇷",
    "Serbia": "🇷🇸",
    "Russia": "🇷🇺",
    "Poland": "🇵🇱",
    "Romania": "🇷🇴",
    "Czech Republic": "🇨🇿",
    "Hungary": "🇭🇺",
}

def league_to_flag(country_name: str) -> str:
    """Ülke adına göre bayrak döndürür."""
    return LEAGUE_FLAGS.get(country_name, "🌍")

# ================== ZAMAN ==================
def utcnow():
    """UTC zamanını döndürür."""
    return datetime.now(timezone.utc)

# ================== ORAN VE FORM HESAPLAMALARI ==================
def ensure_min_odds(odds: float, minimum: float = 1.40) -> float:
    """Oran çok düşükse minimum değere yuvarla."""
    return max(odds, minimum)

def calc_form_score(form_string: str) -> float:
    """Takım formunu puanlar (W=1, D=0.5, L=0)."""
    if not form_string:
        return 0
    form = form_string.upper()
    return form.count("W") + 0.5 * form.count("D")

# ================== GÜVEN SEVİYESİ ==================
def confidence_score(probability: float) -> str:
    """AI tahmini güven seviyesini Türkçe olarak döndürür."""
    if probability >= 0.85:
        return "Çok Yüksek Güven 🔥"
    elif probability >= 0.70:
        return "Yüksek Güven 💪"
    elif probability >= 0.55:
        return "Orta Seviye ⚙️"
    else:
        return "Düşük Güven ⚠️"

# ================== BANNER YARDIMCISI ==================
def format_prediction_line(match):
    """Maç verilerini banner'a uygun biçimde düzenler."""
    flag = league_to_flag(match.get("country", ""))
    minute = f"{EMOJI['clock']} {match.get('minute', '—')}'"
    prediction = match.get("prediction", "—")
    emoji = EMOJI_MAP.get(prediction, "💡")
    confidence = confidence_score(match.get("confidence", 0.7))
    home = match.get("home", "Ev Sahibi")
    away = match.get("away", "Deplasman")

    return f"{flag} {minute} | {home} vs {away} | {emoji} {prediction} | {confidence}"

# ================== GENEL BANNER ==================
def banner(title: str, matches: list) -> str:
    """Maç listesini üst başlıkla banner haline getirir."""
    if not matches:
        return f"{EMOJI['ai']} {title}\nVeri bulunamadı ⏳"

    lines = [f"{EMOJI['ai']} {title}", "━━━━━━━━━━━━━━━"]
    for m in matches:
        lines.append(format_prediction_line(m))
    return "\n".join(lines)

# ================== RASTGELE AI MESAJI ==================
def random_ai_message() -> str:
    """AI tarafından rastgele mesaj üretir."""
    phrases = [
        "Veriler analiz ediliyor...",
        "Yapay zeka modeli güncelleniyor 🤖",
        "Yeni istatistikler taranıyor 📊",
        "Tahmin motoru çalışıyor ⚙️",
        "Maç verileri değerlendiriliyor 🔍",
    ]
    return random.choice(phrases)
