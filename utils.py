# ================== messages.py — STAKEDRIP AI ULTRA v5.1 ==================
from utils import format_prediction_line, league_to_flag, EMOJI

# 🔴 Canlı Maç Banner
def create_live_banner(predictions):
    banner = f"{EMOJI['fire']} <b>CANLI YAPAY ZEKA TAHMİNLERİ</b> {EMOJI['fire']}\n"
    banner += "⚽ Basketbol 🏀 Tenis 🎾 dahil tüm dünyadan analiz!\n\n"
    for p in predictions:
        banner += format_prediction_line(p) + "\n\n"
    banner += "📡 Yapay zeka analizleri otomatik olarak güncellenir."
    return banner

# 📅 Günlük Kupon Banner
def create_daily_banner(picks):
    banner = f"{EMOJI['star']} <b>GÜNLÜK YAPAY ZEKA KUPONU</b> {EMOJI['star']}\n\n"
    for p in picks:
        banner += format_prediction_line(p) + "\n\n"
    banner += "🕓 Günlük analizler her sabah 10:00’da paylaşılır."
    return banner

# 💰 VIP (Kasa) Kupon Banner
def create_vip_banner(vip_picks):
    banner = f"{EMOJI['cash']} <b>VIP / KASA KUPONU</b> {EMOJI['lock']}\n\n"
    for p in vip_picks:
        banner += format_prediction_line(p) + "\n\n"
    banner += "💼 Sadece yüksek güven oranlı (%85+) maçlar içerir."
    return banner
