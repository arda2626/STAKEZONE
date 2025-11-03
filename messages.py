# messages.py — Banner Fonksiyonları

from datetime import datetime, timezone

def create_daily_banner(predictions):
    now = datetime.now(timezone.utc)
    text = f"🤖 📅 GÜNLÜK KUPON 🎯 | {now.strftime('%d %B %H:%M')}\n"
    text += "━━━━━━━━━━━━━━━\n"
    for i, p in enumerate(predictions, start=1):
        home = p.get("home")
        away = p.get("away")
        odds = p.get("odds")
        confidence = int(p.get("confidence",0)*100)
        match_date = p.get("date", now.isoformat())
        text += f"⚽️ {i}. {home} vs {away} | {match_date} 🌍\n"
        text += f"🎯 Tahmin: {p.get('prediction','-')} • 💰 Oran: {odds:.2f}\n"
        text += f"🌟 Güven: {confidence}%\n"
    total_odds = 1
    for p in predictions:
        total_odds *= p.get("odds",1)
    text += f"💵 Toplam Oran: {total_odds:.2f}\n"
    text += f"🕒 Güncelleme: {now.strftime('%d %B %H:%M')}"
    return text

def create_vip_banner(predictions):
    now = datetime.now(timezone.utc)
    text = f"🤖 🔥 VIP KUPON 🎯 | {now.strftime('%d %B %H:%M')}\n"
    text += "━━━━━━━━━━━━━━━\n"
    for i, p in enumerate(predictions, start=1):
        home = p.get("home")
        away = p.get("away")
        odds = p.get("odds")
        confidence = int(p.get("confidence",0)*100)
        match_date = p.get("date", now.isoformat())
        text += f"⚽️ {i}. {home} vs {away} | {match_date} 🌍\n"
        text += f"🎯 Tahmin: {p.get('prediction','-')} • 💰 Oran: {odds:.2f}\n"
        text += f"🌟 Güven: {confidence}%\n"
    return text

def create_live_banner(predictions):
    now = datetime.now(timezone.utc)
    text = f"🤖 ⏱️ CANLI MAÇ 🎯 | {now.strftime('%d %B %H:%M')}\n"
    text += "━━━━━━━━━━━━━━━\n"
    for i, p in enumerate(predictions, start=1):
        home = p.get("home")
        away = p.get("away")
        odds = p.get("odds")
        text += f"⚽️ {home} vs {away} | 🎯 Tahmin: {p.get('prediction','-')} • 💰 Oran: {odds:.2f}\n"
    return text
