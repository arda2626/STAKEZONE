# ================== utils.py — STAKEDRIP AI ULTRA v5.1 ==================
import random

# ============ ODDS TOOLS ============ #
def ensure_min_odds(odds, min_value=1.40):
    """Oran 1.40'tan düşükse, rastgele arttır."""
    try:
        if odds < min_value:
            odds = round(random.uniform(min_value, min_value + 0.5), 2)
    except Exception:
        odds = min_value
    return odds


# ============ FORM SCORE CALCULATION ============ #
def calc_form_score(team_stats):
    """Takım form skorunu hesapla (basitleştirilmiş)."""
    if not team_stats or not isinstance(team_stats, dict):
        return random.uniform(0.55, 0.85)
    score = (
        team_stats.get("win_rate", 0.5) * 0.5
        + team_stats.get("attack", 0.5) * 0.3
        + team_stats.get("defense", 0.5) * 0.2
    )
    return round(min(max(score, 0.4), 0.95), 2)


# ============ EMOJIS ============ #
EMOJI = {
    "fire": "🔥",
    "cash": "💰",
    "clock": "⏱️",
    "chart": "📊",
    "goal": "⚽",
    "court": "🏀",
    "tennis": "🎾",
    "flag": "🏴",
    "lock": "🔒",
    "live": "🟢",
    "alert": "🚨",
    "star": "⭐",
}

EMOJI_MAP = {
    "football": EMOJI["goal"],
    "basketball": EMOJI["court"],
    "tennis": EMOJI["tennis"],
}


# ============ FLAGS ============ #
def league_to_flag(league_name: str) -> str:
    """Lig adına göre ülke bayrağı döndürür."""
    name = league_name.lower()
    flags = {
        "england": "🏴",
        "turkey": "🇹🇷",
        "spain": "🇪🇸",
        "italy": "🇮🇹",
        "germany": "🇩🇪",
        "france": "🇫🇷",
        "netherlands": "🇳🇱",
        "portugal": "🇵🇹",
        "brazil": "🇧🇷",
        "argentina": "🇦🇷",
        "japan": "🇯🇵",
        "usa": "🇺🇸",
        "greece": "🇬🇷",
        "austria": "🇦🇹",
        "sweden": "🇸🇪",
        "belgium": "🇧🇪",
        "norway": "🇳🇴",
        "croatia": "🇭🇷",
        "denmark": "🇩🇰",
        "switzerland": "🇨🇭",
        "scotland": "🏴",
        "russia": "🇷🇺",
        "mexico": "🇲🇽",
        "poland": "🇵🇱",
        "serbia": "🇷🇸",
    }

    for key, flag in flags.items():
        if key in name:
            return flag
    return "🌍"


# ============ BANNER HELPER ============ #
def format_prediction_line(match):
    """AI tahminini banner için biçimlendir."""
    flag = league_to_flag(match.get("league", ""))
    sport_icon = EMOJI_MAP.get(match.get("sport"), "🎯")
    minute = match.get("minute", None)
    conf = match.get("confidence", 0)

    minute_text = f"({minute}’)" if minute else ""
    conf_text = f"🔮 Güven: %{int(conf * 100)}"

    return (
        f"{sport_icon} {flag} <b>{match['home']} vs {match['away']}</b> {minute_text}\n"
        f"🏆 {match['league']} | {conf_text} | 💸 Oran: {match.get('odds', '—')}"
    )
