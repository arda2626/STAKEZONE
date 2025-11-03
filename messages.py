from utils import banner as util_banner, league_to_flag, EMOJI, EMOJI_MAP
from html import escape
from datetime import datetime, timezone, timedelta

# Türkiye saati
def current_time_tr():
    tr_tz = timezone(timedelta(hours=3))
    return datetime.now(tr_tz).strftime("%d %B %H:%M")  # Örn: 03 Kasım 22:57

def create_live_banner(predictions):
    update_time = current_time_tr()
    head = util_banner(f"⚡️ CANLI MAÇLAR ⚽️  |  Güncelleme: {update_time}", predictions)
    lines = [f"<pre>{escape(head)}</pre>", ""]

    for i, p in enumerate(predictions, 1):
        flag = league_to_flag(p.get("league"))
        league = escape(p.get("league", "Bilinmiyor"))
        minute = p.get("minute", "")
        home = escape(p.get("home", "-"))
        away = escape(p.get("away", "-"))
        bet = escape(str(p.get("bet", "Tahmin Yok")))
        odds = p.get("odds", 1.5)
        confidence = int(p.get("confidence", 0) * 100)

        lines.append(f"🎯 <b>{i}. {home}</b> vs <b>{away}</b>")
        lines.append(f"{flag} {league} • ⏱️ {minute}'")
        lines.append(f"💡 Tahmin: <b>{bet}</b>")
        lines.append(f"💰 Oran: <b>{odds}</b>")
        lines.append(f"🧠 Güven Oranı: <b>%{confidence}</b>")
        lines.append("━━━━━━━━━━━━━━━━━━")

    lines.append(f"\n{EMOJI.get('ding','🔔')} Minimum oran: 1.20 • Maksimum: 3 maç")
    return "\n".join(lines)


def create_daily_banner(predictions):
    update_time = current_time_tr()
    head = util_banner(f"📅 GÜNLÜK KUPON 🎯  |  {update_time}")
    total = 1.0
    lines = [f"<pre>{escape(head)}</pre>", ""]

    for p in predictions:
        home = escape(p.get("home", "-"))
        away = escape(p.get("away", "-"))
        bet = escape(str(p.get("bet", "Tahmin Yok")))
        odds = p.get("odds", 1.5)
        lines.append(f"⚽️ {home} vs {away}")
        lines.append(f"🎯 {bet} @ <b>{odds}</b>\n")
        total *= odds

    lines.append(f"💵 Toplam Oran: <b>{round(total, 2)}</b>")
    lines.append(f"🕒 Güncelleme: {update_time}")
    return "\n".join(lines)


def create_vip_banner(predictions):
    update_time = current_time_tr()
    head = util_banner(f"💎 VIP KASA 🎯  |  {update_time}")
    total = 1.0
    lines = [f"<pre>{escape(head)}</pre>", ""]

    for p in predictions:
        home = escape(p.get("home", "-"))
        away = escape(p.get("away", "-"))
        bet = escape(str(p.get("bet", "Tahmin Yok")))
        odds = p.get("odds", 1.5)
        lines.append(f"🏆 {home} vs {away}")
        lines.append(f"🎯 {bet} @ <b>{odds}</b>\n")
        total *= odds

    lines.append(f"💰 Potansiyel Kazanç: <b>{round(total, 2)}</b>")
    lines.append(f"🕒 Güncelleme: {update_time}")
    return "\n".join(lines)
