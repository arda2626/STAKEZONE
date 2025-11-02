# utils.py
from datetime import datetime, timezone, timedelta

# ---------------- BASIC HELPERS ----------------
def ensure_min_odds(odds, min_odds=1.2):
    return max(odds, min_odds)

def calc_form_score(team_stats):
    return sum(team_stats)/len(team_stats) if team_stats else 0

def combine_confidence(*args):
    return sum(args)/len(args) if args else 0

def utcnow():
    return datetime.now(timezone.utc)

def turkey_now():
    return datetime.now(timezone(timedelta(hours=3)))

# ---------------- EMOJI & BANNER ----------------
EMOJI = {
    "futbol":"⚽","nba":"🏀","tenis":"🎾","ding":"🔔","cash":"💰",
    "win":"✅","lose":"❌","clock":"🕒","cup":"🏆","info":"ℹ️"
}

def banner(title_short="LIVE"):
    return "\n".join(["═"*38, "💎 STAKEDRIP LIVE PICKS 💎", f"🔥 AI CANLI TAHMİN ({title_short}) 🔥", "═"*38])

# ---------------- COUNTRY / LEAGUE EMOJI MAP ----------------
EMOJI_MAP = {
    "turkey":"🇹🇷","süper lig":"🇹🇷","super lig":"🇹🇷",
    "england":"🏴","premier league":"🏴",
    "spain":"🇪🇸","laliga":"🇪🇸","la liga":"🇪🇸",
    "italy":"🇮🇹","serie a":"🇮🇹",
    "germany":"🇩🇪","bundesliga":"🇩🇪",
    "france":"🇫🇷","ligue 1":"🇫🇷",
    "portugal":"🇵🇹","netherlands":"🇳🇱","belgium":"🇧🇪",
    "scotland":"🏴","sweden":"🇸🇪","norway":"🇳🇴","denmark":"🇩🇰",
    "poland":"🇵🇱","switzerland":"🇨🇭","austria":"🇦🇹",
    "russia":"🇷🇺","ukraine":"🇺🇦",
    "usa":"🇺🇸","mls":"🇺🇸","canada":"🇨🇦","mexico":"🇲🇽","brazil":"🇧🇷","argentina":"🇦🇷",
    "japan":"🇯🇵","korea":"🇰🇷","china":"🇨🇳","australia":"🇦🇺","saudi":"🇸🇦","qatar":"🇶🇦",
    "egypt":"🇪🇬","morocco":"🇲🇦","south africa":"🇿🇦","nigeria":"🇳🇬","ghana":"🇬🇭",
    "conmebol":"🌎","concacaf":"🌎","caf":"🌍","uefa":"🇪🇺","champions league":"🏆",
    "europa league":"🇪🇺","fifa":"🌍",
    "nba":"🇺🇸🏀","euroleague":"🏀🇪🇺","atp":"🎾","wta":"🎾","itf":"🎾"
}

EXTRA_MATCH = { 
    "super lig":"turkey","süper lig":"turkey","premier":"england","la liga":"spain",
    "serie a":"italy","bundesliga":"germany","ligue 1":"france",
    "mls":"usa","nba":"nba","euroleague":"euroleague","atp":"atp","wta":"wta"
}

def league_to_flag(league_name):
    if not league_name: return "🏟️"
    s = str(league_name).lower()
    for k,v in EMOJI_MAP.items():
        if k in s and len(k) > 1:
            return v
    for substr, mapped in EXTRA_MATCH.items():
        if substr in s:
            return EMOJI_MAP.get(mapped, "🏟️")
    return "🏟️"

# ---------------- PREDICTION STORAGE ----------------
# Hafızada saklamak için basit liste
PREDICTIONS_DB = []

def save_prediction(prediction: dict):
    PREDICTIONS_DB.append(prediction)

def mark_prediction(pred_id, status, result):
    for p in PREDICTIONS_DB:
        if p.get("id") == pred_id:
            p["status"] = status
            p["result"] = result
            break

def get_pending_predictions():
    return [p for p in PREDICTIONS_DB if p.get("status") is None]

def day_summary_between(start_iso, end_iso):
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    counts = {"won":0,"lost":0,"pending":0,"unknown":0}
    for p in PREDICTIONS_DB:
        created_at = datetime.fromisoformat(p.get("created_at"))
        if start <= created_at <= end:
            status = p.get("status") or "pending"
            counts[status] = counts.get(status,0)+1
    return counts.items()

def build_live_text(predictions):
    lines = []
    for p in predictions:
        lines.append(f"{p.get('home')} vs {p.get('away')} • Tahmin: {p.get('bet_text','')} • Oran: {p.get('odds')}")
    return "\n".join(lines)
