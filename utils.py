from datetime import datetime, timezone, timedelta

# ================== EMOJİLER ==================
EMOJI = {
    "futbol": "⚽",
    "nba": "🏀",
    "basketball": "🏀",
    "tenis": "🎾",
    "ding": "🔔",
    "cash": "💰",
    "win": "✅",
    "lose": "❌",
    "clock": "🕒",
    "cup": "🏆",
    "info": "ℹ️"
}

# ================== ÜLKE / LİG BAYRAKLARI ==================
EMOJI_MAP = {
    "turkey":"🇹🇷","süper lig":"🇹🇷","england":"🏴","premier league":"🏴","spain":"🇪🇸","laliga":"🇪🇸",
    "italy":"🇮🇹","serie a":"🇮🇹","germany":"🇩🇪","bundesliga":"🇩🇪","france":"🇫🇷","ligue 1":"🇫🇷",
    "portugal":"🇵🇹","netherlands":"🇳🇱","belgium":"🇧🇪","scotland":"🏴","sweden":"🇸🇪","norway":"🇳🇴",
    "denmark":"🇩🇰","poland":"🇵🇱","switzerland":"🇨🇭","austria":"🇦🇹","russia":"🇷🇺","ukraine":"🇺🇦",
    "usa":"🇺🇸","mls":"🇺🇸","canada":"🇨🇦","mexico":"🇲🇽","brazil":"🇧🇷","argentina":"🇦🇷",
    "japan":"🇯🇵","korea":"🇰🇷","china":"🇨🇳","australia":"🇦🇺","saudi":"🇸🇦","qatar":"🇶🇦",
    "egypt":"🇪🇬","morocco":"🇲🇦","south africa":"🇿🇦","nigeria":"🇳🇬","ghana":"🇬🇭",
    "conmebol":"🌎","concacaf":"🌎","caf":"🌍","uefa":"🇪🇺",
    "champions league":"🏆","europa league":"🇪🇺","fifa":"🌍",
    # basketbol
    "nba":"🇺🇸🏀","euroleague":"🏀🇪🇺","tbl":"🇹🇷🏀",
    # tenis
    "atp":"🎾","wta":"🎾","itf":"🎾"
}

# Kısa isim eşlemeleri
EXTRA_MATCH = {
    "super lig":"turkey","süper lig":"turkey",
    "premier":"england","la liga":"spain","serie a":"italy",
    "bundesliga":"germany","ligue 1":"france",
    "mls":"usa","nba":"nba","euroleague":"euroleague",
    "atp":"atp","wta":"wta","itf":"itf",
    "champions":"champions league","europa":"europa league"
}

# ================== BAYRAK GETİR ==================
def league_to_flag(league_name):
    if not league_name:
        return "🏟️"
    s = str(league_name).lower()
    for k, v in EMOJI_MAP.items():
        if k in s:
            return v
    for substr, mapped in EXTRA_MATCH.items():
        if substr in s:
            return EMOJI_MAP.get(mapped, "🏟️")
    return "🏟️"

# ================== BANNER ==================
def banner(title_short="LIVE"):
    lines = [
        "═"*38,
        "💎 STAKEDRIP AI BAHİS SİNYALLERİ 💎",
        f"🔥 CANLI TAHMİN ({title_short}) 🔥",
        "═"*38
    ]
    return "\n".join(lines)

# ================== ZAMAN YARDIMCILARI ==================
def utcnow(): 
    return datetime.now(timezone.utc)

def turkey_now(): 
    return datetime.now(timezone(timedelta(hours=3)))
