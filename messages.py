# ================== messages.py — STAKEDRIP AI ULTRA v5.0+ ==================
import random

SPORT_EMOJIS = {
    "football": "⚽️",
    "basketball": "🏀",
    "tennis": "🎾"
}

def create_live_banner(predictions):
    header = (
        "🔥🔥🔥 <b>STAKEDRIP AI CANLI TAHMİNLER</b> 🔥🔥🔥\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⏱️ <i>Gerçek zamanlı verilerden üretilmiştir</i>\n\n"
    )
    lines = []
    for p in predictions:
        emoji = SPORT_EMOJIS.get(p["sport"], "🎯")
        bar = "⚡" * int(p["confidence"] * 10)
        lines.append(
            f"{emoji} <b>{p['home']}</b> vs <b>{p['away']}</b>\n"
            f"🏆 {p['league']}\n"
            f"📊 Tahmin: <b>{p['prediction']}</b>\n"
            f"💰 Oran: {p.get('odds', 1.0)}\n"
            f"⚡ Güven: {int(p['confidence']*100)}% {bar}\n"
            f"⏱️ Dakika: {p.get('minute', '-')}' | Skor: {p.get('score', '-')}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━"
        )
    footer = "\n🔥 <i>STAKEDRIP AI — canlı verilerle anlık kazanç</i> 🔥"
    return header + "\n".join(lines) + "\n" + footer


def create_daily_banner(picks):
    header = (
        "📅 <b>GÜNLÜK STAKEDRIP AI KUPONU</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    lines = []
    for p in picks:
        emoji = SPORT_EMOJIS.get(p["sport"], "🎯")
        lines.append(
            f"{emoji} {p['home']} vs {p['away']}\n"
            f"💡 Tahmin: <b>{p['prediction']}</b>\n"
            f"💰 Oran: {p.get('odds', 1.0)} | ⚡ {int(p['confidence']*100)}%\n"
            "━━━━━━━━━━━━━━━"
        )
    footer = "\n💎 <i>AI tarafından seçilen en güvenli 3 maç</i>"
    return header + "\n".join(lines) + footer


def create_vip_banner(picks):
    header = (
        "💎💎💎 <b>VIP KASA KUPONU</b> 💎💎💎\n"
        "🔥 <i>AI güven oranı: %90+</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    lines = []
    for p in picks:
        emoji = SPORT_EMOJIS.get(p["sport"], "🎯")
        lines.append(
            f"{emoji} <b>{p['home']}</b> - <b>{p['away']}</b>\n"
            f"💡 <b>{p['prediction']}</b> | 💰 {p.get('odds', 1.0)} | ⚡ {int(p['confidence']*100)}%\n"
            f"🏆 {p['league']}\n"
            "━━━━━━━━━━━━━━━"
        )
    footer = "\n🚀 <i>STAKEDRIP VIP — kasa odaklı yüksek güvenli kombin</i>"
    return header + "\n".join(lines) + footer
