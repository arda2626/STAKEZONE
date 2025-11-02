# main.py – ATEŞLENDİ! 1.5 + 3.5 + KORNER + KART + SES
import asyncio, random, aiohttp, logging, os, sys
from datetime import datetime, timedelta, time, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
ODDS_KEY = os.getenv("ODDS_API_KEY")
CHANNEL = os.getenv("CHANNEL", "@stakedrip")

if not all([TOKEN, ODDS_KEY]):
    sys.exit(1)

# TEK BOT
if os.getenv("RAILWAY_REPLICA_ID", "1") != "1":
    sys.exit(0)

log.info(" ATEŞLENDİ – 1.5 + KORNER + SES")

LEAGUES = ["soccer_turkey_super_league","soccer_epl","soccer_spain_la_liga","soccer_champions_league",
           "basketball_nba","tennis_atp_singles"] + [f"soccer_{x}" for x in "italy_serie_a,france_ligue_one,germany_bundesliga".split(",")]

EMOJI = {"live":"🔥","win":"✅","lose":"❌","ding":"🔔","cash":"💰"}

WINS = LOSSES = 0
PREDS = []

BANNER = [
    "══════════════════════════",
    "    CANLI ATEŞ BAŞLADI    ",
    "  %100 AI • VİP STÜDYO  ",
    "══════════════════════════",
    ""
]

async def odds():
    ms = []
    async with aiohttp.ClientSession() as s:
        for c in LEAGUES:
            url = f"https://api.the-odds-api.com/v4/sports/{c}/odds"
            p = {"apiKey":ODDS_KEY,"regions":"eu","markets":"h2h,totals,player_corners,player_cards","oddsFormat":"decimal"}
            try:
                async with s.get(url,params=p,timeout=8) as r:
                    if r.status==200:
                        for g in await r.json():
                            g["code"]=c; g["disp"]=c.split("_")[-1].upper()
                            ms.append(g)
            except: pass
    return ms

def predict(m):
    b = m.get("bookmakers",[{}])[0]
    markets = {x["key"]:x for x in b.get("markets",[])}

    # 2.5
    o25 = markets.get("totals",{}).get("outcomes",[])
    over25 = next((x for x in o25 if "Over" in x["name"] and "2.5" in x["name"]), None)
    under25 = next((x for x in o25 if "Under" in x["name"] and "2.5" in x["name"]), None)

    # 1.5 & 3.5
    over15 = next((x for x in markets.get("totals",{}).get("outcomes",[]) if "Over 1.5" in x["name"]), None)
    over35 = next((x for x in markets.get("totals",{}).get("outcomes",[]) if "Over 3.5" in x["name"]), None)

    # KORNER & KART
    corner = markets.get("player_corners",{}).get("outcomes",[{}])[0] if "player_corners" in markets else {}
    card = markets.get("player_cards",{}).get("outcomes",[{}])[0] if "player_cards" in markets else {}

    bets = [
        ("ÜST 2.5", 1/over25["price"] if over25 else 0, over25["price"] if over25 else 0),
        ("ALT 2.5", 1/under25["price"] if under25 else 0, under25["price"] if under25 else 0),
        ("ÜST 1.5", 1/over15["price"] if over15 else 0, over15["price"] if over15 else 0),
        ("ÜST 3.5", 1/over35["price"] if over35 else 0, over35["price"] if over35 else 0),
        ("KORNER ÜST", 1/corner.get("price",99) if corner else 0, corner.get("price",0)),
        ("KART ÜST", 1/card.get("price",99) if card else 0, card.get("price",0)),
    ]

    valid = [(n,p,r) for n,p,r in bets if p>=0.56 and r>=1.20]
    if not valid: return None
    n,p,r = max(valid, key=lambda x:x[1])
    return {"bet":n, "oran":round(r+random.uniform(-0.03,0.04),2), "prob":int(p*100)}

async def live(ctx):
    global PREDS
    ms = await odds()
    now_live = []
    for m in ms:
        try:
            start = datetime.fromisoformat(m["commence_time"].rstrip("Z")+"+00:00")
            if start <= datetime.now(timezone.utc) <= start + timedelta(minutes=100):
                p = predict(m)
                if p and p["prob"] >= 64:
                    now_live.append({"m":m,"p":p,"t":start})
        except: continue
    if not now_live: return

    top = sorted(now_live, key=lambda x:x["p"]["prob"], reverse=True)[:3]
    lines = BANNER[:]
    for i,x in enumerate(top,1):
        lines += [
            f"{i}. **{x['m']['home_team']} vs {x['m']['away_team']}** ⚽ {EMOJI['live']}",
            f"   `{int((datetime.now(timezone.utc)-x['t']).total_seconds()//60)}'` • `{x['m']['disp']}`",
            f"   {x['p']['bet']} → **{x['p']['oran']}** • `AI: %{x['p']['prob']}`",
            ""
        ]
        PREDS.append({"id":hash(f"{x['m']['home_team']}{m['commence_time']}"),"bet":x['p']['bet'],"oran":x['p']['oran']})
    lines.append(f"{EMOJI['ding']} YENİ CANLI! {EMOJI['cash']} KAZANÇ: `{WINS}W-{LOSSES}L`")
    await ctx.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")

async def results(ctx):
    global WINS, LOSSES
    # ... (önceki sonuç kodu aynı)
    pass

def main():
    app = Application.builder().token(TOKEN).build()
    job = app.job_queue
    job.run_repeating(live, interval=3600, first=5)
    job.run_repeating(results, interval=300, first=20)
    log.info("ATEŞLENDİ – VİP STÜDYO ÇALIŞIYOR")
    app.run_polling()

if __name__ == "__main__":
    main()
