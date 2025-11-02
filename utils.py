# utils.py
from datetime import datetime, timezone, timedelta

# ---------------- EMOJI ----------------
EMOJI = {
    "futbol":"⚽","nba":"🏀","tenis":"🎾","ding":"🔔","cash":"💰",
    "win":"✅","lose":"❌","clock":"🕒","cup":"🏆","info":"ℹ️"
}

# ---------------- BANNER ----------------
def banner(title_short="LIVE"):
    return "\n".join(["═"*38, "💎 STAKEDRIP LIVE PICKS 💎", f"🔥 AI CANLI TAHMİN ({title_short}) 🔥", "═"*38])

# ---------------- COUNTRY / LEAGUE EMOJI MAP ----------------
EMOJI_MAP = {
    # Türkiye & Süper Lig
    "turkey":"🇹🇷","süper lig":"🇹🇷","super lig":"🇹🇷",
    # İngiltere
    "england":"🏴","premier league":"🏴",
    # İspanya
    "spain":"🇪🇸","laliga":"🇪🇸","la liga":"🇪🇸",
    # İtalya
    "italy":"🇮🇹","serie a":"🇮🇹",
    # Almanya
    "germany":"🇩🇪","bundesliga":"🇩🇪",
    # Fransa
    "france":"🇫🇷","ligue 1":"🇫🇷",
    # Portekiz, Hollanda, Belçika
    "portugal":"🇵🇹","netherlands":"🇳🇱","belgium":"🇧🇪",
    # İskoçya, İskandinav
    "scotland":"🏴","sweden":"🇸🇪","norway":"🇳🇴","denmark":"🇩🇰",
    # Polonya, İsviçre, Avusturya
    "poland":"🇵🇱","switzerland":"🇨🇭","austria":"🇦🇹",
    # Rusya, Ukrayna
    "russia":"🇷🇺","ukraine":"🇺🇦",
    # Amerika kıtası
    "usa":"🇺🇸","mls":"🇺🇸","canada":"🇨🇦","mexico":"🇲🇽","brazil":"🇧🇷","argentina":"🇦🇷",
    # Asya & Okyanusya
    "japan":"🇯🇵","korea":"🇰🇷","china":"🇨🇳","australia":"🇦🇺","saudi":"🇸🇦","qatar":"🇶🇦",
    # Afrika
    "egypt":"🇪🇬","morocco":"🇲🇦","south africa":"🇿🇦","nigeria":"🇳🇬","ghana":"🇬🇭",
    # Kupalar & Uluslararası
    "conmebol":"🌎","concacaf":"🌎","caf":"🌍","uefa":"🇪🇺","champions league":"🏆",
    "europa league":"🇪🇺","fifa":"🌍",
    # Basketbol & Tenis
    "nba":"🇺🇸🏀","euroleague":"🏀🇪🇺","atp":"🎾","wta":"🎾","itf":"🎾"
}

EXTRA_MATCH = { 
    "super lig":"turkey","süper lig":"turkey","premier":"england","la liga":"spain",
    "serie a":"italy","bundesliga":"germany","ligue 1":"france",
    "mls":"usa","nba":"nba","euroleague":"euroleague","atp":"atp","wta":"wta"
}

def league_to_flag(league_name):
    if not league_name: return "🏟️"
    s = str(league_name).lower()
    for k,v in EMOJI_MAP.items():
        if k in s and len(k) > 1:
            return v
    for substr, mapped in EXTRA_MATCH.items():
        if substr in s:
            return EMOJI_MAP.get(mapped, "🏟️")
    return "🏟️"

# ---------------- TIME HELPERS ----------------
def utcnow(): return datetime.now(timezone.utc)
def turkey_now(): return datetime.now(timezone(timedelta(hours=3)))
