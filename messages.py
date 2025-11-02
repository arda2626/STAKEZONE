from utils import banner, EMOJI, league_to_flag
from db import save_prediction
from utils import utcnow

def build_live_text(picks, include_minute=True):
    head = banner("LIVE")
    lines = [head, ""]
    for i,p in enumerate(picks,1):
        flag = league_to_flag(p.get("league"))
        minute_text = p.get("minute")
        minute_str = f" | {minute_text}" if minute_text and include_minute else ""
        emoji = EMOJI.get(p["sport"], "⚽")
        lines += [
            f"{flag} {p.get('league','')} {minute_str} {emoji}",
            f"{i}. **{p['home']} vs {p['away']}**",
            f"   Tahmin: {p['bet']} → **{p['odds']}** • AI: %{p['prob']}",
            ""
        ]
    lines.append(f"{EMOJI['ding']} Minimum oran: 1.20 • Maks: 3 maç")
    return "\n".join(lines)
