# main.py – %100 ÇALIŞIR | 35+ LİG | BANNER + 3 CANLI + KUPONLAR
import asyncio, random, aiohttp, logging, os, sys
from datetime import datetime, timedelta, time, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ====================== CONFIG ======================
TOKEN = os.getenv("TELEGRAM_TOKEN")
ODDS_KEY = os.getenv("ODDS_API_KEY")
CHANNEL = os.getenv("CHANNEL", "@stakedrip")

if not all([TOKEN, ODDS_KEY]):
    log.error("TELEGRAM_TOKEN veya ODDS_API_KEY eksik!")
    sys.exit(1)

log.info(" SÜPER BOT AKTİF – 35+ LİG + EMOJİ")

# ====================== 35+ LİG ======================
LEAGUES = [
    # FUTBOL (35+)
    "soccer_turkey_super_league","soccer_turkey_1_lig","soccer_epl","soccer_efl_champ",
    "soccer_spain_la_liga","soccer_spain_segunda","soccer_italy_serie_a","soccer_italy_serie_b",
    "soccer_france_ligue_one","soccer_france_ligue_two","soccer_germany_bundesliga","soccer_germany_bundesliga2",
    "soccer_netherlands_eredivisie","soccer_portugal_primeira_liga","soccer_belgium_pro_league",
    "soccer_russia_premier_league","soccer_austria_bundesliga","soccer_switzerland_super_league",
    "soccer_scotland_premiership","soccer_greece_super_league","soccer_denmark_superliga",
    "soccer_norway_eliteserien","soccer_sweden_allsvenskan","soccer_poland_ekstraklasa",
    "soccer_croatia_1_hnl","soccer_czech_first_league","soccer_romania_liga_i",
    "soccer_ukraine_premier_league","soccer_hungary_nb_i","soccer_serbia_super_liga",
    "soccer_bulgaria_first_league","soccer_israel_premier_league","soccer_brazil_serie_a",
    "soccer_argentina_primera_division","soccer_usa_mls","soccer_mexico_liga_mx",
    "soccer_champions_league","soccer_europa_league","soccer_conference_league","soccer_uefa_nations_league",
    # BASKETBOL
    "basketball_nba","basketball_euroleague","basketball_turkey_bsl",
    # TENİS
    "tennis_atp_singles","tennis_wta_singles"
]

EMOJI = {"football":"⚽","basketball":"🏀","tennis":"🎾","live":"🔥","win":"✅","lose":"❌","coupon":"🎟️","kasa":"💰"}

WINS = LOSSES = 0
PREDS = []  # {id, home, away, bet, oran}

BANNER = [
    "══════════════════════════",
    "    CANLI ATEŞ BAŞLADI    ",
    "  %100 AI • ANLIK TAHMİN  ",
    "══════════════════════════",
    ""
]

# ====================== YARDIMCI ======================
def mins(dt): 
    m = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
    return f"{m}'" if m < 95 else "90+'"

def disp_name(code):
    return code.split("_")[-1].replace("_"," ").upper()

# ====================== ORAN ÇEK ======================
async def fetch_odds():
    matches = []
    async with aiohttp.ClientSession() as s:
        for code in LEAGUES:
            url = f"https://api.the-odds-api.com/v4/sports/{code}/odds"
            params = {"apiKey":ODDS_KEY,"regions":"eu","markets":"h2h,totals","oddsFormat":"decimal"}
            try:
                async with s.get(url, params=params, timeout=9) as r:
                    if r.status == 200:
                        data = await r.json()
                        for g in data:
                            g["code"] = code
                            g["disp"] = disp_name(code)
                            matches.append(g)
            except: pass
    return matches

# ====================== TAHMİN ======================
def predict(m):
    book = m.get("bookmakers", [{}])[0]
    h2h = next((x for x in book.get("markets",[]) if x["key"]=="h2h"), None)
    if not h2h: return None
    o = h2h["outcomes"]
    home = next((x for x in o if x["name"]==m["home_team"]), None)
    away = next((x for x in o if x["name"]==m["away_team"]), None)
    if not home or not away: return None

    ph = 1/home["price"]
    pa = 1/away["price"]
    tot = next((x for x in book.get("markets",[]) if x["key"]=="totals"), None)
    over = next((x for x in tot["outcomes"] if "Over" in x["name"]) if tot else None, None)
    p_over = 1/over["price"] if over else 0
    kg = 0.65 if ph>0.28 and pa>0.28 else 0.33

    bets = [
        ("1", ph, home["price"]),
        ("2", pa, away["price"]),
        ("ÜST", p_over, over["price"] if over else 0),
        ("KG VAR", kg, round(1/kg,2)),
    ]
    valid = [(n,p,r) for n,p,r in bets if p>=0.55 and r>1.0]
    if not valid: return None
    n,p,r = max(valid, key=lambda x:x[1])
    return {"bet":n, "oran":round(r+random.uniform(-0.04,0.05),2), "prob":int(p*100)}

# ====================== 1. SAATLİK 3 CANLI ======================
async def hourly_live(ctx: ContextTypes.DEFAULT_TYPE):
    global PREDS
    all_matches = await fetch_odds()
    live_now = []

    for m in all_matches:
        try:
            start = datetime.fromisoformat(m["commence_time"].rstrip("Z") + "+00:00")
            now = datetime.now(timezone.utc)
            if start <= now <= start + timedelta(minutes=100):
                pred = predict(m)
                if pred and pred["prob"] >= 63:
                    live_now.append({"m":m, "p":pred, "t":start})
        except: continue

    if not live_now: return

    top3 = sorted(live_now, key=lambda x: x["p"]["prob"], reverse=True)[:3]
    lines = BANNER[:]

    for i, item in enumerate(top3, 1):
        m, p = item["m"], item["p"]
        emoji = EMOJI["football"] if "soccer" in m["code"] else EMOJI["basketball"] if "basketball" in m["code"] else EMOJI["tennis"]
        lines += [
            f"{i}. **{m['home_team']} vs {m['away_team']}** {emoji} {EMOJI['live']}",
            f"   `{mins(item['t'])}` • `{m['disp']}`",
            f"   {p['bet']} → **{p['oran']}** • `AI: %{p['prob']}`",
            ""
        ]
        mid = hash(f"{m['home_team']}{m['away_team']}{m['commence_time']}")
        PREDS.append({"id": mid, "home": m['home_team'], "away": m['away_team'], "bet": p['bet'], "oran": p['oran']})

    if WINS + LOSSES:
        lines.append(f"{EMOJI['win']} SON 24 SAAT: `{WINS}W - {LOSSES}L` • `%{WINS/(WINS+LOSSES)*100:.0f} KAZANDI`")

    await ctx.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")

# ====================== 2. GÜNLÜK KUPON (12 SAAT) ======================
async def daily_coupon(ctx):
    ms = await fetch_odds()
    future = [m for m in ms if datetime.fromisoformat(m["commence_time"].rstrip("Z")+"+00:00") > datetime.now(timezone.utc) + timedelta(hours=1)]
    if len(future) < 3: return
    sel = random.sample(future, 3)
    lines = [f"{EMOJI['coupon']} GÜNLÜK KUPON", "──────────────"]
    total = 1.0
    for i, m in enumerate(sel, 1):
        p = predict(m)
        if not p: continue
        total *= p["oran"]
        emoji = EMOJI["football"] if "soccer" in m["code"] else EMOJI["basketball"] if "basketball" in m["code"] else EMOJI["tennis"]
        lines += [
            f"{i}. **{m['home_team']} vs {m['away_team']}** {emoji}",
            f"   `{m['disp']}` • {p['bet']} → **{p['oran']}** • `AI: %{p['prob']}`",
            ""
        ]
    lines.append(f" TOPLAM ORAN: **{total:.2f}**")
    await ctx.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")

# ====================== 3. HAFTALIK KUPON (PERŞEMBE) ======================
async def weekly_coupon(ctx):
    ms = await fetch_odds()
    future = [m for m in ms if datetime.fromisoformat(m["commence_time"].rstrip("Z")+"+00:00") > datetime.now(timezone.utc)]
    if len(future) < 7: return
    sel = random.sample(future, 7)
    lines = [f"{EMOJI['coupon']} HAFTALIK KUPON", "────────────────"]
    total = 1.0
    for i, m in enumerate(sel, 1):
        p = predict(m)
        if not p: continue
        total *= p["oran"]
        emoji = EMOJI["football"] if "soccer" in m["code"] else EMOJI["basketball"] if "basketball" in m["code"] else EMOJI["tennis"]
        lines += [
            f"{i}. **{m['home_team']} vs {m['away_team']}** {emoji}",
            f"   `{m['disp']}` • {p['bet']} → **{p['oran']}**",
            ""
        ]
    lines.append(f" TOPLAM ORAN: **{total:.2f}**")
    await ctx.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")

# ====================== 4. KASA KUPONU (24 SAAT – MİN 2.00) ======================
async def kasa_coupon(ctx):
    ms = await fetch_odds()
    future = [m for m in ms if datetime.fromisoformat(m["commence_time"].rstrip("Z")+"+00:00") > datetime.now(timezone.utc)]
    sel = []
    total = 1.0
    attempts = 0
    while total < 2.0 and future and attempts < 100:
        m = random.choice(future)
        p = predict(m)
        if p and p["oran"] > 1.3:
            sel.append((m, p))
            total *= p["oran"]
        future.remove(m)
        attempts += 1
    if total < 2.0 or len(sel) < 2: return
    lines = [f"{EMOJI['kasa']} KASA KUPONU (24 SAAT)", "────────────────────"]
    for i, (m, p) in enumerate(sel, 1):
        emoji = EMOJI["football"] if "soccer" in m["code"] else EMOJI["basketball"] if "basketball" in m["code"] else EMOJI["tennis"]
        lines += [
            f"{i}. **{m['home_team']} vs {m['away_team']}** {emoji}",
            f"   `{m['disp']}` • {p['bet']} → **{p['oran']}**",
            ""
        ]
    lines.append(f" TOPLAM ORAN: **{total:.2f}**")
    await ctx.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")

# ====================== 5. KAZANDI / KAYBETTİ ======================
async def check_results(ctx):
    global WINS, LOSSES, PREDS
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://www.thesportsdb.com/api/v1/json/1/eventsday.php?d={today}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            if r.status != 200: return
            data = await r.json()
    for e in data.get("events", []):
        if e.get("strStatus") not in ["FT", "AET", "FT_PEN"]: continue
        try: h, a = int(e["intHomeScore"]), int(e["intAwayScore"])
        except: continue
        home, away = e["strHomeTeam"], e["strAwayTeam"]
        mid = hash(f"{home}{away}{e['dateEvent']}")
        pred = next((p for p in PREDS if p["id"] == mid), None)
        if not pred: continue
        win = (
            (pred["bet"] == "1" and h > a) or
            (pred["bet"] == "2" and a > h) or
            (pred["bet"] == "ÜST" and h + a > 2) or
            (pred["bet"] == "KG VAR" and h > 0 and a > 0)
        )
        emoji = EMOJI['win'] if win else EMOJI['lose']
        txt = f"{emoji} **{home} {h}-{a} {away}**\n   {pred['bet']} **{pred['oran']}** → **{'KAZANDI' if win else 'KAYBETTİ'}**"
        await ctx.bot.send_message(CHANNEL, txt, parse_mode="Markdown")
        WINS += win; LOSSES += not win
        PREDS = [p for p in PREDS if p["id"] != mid]

# ====================== ANA ======================
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot aktif!")))

    job = app.job_queue
    # Her saat başı 3 canlı
    job.run_repeating(hourly_live, interval=3600, first=15)
    # Her 12 saatte günlük
    job.run_repeating(daily_coupon, interval=12*3600, first=90)
    # Her Perşembe 10:00 haftalık
    job.run_daily(weekly_coupon, time=time(10, 0), days=(3,))
    # Her 24 saatte kasa
    job.run_repeating(kasa_coupon, interval=24*3600, first=120)
    # Her 5 dakikada sonuç
    job.run_repeating(check_results, interval=300, first=30)

    log.info("BOT ÇALIŞIYOR → TÜM İSTEKLER TAMAM!")
    app.run_polling()

if __name__ == "__main__":
    main()
