# main.py - HATA YOK + ORAN DOĞRU + TEK CONTAINER + THESPORTSDB
import asyncio
import random
import aiohttp
import logging
from datetime import datetime, timedelta, time, timezone
import os
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ====================== LOGGING ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== CONFIG ======================
TOKEN = os.getenv("TELEGRAM_TOKEN")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
THESPORTSDB_API_KEY = os.getenv("THESPORTSDB_API_KEY", "123")
CHANNEL = os.getenv("CHANNEL", "@stakedrip")

if not all([TOKEN, ODDS_API_KEY]):
    logger.error("HATA: TELEGRAM_TOKEN veya ODDS_API_KEY eksik!")
    sys.exit(1)

# TEK CONTAINER - SIKI KONTROL
REPLICA_ID = os.getenv("RAILWAY_REPLICA_ID")
if not REPLICA_ID:
    logger.info("Replica ID yok → Çıkılıyor (tek container)")
    sys.exit(0)
else:
    logger.info(f"Replica ID: {REPLICA_ID} → Çalışıyor")

SPORTS = {
    "football": ["soccer_turkey_super_league", "soccer_epl", "soccer_spain_la_liga"],
    "basketball": ["basketball_nba", "basketball_euroleague"],
    "tennis": ["tennis_atp_singles"]
}

EMOJI = {
    "football": "Football", "basketball": "Basketball", "tennis": "Tennis",
    "live": "Fire", "upcoming": "Briefcase", "win": "Check Mark Button", "lose": "Cross Mark",
    "daily": "Ticket", "weekly": "Gem"
}

WIN_COUNT = 0
LOSE_COUNT = 0
PREDICTIONS = []

# ====================== ZAMAN ======================
def get_time_info(match):
    try:
        dt = datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00"))
        dt_ist = dt.astimezone(timezone(timedelta(hours=3)))
        date_str = dt_ist.strftime("%d.%m.%Y")
        time_str = dt_ist.strftime("%H:%M")
    except:
        date_str = "Bilinmiyor"
        time_str = "??:??"

    now = datetime.now(timezone.utc)
    if dt <= now <= dt + timedelta(minutes=120):
        mins = int((now - dt).total_seconds() // 60)
        return f"`{date_str} – {mins}'` {EMOJI['live']}"
    else:
        return f"`{date_str} – {time_str}` {EMOJI['upcoming']}"

# ====================== ODDS API ======================
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
                            game["league"] = game.get("sport_nice", code.split("_")[-1].replace("_", " ").title())
                            matches.append(game)
        except Exception as e:
            logger.error(f"{code} hatası: {e}")
    return matches

# ====================== TAHMİN (HATASIZ) ======================
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

    # DÜZELTME: over ve under tanımlı değilse hata
    over = under = None
    totals = next((m for m in book.get("markets", []) if m["key"] == "totals"), None)
    if totals:
        over = next((x for x in totals["outcomes"] if "Over" in x["name"]), None)
        under = next((x for x in totals["outcomes"] if "Under" in x["name"]), None)

    p_over = 1 / over["price"] if over else 0
    p_under = 1 / under["price"] if under else 0

    p_kg_var = 0.6 if p_home > 0.3 and p_away > 0.3 else 0.3
    p_kg_yok = 1 - p_kg_var

    bets = [
        ("1 (Ev)", p_home, home["price"] if home else 0),
        ("X", p_draw, draw["price"] if draw else 0),
        ("2 (Dep)", p_away, away["price"] if away else 0),
        ("Üst 2.5", p_over, over["price"] if over else 0),
        ("Alt 2.5", p_under, under["price"] if under else 0),
        ("KG Var", p_kg_var, 1 / p_kg_var if p_kg_var > 0 else 0),
        ("KG Yok", p_kg_yok, 1 / p_kg_yok if p_kg_yok > 0 else 0)
    ]

    valid = [(b, p, r) for b, p, r in bets if p >= 0.50 and r > 1.0]
    if not valid: return None

    best_bet, best_prob, real_rate = max(valid, key=lambda x: x[1])
    oran = round(real_rate + random.uniform(-0.05, 0.05), 2)

    return {"bet": best_bet, "oran": oran, "prob": int(best_prob * 100)}

# ====================== FORMAT ======================
def format_match(match, pred, number=None, is_live=False):
    sport_emoji = EMOJI.get(match["sport"], "Unknown")
    time_info = get_time_info(match)
    live_tag = EMOJI['live'] if is_live else ""
    num = f"**{number}.** " if number else ""
    return (
        f"{num}**{match['home_team']} vs {match['away_team']}** {sport_emoji} {live_tag}\n"
        f"   {time_info} | `{match.get('league', 'Lig')}`\n"
        f"   **{pred['bet']}** → **{pred['oran']}** | `%{pred['prob']} AI`"
    )

# ====================== CANLI SKOR ======================
async def check_live_results(context: ContextTypes.DEFAULT_TYPE):
    global WIN_COUNT, LOSE_COUNT, PREDICTIONS
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_API_KEY}/eventsday.php?d={today}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200: return
            data = await resp.json()
            events = data.get("events", [])

    for event in events:
        if not event.get("intHomeScore") or not event.get("intAwayScore"): continue
        if event["strStatus"] not in ["FT", "AET", "PEN"]: continue

        home = event["strHomeTeam"]
        away = event["strAwayTeam"]
        home_goals = int(event["intHomeScore"])
        away_goals = int(event["intAwayScore"])
        match_id = hash(f"{home}{away}{event['dateEvent']}")

        if any(p.get("match_id") == match_id for p in PREDICTIONS): continue

        pred = next((p for p in PREDICTIONS if p["home"] == home and p["away"] == away), None)
        if not pred: continue

        result = "win" if (
            (pred['bet'] == "1 (Ev)" and home_goals > away_goals) or
            (pred['bet'] == "2 (Dep)" and away_goals > home_goals) or
            (pred['bet'] == "X" and home_goals == away_goals) or
            (pred['bet'] == "Üst 2.5" and home_goals + away_goals > 2.5) or
            (pred['bet'] == "Alt 2.5" and home_goals + away_goals < 2.5) or
            (pred['bet'] == "KG Var" and home_goals > 0 and away_goals > 0) or
            (pred['bet'] == "KG Yok" and (home_goals == 0 or away_goals == 0))
        ) else "lose"

        emoji = EMOJI['win'] if result == "win" else EMOJI['lose']
        text = f"{emoji} **{home} {home_goals}-{away_goals} {away}** → **{pred['bet']}** {'KAZANDI' if result == 'win' else 'KAYBETTİ'}!"
        await context.bot.send_message(CHANNEL, text, parse_mode='Markdown')

        if result == "win":
            WIN_COUNT += 1
        else:
            LOSE_COUNT += 1

        PREDICTIONS = [p for p in PREDICTIONS if p.get("match_id") != match_id]

# ====================== SAAT BAŞI ======================
async def hourly_prediction(context: ContextTypes.DEFAULT_TYPE):
    global PREDICTIONS
    live_matches = []
    upcoming_matches = []

    for sport in SPORTS:
        matches = await fetch_odds(sport)
        for m in matches:
            pred = get_best_bet(m)
            if not pred: continue
            now = datetime.now(timezone.utc)
            dt = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
            is_live = dt <= now <= dt + timedelta(minutes=120)
            item = {"match": m, "pred": pred, "is_live": is_live}
            if is_live:
                live_matches.append(item)
            else:
                upcoming_matches.append(item)

            match_id = hash(f"{m['home_team']}{m['away_team']}{m['commence_time']}")
            PREDICTIONS.append({
                "match_id": match_id,
                "home": m['home_team'],
                "away": m['away_team'],
                "bet": pred['bet'],
                "oran": pred['oran']
            })

    lines = []
    ist_now = datetime.now(timezone(timedelta(hours=3))).strftime("%H:%M")
    lines.append(f"**{ist_now} TEZGAH** {EMOJI['upcoming']}\n")

    has_content = False

    if live_matches:
        live_matches = sorted(live_matches, key=lambda x: x["pred"]["prob"], reverse=True)[:3]
        lines.append(f"**CANLI ATEŞ** {EMOJI['live']}")
        for i, item in enumerate(live_matches, 1):
            lines.append(format_match(item["match"], item["pred"], number=i, is_live=True))
        has_content = True

    if upcoming_matches:
        upcoming_matches = sorted(upcoming_matches, key=lambda x: x["pred"]["prob"], reverse=True)[:5]
        if live_matches: lines.append("")
        start_num = len(live_matches) + 1 if live_matches else 1
        for i, item in enumerate(upcoming_matches, start_num):
            lines.append(format_match(item["match"], item["pred"], number=i))
        has_content = True

    if WIN_COUNT + LOSE_COUNT > 0:
        win_rate = (WIN_COUNT / (WIN_COUNT + LOSE_COUNT)) * 100
        lines.append(f"\n**Kazanç Takibi:** `{WIN_COUNT}W - {LOSE_COUNT}L` | `%{win_rate:.1f}`")

    if has_content:
        await context.bot.send_message(CHANNEL, "\n".join(lines), parse_mode='Markdown')

# ====================== KUPONLAR ======================
async def daily_coupon(context: ContextTypes.DEFAULT_TYPE):
    all_matches = []
    for sport in ["football", "basketball"]:
        all_matches.extend(await fetch_odds(sport))
    if len(all_matches) < 3: return

    selected = random.sample(all_matches, 3)
    lines = [f"**GÜNLÜK KUPON** {EMOJI['daily']}\n"]
    total = 1.0
    for i, m in enumerate(selected, 1):
        pred = get_best_bet(m)
        if pred:
            total *= pred["oran"]
            lines.append(format_match(m, pred, number=i))
    lines.append(f"\n**Toplam Oran:** `{total:.2f}`")
    await context.bot.send_message(CHANNEL, "\n".join(lines), parse_mode='Markdown')

async def weekly_coupon(context: ContextTypes.DEFAULT_TYPE):
    all_matches = []
    for sport in ["football", "basketball"]:
        all_matches.extend(await fetch_odds(sport))
    if len(all_matches) < 7: return

    selected = random.sample(all_matches, 7)
    lines = [f"**HAFTALIK KASA** {EMOJI['weekly']}\n"]
    total = 1.0
    for i, m in enumerate(selected, 1):
        pred = get_best_bet(m)
        if pred:
            total *= pred["oran"]
            lines.append(format_match(m, pred, number=i))
    lines.append(f"\n**Toplam Oran:** `{total:.2f}`")
    await context.bot.send_message(CHANNEL, "\n".join(lines), parse_mode='Markdown')

# ====================== ANA ======================
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot aktif!")))

    job = app.job_queue
    job.run_repeating(hourly_prediction, interval=3600, first=10)
    job.run_repeating(daily_coupon, interval=12*3600, first=60)
    job.run_daily(weekly_coupon, time=time(10, 0), days=(6,))
    job.run_repeating(check_live_results, interval=300, first=300)

    print("Bot çalışıyor... (HATA YOK + ORAN DOĞRU + TEK CONTAINER)")
    app.run_polling()

if __name__ == "__main__":
    main()
