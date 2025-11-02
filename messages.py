from utils import EMOJI, league_to_flag, banner, turkey_now

# ================== MAÇ MESAJI OLUŞTUR ==================
def format_match_message(match):
    """
    match: dict
    {
        "home_team": "Galatasaray",
        "away_team": "Fenerbahçe",
        "league": "Super Lig",
        "start_time": datetime,
        "prediction": "KG",  # veya "Üst", "Alt", "1", "2"
        "odds": 1.85
    }
    """
    flag = league_to_flag(match.get("league"))
    start_time = match.get("start_time").strftime("%H:%M")
    pred = match.get("prediction")
    odds = match.get("odds")
    sport_emoji = EMOJI.get(match.get("sport","futbol"), "⚽")
    
    msg = f"{banner(title_short='LIVE')}\n"
    msg += f"{sport_emoji} {flag} {match.get('league')} | {start_time}\n"
    msg += f"🏟️ {match.get('home_team')}  vs  {match.get('away_team')}\n"
    msg += f"🎯 Tahmin: {pred}  |  Oran: {odds}\n"
    msg += f"🕒 {turkey_now().strftime('%d/%m %H:%M')}\n"
    msg += "═"*38
    return msg
