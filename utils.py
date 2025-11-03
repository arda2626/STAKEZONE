# utils.py - BAYRAK + CANLI DAKİKA
from datetime import datetime, timezone

# 262 BAYRAK (telefon için kısa hali, tam liste aşağıda)
COUNTRY_TO_FLAG = {
    "Turkey": "🇹🇷", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Spain": "🇪🇸", "Italy": "🇮🇹", "Germany": "🇩🇪",
    "France": "🇫🇷", "Portugal": "🇵🇹", "Brazil": "🇧🇷", "Argentina": "🇦🇷", "USA": "🇺🇸",
    "Japan": "🇯🇵", "Russia": "🇷🇺", "Greece": "🇬🇷", "Poland": "🇵🇱", "Belgium": "🇧🇪",
    "Croatia": "🇭🇷", "Mexico": "🇲🇽", "Egypt": "🇪🇬", "Nigeria": "🇳🇬", "Ghana": "🇬🇭",
    # TAM LİSTE İÇİN: https://git.new/flags
}

def league_to_flag(country):
    if not country: return "🌍"
    key = country.strip().split()[-1]
    return COUNTRY_TO_FLAG.get(key, COUNTRY_TO_FLAG.get(country, "🌍"))

def get_live_minute(match):
    try:
        start = datetime.fromisoformat(match["date"].replace("Z", "+00:00"))
        mins = int((datetime.now(timezone.utc) - start).total_seconds() // 60)
        return "90+" if mins >= 90 else str(mins) + "'"
    except:
        return "0'"

# Canlı korner & kart (şimdilik demo)
async def get_live_events(match_id):
    return {"corners": random.randint(3, 12), "cards": random.randint(1, 6)}
