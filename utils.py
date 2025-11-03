# ================== utils.py — STAKEDRIP AI ULTRA v5.0 ==================
import random
from datetime import datetime, timezone

# ================== EMOJİ SETİ ==================
EMOJI = {
    "fire": "🔥",
    "star": "⭐️",
    "money": "💰",
    "chart": "📊",
    "trophy": "🏆",
    "alarm": "⏰",
    "live": "🟢",
    "football": "⚽️",
    "basketball": "🏀",
    "tennis": "🎾",
    "calendar": "📅",
    "earth": "🌍",
    "rocket": "🚀",
}

EMOJI_MAP = {
    "football": EMOJI["football"],
    "basketball": EMOJI["basketball"],
    "tennis": EMOJI["tennis"]
}

# ================== ZAMAN ==================
def utcnow():
    return datetime.now(timezone.utc)

def format_time(ts):
    if isinstance(ts, str):
        return ts
    return ts.strftime("%H:%M")

# ================== BAYRAKLAR ==================
def league_to_flag(league_name: str) -> str:
    """Lige veya ülkeye göre uygun bayrak döndürür."""
    name = league_name.lower()
    flags = {
        # Avrupa
        "turkey": "🇹🇷", "super lig": "🇹🇷",
        "england": "🏴", "premier": "🏴",
        "spain": "🇪🇸", "la liga": "🇪🇸",
        "italy": "🇮🇹", "serie a": "🇮🇹",
        "germany": "🇩🇪", "bundesliga": "🇩🇪",
        "france": "🇫🇷", "ligue": "🇫🇷",
        "netherlands": "🇳🇱", "eredivisie": "🇳🇱",
        "portugal": "🇵🇹", "liga portugal": "🇵🇹",
        "belgium": "🇧🇪", "pro league": "🇧🇪",
        "switzerland": "🇨🇭", "austria": "🇦🇹", "scotland": "🏴",
        "greece": "🇬🇷", "denmark": "🇩🇰", "norway": "🇳🇴", "sweden": "🇸🇪",
        "finland": "🇫🇮", "poland": "🇵🇱", "czech": "🇨🇿", "croatia": "🇭🇷",
        "serbia": "🇷🇸", "romania": "🇷🇴", "hungary": "🇭🇺", "ukraine": "🇺🇦", "russia": "🇷🇺",

        # Amerika
        "usa": "🇺🇸", "mls": "🇺🇸", "mexico": "🇲🇽", "brazil": "🇧🇷", "brasileirao": "🇧🇷",
        "argentina": "🇦🇷", "chile": "🇨🇱", "colombia": "🇨🇴", "uruguay": "🇺🇾",
        "ecuador": "🇪🇨", "peru": "🇵🇪", "canada": "🇨🇦",

        # Asya
        "japan": "🇯🇵", "j-league": "🇯🇵", "china": "🇨🇳", "south korea": "🇰🇷",
        "k league": "🇰🇷", "saudi": "🇸🇦", "qatar": "🇶🇦", "uae": "🇦🇪", "iran": "🇮🇷",
        "israel": "🇮🇱", "india": "🇮🇳", "indonesia": "🇮🇩", "vietnam": "🇻🇳", "thailand": "🇹🇭",

        # Afrika
        "egypt": "🇪🇬", "morocco": "🇲🇦", "south africa": "🇿🇦", "nigeria": "🇳🇬",
        "ghana": "🇬🇭", "algeria": "🇩🇿", "tunisia": "🇹🇳", "senegal": "🇸🇳",

        # Okyanusya
        "australia": "🇦🇺", "new zealand": "🇳🇿",
    }
    for key, flag in flags.items():
        if key in name:
            return flag
    return EMOJI["earth"]

# ================== BANNER ==================
def banner(predictions, title="LIVE AI PREDICTIONS"):
    """Tahmin listesini şık bir banner formatında döndürür."""
    lines = []
    header = f"{EMOJI['rocket']} <b>{title}</b> {EMOJI['fire']}\n"
    lines.append(header)

    for p in predictions:
        sport_icon = EMOJI_MAP.get(p.get("sport", "football"), EMOJI["football"])
        flag = league_to_flag(p.get("league", ""))
        teams = f"{p.get('home', '')} vs {p.get('away', '')}"
        conf = f"{p.get('confidence', 0)*100:.1f}%"
        odds = f"{p.get('odds', 1.5):.2f}"

        line = (
            f"{sport_icon} {flag} <b>{teams}</b>\n"
            f"   {EMOJI['chart']} Odds: {odds} | {EMOJI['star']} Confidence: {conf}\n"
        )
        lines.append(line)

    footer = f"\n{EMOJI['money']} <i>STAKEDRIP AI - Smart Betting Intelligence</i>"
    return "\n".join(lines) + footer
