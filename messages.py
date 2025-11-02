# messages.py
from utils import banner, EMOJI
from emoji_map import league_to_flag

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
    lines.append(f"{EMOJI['ding']} Minimum oran: {EMOJI.get('min_odds','1.20')} • Maks: 3 maç")
    return "\n".join(lines)

def build_coupon_text(title, picks):
    head = banner(title)
    lines = [head, ""]
    total = 1.0
    for i,p in enumerate(picks,1):
        lines += [f"{i}. {p.get('home')} vs {p.get('away')} • {p['bet']} @ **{p['odds']}** • AI: %{p['prob']}", ""]
        total *= p['odds']
    lines += [f"TOPLAM ORAN: **{round(total,2)}** {EMOJI['cash']}"]
    return "\n".join(lines)
