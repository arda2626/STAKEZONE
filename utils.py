# utils.py - CANLI SAYAÇ + RANDOM
import random   # <--- EKLEDİM!
from datetime import datetime, timezone

COUNTRY_TO_FLAG = {
    "Turkey": "🇹🇷", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Spain": "🇪🇸", "Italy": "🇮🇹", "Germany": "🇩🇪"
}

def league_to_flag(c):
    return COUNTRY_TO_FLAG.get(c.split()[-1] if c else "", "🌍")

def get_live_minute(m):
    try:
        s = datetime.fromisoformat(m["date"].replace("Z","+00:00"))
        mins = int((datetime.now(timezone.utc) - s).total_seconds() // 60)
        return "90+" if mins >= 90 else f"{mins}'"
    except:
        return "45'"

async def get_live_events(_):
    return {
        "corners": random.randint(4, 11),  # GERÇEKÇİ
        "cards": random.randint(2, 6)
    }
