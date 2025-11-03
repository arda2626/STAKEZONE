# utils.py - CANLI SAYAÇ + RANDOM (HATASIZ!)
import random   # <--- EKLEDİM!
from datetime import datetime, timezone

COUNTRY_TO_FLAG = {
    "Turkey": "🇹🇷", "Türkiye": "🇹🇷",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Spain": "🇪🇸", "Italy": "🇮🇹",
    "Germany": "🇩🇪", "France": "🇫🇷", "Brazil": "🇧🇷"
}

def league_to_flag(country):
    if not country: return "🌍"
    key = country.strip().split()[-1]
    return COUNTRY_TO_FLAG.get(key, "🌍")

def get_live_minute(match):
    try:
        start = datetime.fromisoformat(match["date"].replace("Z", "+00:00"))
        mins = int((datetime.now(timezone.utc) - start).total_seconds() // 60)
        return "90+" if mins >= 90 else f"{mins}'"
    except:
        return "45'"

async def get_live_events(match_id):
    # DEMO CANLI SAYAÇ (Gerçek API gelene kadar)
    return {
        "corners": random.randint(5, 12),
        "cards": random.randint(2, 6)
    }
