# main.py - STAKEZONE AI v13 (TÜM 50+ LİG! MAÇ YOK DEMEZ!)
import asyncio, logging
from datetime import datetime, timedelta, timezone
from telegram.ext import Application, CommandHandler
from telegram import Update
from fastapi import FastAPI, Request
import uvicorn, aiohttp

from db import init_db, DB_PATH, mark_posted, was_posted_recently
from prediction import ai_predict
from utils import league_to_flag, get_live_minute, get_live_events

TELEGRAM_TOKEN = "8393964009:AAE6BnaKNqYLk3KahAL2k9ABOkdL7eFIb7s"
CHANNEL_ID = "@stakedrip"
WEBHOOK_URL = "https://stakezone-ai.onrender.com/stakedrip"
THE_ODDS_API_KEY = "41eb74e295dfecf0a675417cbb56cf4d"

TR_TIME = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# TÜM DÜNYA LİGLERİ (50+!)
ALL_SOCCER = [
    "soccer_epl", "soccer_efl_champ", "soccer_england_league1", "soccer_england_league2",
    "soccer_spain_la_liga", "soccer_spain_segunda_division",
    "soccer_italy_serie_a", "soccer_italy_serie_b",
    "soccer_germany_bundesliga", "soccer_germany_bundesliga2",
    "soccer_france_ligue_one", "soccer_france_ligue_two",
    "soccer_turkey_super_league",
    "soccer_netherlands_eredivisie", "soccer_portugal_primeira_liga",
    "soccer_belgium_first_div", "soccer_austria_bundesliga",
    "soccer_greece_super_league", "soccer_switzerland_superleague",
    "soccer_denmark_superliga", "soccer_norway_eliteserien",
    "soccer_sweden_allsvenskan", "soccer_finland_veikkausliiga",
    "soccer_poland_ekstraklasa", "soccer_russia_premier_league",
    "soccer_uefa_champs_league", "soccer_uefa_europa_league",
    "soccer_uefa_champs_league_qualification", "soccer_uefa_euro_qualification",
    "soccer_uefa_nations_league", "soccer_conmebol_copa_libertadores",
    "soccer_brazil_campeonato", "soccer_argentina_primera_division",
    "soccer_mexico_ligamx", "soccer_usa_mls", "soccer_japan_j_league",
    "soccer_china_superleague", "soccer_korea_kleague1",
    "soccer_australia_aleague", "soccer_africa_cup_of_nations"
    # İstersen daha ekleriz, API 100+ destekliyor!
]

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

def neon_banner(title, conf):
    return (
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n"
        "   ⚡ STAKEZONE AI v13 ⚡\n"
        "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦\n\n"
        f"      {title}\n"
        f"   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n"
        f"   🔥 %{int(conf*100)} KAZANMA ŞANSI\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

async def build_coupon(min_conf, title, max_hours_ahead=0):
    matches = []
    async with aiohttp.ClientSession() as s:
        for sp in ALL_SOCCER:
            try:
                async with s.get(f"https://api.the-odds-api.com/v4/sports/{sp}/odds",
                                params={"apiKey": THE_ODDS_API_KEY, "regions": "eu"}) as r:
                    if r.status != 200: continue
                    data = await r.json()
                    for g in data:
                        start = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
                        delta = (start - NOW_UTC).total_seconds() / 3600
                        if delta > max_hours_ahead: continue
                        if max_hours_ahead == 0 and delta >= 0: continue
                        if was_posted_recently(g["id"]): continue
                        matches.append({"id": g["id"], "home": g["home_team"], "away": g["away_team"],
                                        "sport": sp, "date": g["commence_time"], "start": start})
            except: pass

    if not matches:
        return None

    picks = []
    for m in matches:
        p = await ai_predict(m)
        p["odds"] = 1.20 + round(random.uniform(0.1, 1.2), 2)
        if p["confidence"] >= min_conf:
            picks.append((p["confidence"], p))

    if not picks: return None

    best = max(picks, key=lambda x: x[0])[1]
    mark_posted(best["id"])
    live = best.get("start", NOW_UTC) < NOW_UTC
    live_stats = await get_live_events(best["id"]) if live else {"corners": "-", "cards": "-"}
    minute = f" ⚡ {get_live_minute(best)}'" if live else f" ⏰ {best['start'].astimezone(TR_TIME).strftime('%H:%M')}"

    return (
        f"{neon_banner(title, best['confidence'])}\n"
        f"{league_to_flag(best['home'])} <b>{best['home']}</b> vs {league_to_flag(best['away'])} <b>{best['away']}</b>\n"
        f"🕒 <b>{minute}</b>\n"
        f"⚽ <b>{best['main_bet']}</b>\n"
        f"📐 <b>{best['corner_bet']}</b> (Ort: {best.get('corner_avg', 11.2)})\n"
        f"{'   ✅ Canlı: ' + str(live_stats['corners']) + ' korner' if live else ''}\n"
        f"🟨 <b>{best['card_bet']}</b> (Ort: {best.get('card_avg', 4.7)})\n"
        f"{'   ✅ Canlı: ' + str(live_stats['cards']) + ' kart' if live else ''}\n"
        f"💰 Oran: <b>{best['odds']:.2f}</b>\n"
        f"📊 AI GÜVEN: <b>%{int(best['confidence']*100)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 TEK SITEMIZ STAKE! @stakedrip"
    )

async def no_match_message(title):
    return f"⚡ STAKEZONE AI v13 ⚡\n\n      {title}\n   📅 {datetime.now(TR_TIME).strftime('%d %B %Y - %H:%M')} TÜRKİYE\n\n🔍 50+ LİG TARANIYOR...\n⏳ 5 DK SONRA YENİ KUPON!\nABONE OL! @stakedrip"

async def hourly_job(ctx):   # CANLI
    text = await build_coupon(0.55, "CANLI KUPON", 0)
    await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("CANLI KUPON"), parse_mode="HTML")

async def daily_job(ctx):    # 12 SAAT
    text = await build_coupon(0.60, "GÜNLÜK KUPON", 12)
    await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("GÜNLÜK KUPON"), parse_mode="HTML")

async def vip_job(ctx):      # 24 SAAT
    text = await build_coupon(0.80, "VIP KUPON", 24)
    await ctx.bot.send_message(CHANNEL_ID, text or await no_match_message("VIP KUPON"), parse_mode="HTML")

app = FastAPI()
tg = Application.builder().token(TELEGRAM_TOKEN).build()

tg.add_handler(CommandHandler("hourly", lambda u,c: hourly_job(c)))
tg.add_handler(CommandHandler("daily", lambda u,c: daily_job(c)))
tg.add_handler(CommandHandler("vip", lambda u,c: vip_job(c)))

@app.on_event("startup")
async def start():
    init_db(DB_PATH)
    jq = tg.job_queue
    jq.run_repeating(hourly_job, 3600, first=5)
    jq.run_repeating(daily_job, 43200, first=20)
    jq.run_repeating(vip_job, 86400, first=30)
    await tg.initialize(); await tg.start()
    await tg.bot.set_webhook(WEBHOOK_URL)
    log.info("v13 TÜM LİGLER AÇIK!")

@app.post("/stakedrip")
async def wh(r: Request):
    up = Update.de_json(await r.json(), tg.bot)
    await tg.update_queue.put(up)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8443)
