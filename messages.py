# messages.py
from utils import banner as util_banner, league_to_flag, EMOJI, EMOJI_MAP
from html import escape

def create_live_banner(predictions):
    # HTML compatible banner (we'll use parse_mode="HTML")
    head = util_banner("LIVE", predictions)
    lines = [f"<pre>{escape(head)}</pre>", ""]
    for i,p in enumerate(predictions,1):
        flag = league_to_flag(p.get("league"))
        minute = p.get("minute", "")
        lines.append(f"<b>{i}. {escape(p.get('home','-'))} vs {escape(p.get('away','-'))}</b>")
        lines.append(f"{flag} {escape(p.get('league',''))} {escape(str(minute))}")
        lines.append(f"Tahmin: <b>{escape(str(p.get('bet')))}</b> • Oran: <b>{p.get('odds')}</b> • AI: %{int(p.get('confidence',0)*100)}")
        lines.append("<i>—</i>")
    lines.append(f"{EMOJI.get('ding','🔔')} Minimum oran: 1.20 • Maks: 3 maç")
    return "\n".join(lines)

def create_daily_banner(predictions):
    head = util_banner("GÜNLÜK")
    total = 1.0
    lines = [f"<pre>{escape(head)}</pre>", ""]
    for p in predictions:
        lines.append(f"{escape(p.get('home','-'))} vs {escape(p.get('away','-'))} • {escape(str(p.get('bet')))} @ <b>{p.get('odds')}</b>")
        total *= p.get('odds',1.0)
    lines.append(f"<b>TOPLAM ORAN: {round(total,2)}</b>")
    return "\n".join(lines)

def create_vip_banner(predictions):
    head = util_banner("KASA")
    total = 1.0
    lines = [f"<pre>{escape(head)}</pre>", ""]
    for p in predictions:
        lines.append(f"{escape(p.get('home','-'))} vs {escape(p.get('away','-'))} • {escape(str(p.get('bet')))} @ <b>{p.get('odds')}</b>")
        total *= p.get('odds',1.0)
    lines.append(f"<b>POTANSİYEL: {round(total,2)}</b>")
    return "\n".join(lines)
