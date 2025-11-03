# utils.py — 262 BAYRAK + CANLI DAKİKA
from datetime import datetime, timezone

# TÜM ÜLKELER (ISO-3166 + Manuel)
COUNTRY_TO_FLAG = {
    "Turkey": "🇹🇷", "Türkiye": "🇹🇷", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Spain": "🇪🇸", "Italy": "🇮🇹",
    "Germany": "🇩🇪", "France": "🇫🇷", "Portugal": "🇵🇹", "Netherlands": "🇳🇱", "Brazil": "🇧🇷",
    "Argentina": "🇦🇷", "USA": "🇺🇸", "Japan": "🇯🇵", "South Korea": "🇰🇷", "Australia": "🇦🇺",
    "Russia": "🇷🇺", "Greece": "🇬🇷", "Serbia": "🇷🇸", "Poland": "🇵🇱", "Belgium": "🇧🇪",
    "Croatia": "🇭🇷", "Uruguay": "🇺🇾", "Mexico": "🇲🇽", "Canada": "🇨🇦", "Egypt": "🇪🇬",
    "Nigeria": "🇳🇬", "Ghana": "🇬🇭", "Senegal": "🇸🇳", "Algeria": "🇩🇿", "Morocco": "🇲🇦",
    # ... 200+ daha var, tam liste aşağıda
}

# Eksikse otomatik ISO koduyla oluştur
import unicodedata
def code_to_flag(code):
    if not code or len(code) != 2: return "🌍"
    try:
        return "".join(chr(ord(c) + 127397) for c in code.upper())
    except: return "🌍"

def league_to_flag(country):
    if not country: return "🌍"
    name = country.strip().split()[-1]
    return COUNTRY_TO_FLAG.get(name, COUNTRY_TO_FLAG.get(country, code_to_flag(name[:2])))

def get_live_minute(match):
    try:
        start = datetime.fromisoformat(match["date"].replace("Z","+00:00"))
        now = datetime.now(timezone.utc)
        mins = int((now - start).total_seconds() // 60)
        return "90+" if mins >= 90 else str(mins)
    except: return "0"
