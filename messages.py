# messages.py
from utils import EMOJI, league_to_flag, banner, turkey_now

def format_match_message(match):
    flag = league_to_flag(match.get("league"))
    start_time = match.get("start_time").strftime("%H:%M") if match.get("start_time") else "-"
    pred = match.get("prediction")
    odds = match.get("odds")
    sport_emoji = EMOJI.get(match.get("sport","futbol"), "⚽")
    
    msg = f"{banner(title_short='LIVE')}\n"
    msg += f"{sport_emoji} {flag} {match.get('league')} | {start_time}\n"
    msg += f"🏟️ {match.get('home_team')} vs {match.get('away_team')}\n"
    msg += f"🎯 Tahmin: {pred} | Oran: {odds}\n"
    msg += f"🕒 {turkey_now().strftime('%d/%m %H:%M')}\n"
    msg += "═"*38
    return msg
