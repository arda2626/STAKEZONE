# ================== messages.py — STAKEDRIP AI ULTRA v5.10 ==================
from utils import banner as util_banner, league_to_flag
from html import escape
from datetime import datetime, timezone, timedelta

# ================== TÜRKİYE SAATİ ==================
def current_time_tr():
    tr_tz = timezone(timedelta(hours=3))
    return datetime.now(tr_tz).strftime("%d %B %H:%M")  # Örn: 03 Kasım 22:57

# ================== CANLI MAÇ BANNER ==================
def create_live_banner(predictions):
    update_time = current_time_tr()
    head = util_banner(f"⚡️🔥 CANLI MAÇLAR ⚽️ | Güncelleme: {update_time}", predictions)
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

        lines.append(f"🌟 {i}. <b>{home}</b> vs <b>{away}</b> {flag}")
        lines.append(f"🏟️ {league} • ⏱️ {minute}'")
        lines.append(f"🎯 Tahmin: <b>{bet}</b> • 💰 Oran: <b>{odds}</b>")
        lines.append(f"🧠 Güven: <b>%{confidence}</b>")
        lines.append("🔹" * 15)

    lines.append(f"\n🔔 Minimum oran: 1.20 • Maksimum 3 maç")
    return "\n".join(lines)

# ================== GÜNLÜK KUPON BANNER ==================
def create_daily_banner(predictions):
    update_time = current_time_tr()
    head = util_banner(f"📅 GÜNLÜK KUPON 🎯 | {update_time}", predictions)
    total = 1.0
    lines = [f"<pre>{escape(head)}</pre>", ""]

    for i, p in enumerate(predictions, 1):
        flag = league_to_flag(p.get("league"))
        home = escape(p.get("home", "-"))
        away = escape(p.get("away", "-"))
        bet = escape(str(p.get("bet", "Tahmin Yok")))
        odds = p.get("odds", 1.5)
        total *= odds

        # Maç tarihini TR saatine çevir
        try:
            match_dt = datetime.fromisoformat(p.get("date")).astimezone(timezone(timedelta(hours=3)))
            match_date = match_dt.strftime("%d %b %H:%M")
        except:
            match_date = "Tarih Yok"

        lines.append(f"⚽️ {i}. {home} vs {away} {flag}")
        lines.append(f"🗓️ Tarih: {match_date} • 🎯 Tahmin: <b>{bet}</b> • 💰 Oran: <b>{odds}</b>")
        lines.append("🌟" * 15)

    lines.append(f"💵 Toplam Oran: <b>{round(total,2)}</b>")
    lines.append(f"🕒 Güncelleme: {update_time}")
    return "\n".join(lines)

# ================== VIP KASA BANNER ==================
def create_vip_banner(predictions):
    update_time = current_time_tr()
    head = util_banner(f"💎 VIP KASA 🎯 | {update_time}", predictions)
    total = 1.0
    lines = [f"<pre>{escape(head)}</pre>", ""]

    for i, p in enumerate(predictions, 1):
        flag = league_to_flag(p.get("league"))
        home = escape(p.get("home", "-"))
        away = escape(p.get("away", "-"))
        bet = escape(str(p.get("bet", "Tahmin Yok")))
        odds = p.get("odds", 1.5)
        total *= odds

        # Maç tarihini TR saatine çevir
        try:
            match_dt = datetime.fromisoformat(p.get("date")).astimezone(timezone(timedelta(hours=3)))
            match_date = match_dt.strftime("%d %b %H:%M")
        except:
            match_date = "Tarih Yok"

        lines.append(f"🏆 {i}. {home} vs {away} {flag}")
        lines.append(f"🗓️ Tarih: {match_date} • 🎯 Tahmin: <b>{bet}</b> • 💰 Oran: <b>{odds}</b>")
        lines.append("💠" * 15)

    lines.append(f"💰 Potansiyel Kazanç: <b>{round(total,2)}</b>")
    lines.append(f"🕒 Güncelleme: {update_time}")
    return "\n".join(lines)
