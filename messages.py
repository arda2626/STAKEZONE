# messages.py — Banner Fonksiyonları (Bayraklı)
from datetime import datetime, timezone

# Basit ülke kodu → bayrak fonksiyonu
def country_flag(code: str) -> str:
    if not code or len(code) != 2:
        return ""
    return chr(0x1F1E6 + ord(code.upper()[0]) - ord('A')) + chr(0x1F1E6 + ord(code.upper()[1]) - ord('A'))

def create_daily_banner(predictions):
    now = datetime.now(timezone.utc)
    text = f"🤖 📅 GÜNLÜK KUPON 🎯 | {now.strftime('%d %B %H:%M')}\n"
    text += "━━━━━━━━━━━━━━━\n"
    total_odds = 1
    for i, p in enumerate(predictions, start=1):
        home = p.get("home")
        away = p.get("away")
        odds = p.get("odds", 1.5)
        confidence = int(p.get("confidence", 0)*100)
        match_date = p.get("date", now.isoformat())
        flag_home = country_flag(p.get("country_home", ""))
        flag_away = country_flag(p.get("country_away", ""))
        text += f"⚽️ {i}. {flag_home} {home} vs {away} {flag_away}\n"
        text += f"🎯 Tahmin: {p.get('prediction','-')} • 💰 Oran: {odds:.2f}\n"
        text += f"🌟 Güven: {confidence}% | 🕒 {match_date}\n"
        total_odds *= odds
    text += "━━━━━━━━━━━━━━━\n"
    text += f"💵 Toplam Oran: {total_odds:.2f}\n"
    text += f"🕒 Güncelleme: {now.strftime('%d %B %H:%M')}"
    return text

def create_vip_banner(predictions):
    now = datetime.now(timezone.utc)
    text = f"🤖 🔥 VIP KUPON 🎯 | {now.strftime('%d %B %H:%M')}\n"
    text += "━━━━━━━━━━━━━━━\n"
    total_odds = 1
    for i, p in enumerate(predictions, start=1):
        home = p.get("home")
        away = p.get("away")
        odds = p.get("odds", 1.5)
        confidence = int(p.get("confidence", 0)*100)
        flag_home = country_flag(p.get("country_home", ""))
        flag_away = country_flag(p.get("country_away", ""))
        text += f"⚽️ {i}. {flag_home} {home} vs {away} {flag_away}\n"
        text += f"🎯 Tahmin: {p.get('prediction','-')} • 💰 Oran: {odds:.2f}\n"
        text += f"🌟 Güven: {confidence}%\n"
        total_odds *= odds
    text += "━━━━━━━━━━━━━━━\n"
    text += f"💵 Toplam Oran: {total_odds:.2f}"
    return text

def create_live_banner(predictions):
    now = datetime.now(timezone.utc)
    text = f"🤖 ⏱️ CANLI MAÇ 🎯 | {now.strftime('%d %B %H:%M')}\n"
    text += "━━━━━━━━━━━━━━━\n"
    for i, p in enumerate(predictions, start=1):
        home = p.get("home")
        away = p.get("away")
        odds = p.get("odds",1.5)
        flag_home = country_flag(p.get("country_home", ""))
        flag_away = country_flag(p.get("country_away", ""))
        text += f"⚽️ {flag_home} {home} vs {away} {flag_away} | 🎯 Tahmin: {p.get('prediction','-')} • 💰 Oran: {odds:.2f}\n"
    return text
