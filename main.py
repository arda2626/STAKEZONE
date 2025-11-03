# ================== main.py — STAKEDRIP AI ULTRA Webhook Free v5.15 ==================
import asyncio, logging
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler, JobQueue, ContextTypes
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn

from db import init_db, DB_PATH, mark_posted, was_posted_recently
from fetch_matches_free import fetch_all_matches
from prediction import ai_predict

# ================= CONFIG =================
TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
DB_FILE = DB_PATH

MIN_CONFIDENCE = 0.60
MIN_CONFIDENCE_VIP = 0.80
MIN_ODDS = 1.20
WEBHOOK_PATH = "/stakedrip"
WEBHOOK_URL = "https://yourdomain.com" + WEBHOOK_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("stakedrip")

# ================== BAYRAK FONKSİYONU ==================
def country_to_flag(country_name):
    mapping = {
        "Afghanistan": "🇦🇫","Albania": "🇦🇱","Algeria": "🇩🇿","Andorra": "🇦🇩","Angola": "🇦🇴",
        "Argentina": "🇦🇷","Armenia": "🇦🇲","Australia": "🇦🇺","Austria": "🇦🇹","Azerbaijan": "🇦🇿",
        "Bahamas": "🇧🇸","Bahrain": "🇧🇭","Bangladesh": "🇧🇩","Barbados": "🇧🇧","Belarus": "🇧🇾",
        "Belgium": "🇧🇪","Belize": "🇧🇿","Benin": "🇧🇯","Bhutan": "🇧🇹","Bolivia": "🇧🇴",
        "Bosnia and Herzegovina": "🇧🇦","Botswana": "🇧🇼","Brazil": "🇧🇷","Brunei": "🇧🇳","Bulgaria": "🇧🇬",
        "Burkina Faso": "🇧🇫","Burundi": "🇧🇮","Cambodia": "🇰🇭","Cameroon": "🇨🇲","Canada": "🇨🇦",
        "Cape Verde": "🇨🇻","Central African Republic": "🇨🇫","Chad": "🇹🇩","Chile": "🇨🇱","China": "🇨🇳",
        "Colombia": "🇨🇴","Comoros": "🇰🇲","Congo": "🇨🇬","Costa Rica": "🇨🇷","Croatia": "🇭🇷",
        "Cuba": "🇨🇺","Cyprus": "🇨🇾","Czech Republic": "🇨🇿","Denmark": "🇩🇰","Djibouti": "🇩🇯",
        "Dominica": "🇩🇲","Dominican Republic": "🇩🇴","Ecuador": "🇪🇨","Egypt": "🇪🇬","El Salvador": "🇸🇻",
        "Equatorial Guinea": "🇬🇶","Eritrea": "🇪🇷","Estonia": "🇪🇪","Eswatini": "🇸🇿","Ethiopia": "🇪🇹",
        "Fiji": "🇫🇯","Finland": "🇫🇮","France": "🇫🇷","Gabon": "🇬🇦","Gambia": "🇬🇲","Georgia": "🇬🇪",
        "Germany": "🇩🇪","Ghana": "🇬🇭","Greece": "🇬🇷","Grenada": "🇬🇩","Guatemala": "🇬🇹","Guinea": "🇬🇳",
        "Guinea-Bissau": "🇬🇼","Guyana": "🇬🇾","Haiti": "🇭🇹","Honduras": "🇭🇳","Hungary": "🇭🇺",
        "Iceland": "🇮🇸","India": "🇮🇳","Indonesia": "🇮🇩","Iran": "🇮🇷","Iraq": "🇮🇶","Ireland": "🇮🇪",
        "Israel": "🇮🇱","Italy": "🇮🇹","Ivory Coast": "🇨🇮","Jamaica": "🇯🇲","Japan": "🇯🇵",
        "Jordan": "🇯🇴","Kazakhstan": "🇰🇿","Kenya": "🇰🇪","Kiribati": "🇰🇮","Kosovo": "🇽🇰",
        "Kuwait": "🇰🇼","Kyrgyzstan": "🇰🇬","Laos": "🇱🇦","Latvia": "🇱🇻","Lebanon": "🇱🇧",
        "Lesotho": "🇱🇸","Liberia": "🇱🇷","Libya": "🇱🇾","Liechtenstein": "🇱🇮","Lithuania": "🇱🇹",
        "Luxembourg": "🇱🇺","Madagascar": "🇲🇬","Malawi": "🇲🇼","Malaysia": "🇲🇾","Maldives": "🇲🇻",
        "Mali": "🇲🇱","Malta": "🇲🇹","Marshall Islands": "🇲🇭","Mauritania": "🇲🇷","Mauritius": "🇲🇺",
        "Mexico": "🇲🇽","Micronesia": "🇫🇲","Moldova": "🇲🇩","Monaco": "🇲🇨","Mongolia": "🇲🇳",
        "Montenegro": "🇲🇪","Morocco": "🇲🇦","Mozambique": "🇲🇿","Myanmar": "🇲🇲","Namibia": "🇳🇦",
        "Nauru": "🇳🇷","Nepal": "🇳🇵","Netherlands": "🇳🇱","New Zealand": "🇳🇿","Nicaragua": "🇳🇮",
        "Niger": "🇳🇪","Nigeria": "🇳🇬","North Macedonia": "🇲🇰","Norway": "🇳🇴","Oman": "🇴🇲",
        "Pakistan": "🇵🇰","Palau": "🇵🇼","Palestine": "🇵🇸","Panama": "🇵🇦","Papua New Guinea": "🇵🇬",
        "Paraguay": "🇵🇾","Peru": "🇵🇪","Philippines": "🇵🇭","Poland": "🇵🇱","Portugal": "🇵🇹",
        "Qatar": "🇶🇦","Romania": "🇷🇴","Russia": "🇷🇺","Rwanda": "🇷🇼","Saint Kitts and Nevis": "🇰🇳",
        "Saint Lucia": "🇱🇨","Saint Vincent and the Grenadines": "🇻🇨","Samoa": "🇼🇸","San Marino": "🇸🇲",
        "Sao Tome and Principe": "🇸🇹","Saudi Arabia": "🇸🇦","Senegal": "🇸🇳","Serbia": "🇷🇸","Seychelles": "🇸🇨",
        "Sierra Leone": "🇸🇱","Singapore": "🇸🇬","Slovakia": "🇸🇰","Slovenia": "🇸🇮","Solomon Islands": "🇸🇧",
        "Somalia": "🇸🇴","South Africa": "🇿🇦","South Korea": "🇰🇷","South Sudan": "🇸🇸","Spain": "🇪🇸",
        "Sri Lanka": "🇱🇰","Sudan": "🇸🇩","Suriname": "🇸🇷","Sweden": "🇸🇪","Switzerland": "🇨🇭","Syria": "🇸🇾",
        "Taiwan": "🇹🇼","Tajikistan": "🇹🇯","Tanzania": "🇹🇿","Thailand": "🇹🇭","Togo": "🇹🇬",
        "Tonga": "🇹🇴","Trinidad and Tobago": "🇹🇹","Tunisia": "🇹🇳","Turkey": "🇹🇷","Turkmenistan": "🇹🇲",
        "Tuvalu": "🇹🇻","Uganda": "🇺🇬","Ukraine": "🇺🇦","United Arab Emirates": "🇦🇪","United Kingdom": "🇬🇧",
        "USA": "🇺🇸","Uruguay": "🇺🇾","Uzbekistan": "🇺🇿","Vanuatu": "🇻🇺","Vatican City": "🇻🇦",
        "Venezuela": "🇻🇪","Vietnam": "🇻🇳","Yemen": "🇾🇪","Zambia": "🇿🇲","Zimbabwe": "🇿🇼"
    }
    return mapping.get(country_name, "")

# ================= BANNER FONKSİYONLARI =================
def create_banner(picks, title):
    lines = []
    for p in picks:
        home_flag = country_to_flag(p.get("home_country",""))
        away_flag = country_to_flag(p.get("away_country",""))
        match_time = p.get("date")
        if match_time:
            dt = datetime.fromisoformat(match_time).astimezone(timezone(timedelta(hours=3)))
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        else:
            time_str = "—"
        # Canlı maç ise dakika ekle
        minute = p.get("minute")
        if minute:
            time_str += f" ({minute}')"
        lines.append(f"{home_flag} {p['home']} vs {away_flag} {p['away']} | ⏱️ {time_str} | {p.get('bet','Tahmin Yok')}, {p.get('odds',1.5):.2f}")
    return f"<b>{title}</b>\n" + "\n".join(lines)

def create_daily_banner(picks):
    return create_banner(picks, "Günlük Kupon")

def create_vip_banner(picks):
    return create_banner(picks, "VIP Kupon")

def create_live_banner(picks):
    return create_banner(picks, "Canlı Maçlar")

# ================= JOB FUNCTIONS =================
# (daily_coupon_job, vip_coupon_job, hourly_live_job aynen korunur,
# sadece banner fonksiyonlarını yeni versiyonla çağırır)

# ================= ADMIN COMMAND =================
async def test_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await daily_coupon_job(context)
    await update.message.reply_text("Test: Günlük kupon çalıştırıldı.")

async def test_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vip_coupon_job(context)
    await update.message.reply_text("Test: VIP kupon çalıştırıldı.")

async def test_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await hourly_live_job(context)
    await update.message.reply_text("Test: Canlı maç kuponu çalıştırıldı.")

# ================= FASTAPI + TELEGRAM =================
fastapi_app = FastAPI()
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

telegram_app.add_handler(CommandHandler("test_daily", test_daily))
telegram_app.add_handler(CommandHandler("test_vip", test_vip))
telegram_app.add_handler(CommandHandler("test_live", test_live))

@fastapi_app.on_event("startup")
async def startup():
    init_db(DB_FILE)
    log.info("✅ Database initialized")

    jq: JobQueue = telegram_app.job_queue
    jq.run_repeating(daily_coupon_job, interval=3600*12, first=10, name="daily_coupon")
    jq.run_repeating(vip_coupon_job, interval=3600*24, first=20, name="vip_coupon")
    jq.run_repeating(hourly_live_job, interval=3600, first=30, name="hourly_live")

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    log.info(f"Webhook set to {WEBHOOK_URL}")
    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA Free APIs")

@fastapi_app.on_event("shutdown")
async def shutdown():
    await telegram_app.bot.delete_webhook()
    await telegram_app.stop()
    log.info("Bot stopped")

@fastapi_app.post(WEBHOOK_PATH)
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8443)
