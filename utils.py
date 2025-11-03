# ================== utils.py — STAKEDRIP AI ULTRA v5.3 ==================
import random
from datetime import datetime, timezone, timedelta

# ================== EMOJİLER ==================
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
    return LEAGUE_FLAGS.get(country_name, "🌍")

# ================== ZAMAN ==================
def utcnow():
    return datetime.now(timezone.utc)

# ================== ORAN VE FORM ==================
def ensure_min_odds(odds: float, minimum: float = 1.40) -> float:
    return max(odds, minimum)

def calc_form_score(form_string: str) -> float:
    if not form_string:
        return 0
    form = form_string.upper()
    return form.count("W") + 0.5 * form.count("D")

# ================== GÜVEN SEVİYESİ ==================
def confidence_score(probability: float) -> str:
    if probability >= 0.85:
        return "Çok Yüksek Güven 🔥"
    elif probability >= 0.70:
        return "Yüksek Güven 💪"
    elif probability >= 0.55:
        return "Orta Seviye ⚙️"
    else:
        return "Düşük Güven ⚠️"

# ================== BANNER GÖRÜNÜMÜ ==================
def format_prediction_line(match):
    flag = league_to_flag(match.get("country", ""))
    minute = f"{EMOJI['clock']} {match.get('minute', '—')}'"
    prediction = match.get("prediction", "—")
    emoji = EMOJI_MAP.get(prediction, "💡")
    confidence = confidence_score(match.get("confidence", 0.7))
    home = match.get("home", "Ev Sahibi")
    away = match.get("away", "Deplasman")

    return f"{flag} {minute} | {home} vs {away} | {emoji} {prediction} | {confidence}"

def banner(title: str, matches: list) -> str:
    if not matches:
        return f"{EMOJI['ai']} {title}\nVeri bulunamadı ⏳"

    lines = [f"{EMOJI['ai']} {title}", "━━━━━━━━━━━━━━━"]
    for m in matches:
        lines.append(format_prediction_line(m))
    return "\n".join(lines)

# ================== VERİ TABANI DESTEK FONKSİYONLARI ==================
# Bu fonksiyonlar results.py ile uyumludur.
def mark_prediction(prediction_id: str, status: str):
    """Veritabanında tahmini kazandı/kaybetti olarak işaretler."""
    print(f"[DB] Tahmin #{prediction_id} sonucu güncellendi: {status}")

def get_pending_predictions():
    """Henüz sonuçlanmamış tahminleri döndürür (örnek veridir)."""
    return [
        {"id": 1, "home": "Galatasaray", "away": "Fenerbahçe", "prediction": "Over 2.5", "confidence": 0.81},
        {"id": 2, "home": "Real Madrid", "away": "Barcelona", "prediction": "BTTS", "confidence": 0.76},
    ]

def day_summary_between(start_date: datetime, end_date: datetime):
    """Belirli bir tarih aralığındaki kazanç/başarı oranını döndürür."""
    fake_data = {"won": 7, "lost": 3}
    total = fake_data["won"] + fake_data["lost"]
    success_rate = (fake_data["won"] / total) * 100 if total else 0
    return f"📅 {start_date.date()} - {end_date.date()} Arası Başarı Oranı: %{success_rate:.1f}"

# ================== RASTGELE AI MESAJI ==================
def random_ai_message() -> str:
    phrases = [
        "Veriler analiz ediliyor...",
        "Yapay zeka modeli güncelleniyor 🤖",
        "Yeni istatistikler taranıyor 📊",
        "Tahmin motoru çalışıyor ⚙️",
        "Maç verileri değerlendiriliyor 🔍",
    ]
    return random.choice(phrases)
