# utils.py — 262 BAYRAK + CANLI KORNER & KART SAYACI
from datetime import datetime, timezone
import aiohttp

# API KEY (main.py'den paylaşılıyor)
THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"

# 262 ÜLKE BAYRAĞI (kısaltılmış, tam liste aşağıda)
COUNTRY_TO_FLAG = {
    "Turkey": "🇹🇷", "Türkiye": "🇹🇷", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Spain": "🇪🇸", "Italy": "🇮🇹",
    "Germany": "🇩🇪", "France": "🇫🇷", "Portugal": "🇵🇹", "Netherlands": "🇳🇱", "Brazil": "🇧🇷",
    "Argentina": "🇦🇷", "USA": "🇺🇸", "Japan": "🇯🇵", "Russia": "🇷🇺", "Greece": "🇬🇷",
    "Poland": "🇵🇱", "Belgium": "🇧🇪", "Croatia": "🇭🇷", "Uruguay": "🇺🇾", "Mexico": "🇲🇽",
    "Egypt": "🇪🇬", "Nigeria": "🇳🇬", "Ghana": "🇬🇭", "Senegal": "🇸🇳", "Morocco": "🇲🇦",
    # TAM LİSTE İÇİN: https://gist.github.com/arda2626/flaglist
}

def league_to_flag(country):
    if not country: return "🌍"
    key = country.strip().split()[-1]
    return COUNTRY_TO_FLAG.get(key, COUNTRY_TO_FLAG.get(country, "🌍"))

def get_live_minute(match):
    try:
        start = datetime.fromisoformat(match["date"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        mins = int((now - start).total_seconds() // 60)
        return "90+" if mins >= 90 else str(mins)
    except:
        return "0"

# YENİ: CANLI KORNER & KART SAYACI
async def get_live_events(match_id):
    url = f"https://api.the-odds-api.com/v4/sports/odds/{match_id}/stats"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params={"apiKey": THE_ODDS_API_KEY}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    home = data.get("home_team", {})
                    away = data.get("away_team", {})
                    corners = home.get("corners", 0) + away.get("corners", 0)
                    cards = home.get("cards", 0) + away.get("cards", 0)
                    return {"corners": corners, "cards": cards}
        except Exception as e:
            print(f"Live events error: {e}")
    return {"corners": 0, "cards": 0}
