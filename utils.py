# ================== utils.py — STAKEDRIP AI ULTRA v5.5 ==================
import random
import sqlite3
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
        return "🔥 Çok Yüksek Güven"
    elif probability >= 0.70:
        return "💪 Yüksek Güven"
    elif probability >= 0.55:
        return "⚙️ Orta Güven"
    else:
        return "⚠️ Düşük Güven"

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

# ================== VERİ TABANI ==================
def init_db(path=None):
    conn = sqlite3.connect("stakedrip.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home TEXT,
            away TEXT,
            prediction TEXT,
            confidence REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialized: stakedrip.db")

def mark_prediction(prediction_id: str, status: str):
    conn = sqlite3.connect("stakedrip.db")
    cur = conn.cursor()
    cur.execute("UPDATE predictions SET status=? WHERE id=?", (status, prediction_id))
    conn.commit()
    conn.close()
    print(f"[DB] Tahmin #{prediction_id} sonucu güncellendi: {status}")

def get_pending_predictions():
    conn = sqlite3.connect("stakedrip.db")
    cur = conn.cursor()
    cur.execute("SELECT id, home, away, prediction, confidence FROM predictions WHERE status='pending'")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "home": r[1], "away": r[2], "prediction": r[3], "confidence": r[4]} for r in rows]

# ================== GÜNLÜK RAPOR & TEKRAR KONTROL ==================
def is_duplicate_match(home, away, hours=24):
    """Aynı maç 24 saat içinde zaten eklendiyse True döndürür."""
    conn = sqlite3.connect("stakedrip.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM predictions 
        WHERE home=? AND away=? 
        AND created_at >= datetime('now', ?)
    """, (home, away, f'-{hours} hours'))
    exists = cur.fetchone()[0] > 0
    conn.close()
    return exists

def day_summary():
    """Günün genel başarı oranını hesaplar."""
    conn = sqlite3.connect("stakedrip.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT status, COUNT(*) FROM predictions
        WHERE DATE(created_at) = DATE('now')
        GROUP BY status
    """)
    stats = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    total = sum(stats.values())
    won = stats.get("won", 0)
    rate = (won / total) * 100 if total else 0
    return f"📅 Gün Sonu Özeti: {won}/{total} kazandı • Başarı Oranı: %{rate:.1f}"

# ================== RASTGELE MESAJ ==================
def random_ai_message() -> str:
    phrases = [
        "Veriler analiz ediliyor...",
        "Yapay zeka tahmin motoru aktif 🤖",
        "Maç verileri değerlendiriliyor 🔍",
        "Yeni istatistikler işleniyor 📊",
        "Son form ve oranlar inceleniyor ⚙️",
    ]
    return random.choice(phrases)
