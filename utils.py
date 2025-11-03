# utils.py
from datetime import datetime, timezone, timedelta

def league_to_flag(country):
    flags = {"Türkiye":"🇹🇷","England":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","Spain":"🇪🇸","Italy":"🇮🇹","Germany":"🇩🇪","France":"🇫🇷","Brazil":"🇧🇷","Portugal":"🇵🇹","Netherlands":"🇳🇱"}
    return flags.get(country, "🌍")

def get_live_minute(match):
    try:
        start = datetime.fromisoformat(match["date"].replace("Z","+00:00"))
        now = datetime.now(timezone.utc)
        mins = int((now - start).total_seconds() // 60)
        return mins if 0 < mins < 90 else "90+"
    except: return "?"
