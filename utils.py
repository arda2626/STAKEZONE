# ================== utils.py — STAKEDRIP AI ULTRA v5.1 ==================
import math

# ================== EMOJIS ==================
EMOJI = {
    "football": "⚽️",
    "basketball": "🏀",
    "tennis": "🎾",
    "star": "⭐️",
    "live": "🔴",
    "clock": "⏱️",
    "time": "⏰",
    "money": "💰",
    "chart": "📊"
}

# ================== COUNTRY FLAGS ==================
EMOJI_MAP = {
    "england": "🏴",
    "turkey": "🇹🇷",
    "germany": "🇩🇪",
    "spain": "🇪🇸",
    "italy": "🇮🇹",
    "france": "🇫🇷",
    "netherlands": "🇳🇱",
    "portugal": "🇵🇹",
    "brazil": "🇧🇷",
    "argentina": "🇦🇷",
    "usa": "🇺🇸",
    "belgium": "🇧🇪",
    "greece": "🇬🇷",
    "russia": "🇷🇺",
    "croatia": "🇭🇷",
    "sweden": "🇸🇪",
    "norway": "🇳🇴",
    "switzerland": "🇨🇭",
    "australia": "🇦🇺",
    "japan": "🇯🇵",
    "china": "🇨🇳",
    "korea": "🇰🇷",
    "saudi arabia": "🇸🇦",
    "mexico": "🇲🇽",
    "scotland": "🏴",
    "denmark": "🇩🇰",
    "austria": "🇦🇹",
    "poland": "🇵🇱",
    "czech republic": "🇨🇿",
    "romania": "🇷🇴",
    "serbia": "🇷🇸",
    "israel": "🇮🇱",
    "ukraine": "🇺🇦"
}

# ================== HELPERS ==================
def league_to_flag(league_name: str) -> str:
    if not league_name:
        return "🏆"
    lname = league_name.lower()
    for key, flag in EMOJI_MAP.items():
        if key in lname:
            return flag
    return "🏆"

def banner_line(match):
    """Tek maç için Türkçeleştirilmiş, zengin banner satırı üretir"""
    sport_emoji = EMOJI.get(match.get("sport", "football"), "⚽️")
    flag = league_to_flag(match.get("league", ""))
    home, away = match.get("home", "?"), match.get("away", "?")
    odds = match.get("odds", 1.0)
    confidence = match.get("confidence", 0.0)
    minute = match.get("minute", None)
    live = match.get("live", False)

    status = f"{EMOJI['live']} CANLI ({EMOJI['clock']} {minute}’)" if live and minute else "Yaklaşan Maç"
    return (
        f"{sport_emoji} {flag} {match.get('league','Lig')} | {status}\n"
        f"{home} vs {away}\n"
        f"{EMOJI['chart']} Oran: {odds:.2f} | {EMOJI['star']} Güven oranı: {confidence*100:.1f}%"
    )

def banner(matches, title="🎯 AI Tahminleri"):
    """Genel banner metni oluşturur"""
    lines = [f"<b>{title}</b>\n"]
    for m in matches:
        lines.append(banner_line(m))
        lines.append("—" * 25)
    return "\n".join(lines)
