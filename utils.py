# ================== utils.py — STAKEDRIP AI ULTRA v5.1 ==================
import math

# ============ EMOJİLER ============ #
EMOJI = {
    "live": "🔴",
    "cash": "💰",
    "chart": "📊",
    "fire": "🔥",
    "lock": "🔒",
    "star": "⭐",
    "vs": "⚡",
    "clock": "⏱️",
    "flag": "🏳️",
}

# Lig -> Bayrak Eşleştirmesi
LEAGUE_FLAGS = {
    "england": "🏴",
    "turkey": "🇹🇷",
    "spain": "🇪🇸",
    "germany": "🇩🇪",
    "italy": "🇮🇹",
    "france": "🇫🇷",
    "netherlands": "🇳🇱",
    "portugal": "🇵🇹",
    "usa": "🇺🇸",
    "brazil": "🇧🇷",
    "argentina": "🇦🇷",
    "belgium": "🇧🇪",
    "japan": "🇯🇵",
    "china": "🇨🇳",
    "russia": "🇷🇺",
    "greece": "🇬🇷",
    "scotland": "🏴",
    "sweden": "🇸🇪",
    "switzerland": "🇨🇭",
}

# ============ BAYRAK ============ #
def league_to_flag(league_name: str) -> str:
    if not league_name:
        return EMOJI["flag"]
    name = league_name.lower()
    for key, flag in LEAGUE_FLAGS.items():
        if key in name:
            return flag
    return EMOJI["flag"]

# ============ ORAN VE FORM ============ #
def ensure_min_odds(odds: float) -> float:
    """Minimum oran 1.20 olsun."""
    try:
        return round(max(odds, 1.20), 2)
    except Exception:
        return 1.20

def calc_form_score(stats: dict) -> float:
    """Takımın form skorunu 0.0 - 1.0 arası hesapla."""
    wins = stats.get("wins", 0)
    draws = stats.get("draws", 0)
    losses = stats.get("losses", 0)
    total = wins + draws + losses
    if total == 0:
        return 0.5
    return round((wins + 0.5 * draws) / total, 2)

# ============ GÖRSEL SATIR (Banner) ============ #
def format_prediction_line(p):
    """Banner içinde bir tahmin satırı oluşturur."""
    try:
        flag = league_to_flag(p.get("league", ""))
        home = p.get("home", "Ev Sahibi")
        away = p.get("away", "Deplasman")
        minute = f"{EMOJI['clock']} {p['minute']}'" if p.get("minute") else ""
        odds = p.get("odds", 1.5)
        conf = int(p.get("confidence", 0.7) * 100)
        pred = p.get("prediction", "Tahmin Yok")

        return (
            f"{flag} <b>{home}</b> {EMOJI['vs']} <b>{away}</b>\n"
            f"{minute}  |  💡 Tahmin: <b>{pred}</b>\n"
            f"🎯 Güven: <b>%{conf}</b>  |  💸 Oran: <b>{odds}</b>"
        )
    except Exception as e:
        return f"⚠️ Tahmin formatlanamadı: {e}"
