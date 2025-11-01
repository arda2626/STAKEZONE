# main.py - RENKLİ + CANLI AYRI + TEMİZ FORMAT
import asyncio
import random
import aiohttp
import logging
from datetime import datetime, timedelta, time, timezone
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ====================== LOGGING ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== CONFIG ======================
TOKEN = os.getenv("TELEGRAM_TOKEN")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
CHANNEL = os.getenv("CHANNEL", "@stakedrip")

if not ODDS_API_KEY:
    logger.error("HATA: ODDS_API_KEY eksik!")
    exit(1)

SPORTS = {
    "football": ["soccer_turkey_super_league", "soccer_epl", "soccer_spain_la_liga"],
    "basketball": ["basketball_nba", "basketball_euroleague"],
    "tennis": ["tennis_atp_singles"]
}

# ====================== ZAMAN (GMT+3) ======================
def get_time_info(match):
    try:
        dt = datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00"))
        dt_ist = dt.astimezone(timezone(timedelta(hours=3)))
        time_str = dt_ist.strftime("%H:%M")
    except:
        time_str = "??:??"

    now = datetime.now(timezone.utc)
    if dt <= now <= dt + timedelta(minutes=120):
        mins = int((now - dt).total_seconds() // 60)
        return f"`{mins}'` Dakika `Fire`"
    else:
        return f"`{time_str}` Başlayacak"

# ====================== API ======================
async def fetch_odds(sport: str):
    matches = []
    for code in SPORTS.get(sport, []):
        url = f"https://api.the-odds-api.com/v4/sports/{code}/odds"
        params = {"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "h2h,totals", "oddsFormat": "decimal"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for game in data:
                            game["sport"] = sport
                            game["league"] = game.get("sport_nice", code.split("_")[-1].title())
                            matches.append(game)
        except Exception as e:
            logger.error(f"{code} hatası: {e}")
    return matches

# ====================== TAHMİN ======================
def get_best_bet(match):
    book = match.get("bookmakers", [{}])[0]
    h2h = next((m for m in book.get("markets", []) if m["key"] == "h2h"), None)
    if not h2h: return None

    o = h2h["outcomes"]
    home = next((x for x in o if x["name"] == match["home_team"]), None)
    away = next((x for x in o if x["name"] == match["away_team"]), None)
    draw = next((x for x in o if x["name"] == "Draw"), None)

    p_home = 1 / home["price"] if home else 0
    p_away = 1 / away["price"] if away else 0
    p_draw = 1 / draw["price"] if draw else 0

    totals = next((m for m in book.get("markets", []) if m["key"] == "totals"), None)
    p_over = p_under = 0
    if totals:
        over = next((x for x in totals["outcomes"] if "Over" in x["name"]), None)
        under = next((x for x in totals["outcomes"] if "Under" in x["name"]), None)
        p_over = 1 / over["price"] if over else 0
        p_under = 1 / under["price"] if under else 0

    p_kg_var = 0.6 if p_home > 0.3 and p_away > 0.3 else 0.3
    p_kg_yok = 1 - p_kg_var

    bets = [
        ("1 (Ev Sahibi)", p_home),
        ("X (Berabere)", p_draw),
        ("2 (Deplasman)", p_away),
        ("Üst 2.5", p_over),
        ("Alt 2.5", p_under),
        ("KG Var", p_kg_var),
        ("KG Yok", p_kg_yok)
    ]

    valid = [b for b in bets if b[1] >= 0.50]
    if not valid: return None

    best, prob = max(valid, key=lambda x: x[1])
    return {"bet": best, "oran": round(prob * 2.8 + random.uniform(-0.2, 0.3), 2), "prob": int(prob * 100)}

# ====================== FORMAT ======================
def format_match(match, pred, is_live=False):
    emoji = {"football": "Football", "basketball": "Basketball", "tennis": "Tennis"}.get(match["sport"], "Unknown")
    time_info = get_time_info(match)
    live_tag = "`CANLI ATEŞ`" if is_live else ""
    return (
        f"**{match['home_team']} vs {match['away_team']}** {emoji} {live_tag}\n"
        f"{time_info} | `{match.get('league', 'Lig')}`\n"
        f"**{pred['bet']}** → **{pred['oran']}** | `%{pred['prob']} AI`"
    )

# ====================== SAAT BAŞI (CANLI + YAKLAŞAN AYRI) ======================
async def hourly_prediction(context: ContextTypes.DEFAULT_TYPE):
    live_matches = []
    upcoming_matches = []

    for sport in ["football", "basketball", "tennis"]:
        matches = await fetch_odds(sport)
        for m in matches:
            pred = get_best_bet(m)
            if not pred: continue
            now = datetime.now(timezone.utc)
            dt = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
            if dt <= now <= dt + timedelta(minutes=120):
                live_matches.append({"match": m, "pred": pred})
            else:
                upcoming_matches.append({"match": m, "pred": pred})

    lines = []

    # CANLI MAÇLAR
    if live_matches:
        live_matches.sort(key=lambda x: x["pred"]["prob"], reverse=True)[:3]
        lines.append("**`CANLI ATEŞ` TEZGAH** `Fire`")
        for item in live_matches:
            lines.append(format_match(item["match"], item["pred"], is_live=True))

    # YAKLAŞAN MAÇLAR
    if upcoming_matches:
        upcoming_matches.sort(key=lambda x: x["pred"]["prob"], reverse=True)[:5]
        lines.append("\n**`YAKLAŞAN` TEZGAH** `Briefcase`")
        for item in upcoming_matches:
            lines.append(format_match(item["match"], item["pred"], is_live=False))

    if not lines:
        return

    msg = "\n".join(lines)
    await context.bot.send_message(CHANNEL, msg, parse_mode='Markdown')

# ====================== GÜNLÜK KUPON ======================
async def daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    all_matches = []
    for sport in ["football", "basketball"]:
        all_matches.extend(await fetch_odds(sport))

    if len(all_matches) < 3: return
    selected = random.sample(all_matches, 3)
    lines = ["**`GÜNLÜK KUPON` Ticket**"]
    total = 1.0
    for m in selected:
        pred = get_best_bet(m)
        if pred:
            total *= pred["oran"]
            lines.append(format_match(m, pred))
    lines.append(f"\n**Toplam Oran:** `{total:.2f}`")
    await context.bot.send_message(CHANNEL, "\n".join(lines), parse_mode='Markdown')

# ====================== HAFTALIK KUPON ======================
async def weekly_coupon(context: ContextTypes.DEFAULT_TYPE):
    all_matches = []
    for sport in ["football", "basketball"]:
        all_matches.extend(await fetch_odds(sport))

    if len(all_matches) < 7: return
    selected = random.sample(all_matches, 7)
    lines = ["**`HAFTALIK KASA` Gem**"]
    total = 1.0
    for m in selected:
        pred = get_best_bet(m)
        if pred:
            total *= pred["oran"]
            lines.append(format_match(m, pred))
    lines.append(f"\n**Toplam Oran:** `{total:.2f}`")
    await context.bot.send_message(CHANNEL, "\n".join(lines), parse_mode='Markdown')

# ====================== ANA ======================
def main():
    if not TOKEN:
        print("HATA: TELEGRAM_TOKEN eksik!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot aktif!")))

    job = app.job_queue
    job.run_repeating(hourly_prediction, interval=3600, first=10)
    job.run_repeating(daily_coupon, interval=12*3600, first=60)
    job.run_daily(weekly_coupon, time=time(10, 0), days=(6,))

    print("Bot çalışıyor... (RENKLİ + CANLI AYRI + TEMİZ)")
    app.run_polling()

if __name__ == "__main__":
    main()
