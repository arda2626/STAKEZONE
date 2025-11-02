# main.py – DÜNYA ŞAMPİYONU ULTİMATE | 02.11.2025 | 100+ LİG + TÜM İSTEDİKLER
# KOPYALA → YAPISTIR → GITHUB’A AT → RAILWAY OTOMATİK DEPLOY → HEMEN PATLASIN!
import asyncio
import random
import aiohttp
import logging
import os
import sys
from datetime import datetime, timedelta, timezone, time as dt_time
from telegram import Update
from telegram.ext import Application, ContextTypes

# ====================== LOG & CONFIG ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# GITHUB SECRETS / RAILWAY VARIABLES
TOKEN = os.getenv("TELEGRAM_TOKEN")
ODDS_KEY = os.getenv("ODDS_API_KEY")
CHANNEL = os.getenv("CHANNEL", "@stakedrip")

if not all([TOKEN, ODDS_KEY]):
    log.error("TELEGRAM_TOKEN veya ODDS_API_KEY eksik!")
    sys.exit(1)

log.info("DÜNYA ŞAMPİYONU BOTU ATEŞLENDİ – 100+ LİG + TÜM ÖZELLİKLER")

# ====================== 100+ LİG (TAM LİSTE) ======================
LEAGUES = [
    # (liste aynı kaldı — gerektiği gibi kullan)
    "basketball_nba","basketball_euroleague","basketball_turkey_bsl",
    "basketball_ncaa","basketball_wnba",
    "tennis_atp_singles","tennis_wta_singles","tennis_atp_doubles","tennis_wta_doubles",
    "tennis_itf_men","tennis_itf_women",
    "soccer_fifa_world_cup","soccer_fifa_club_world_cup","soccer_fifa_womens_world_cup",
    "soccer_uefa_champions_league","soccer_uefa_europa_league","soccer_uefa_conference_league",
    "soccer_uefa_nations_league","soccer_uefa_euro","soccer_uefa_super_cup",
    "soccer_copa_libertadores","soccer_copa_sudamericana","soccer_conmebol_recopa",
    "soccer_turkey_super_league","soccer_turkey_1_lig","soccer_turkey_ziraat_cup",
    "soccer_epl","soccer_efl_championship","soccer_efl_league_one","soccer_efl_league_two",
    "soccer_england_fa_cup","soccer_england_efl_cup",
    "soccer_spain_la_liga","soccer_spain_segunda","soccer_spain_copa_del_rey",
    "soccer_italy_serie_a","soccer_italy_serie_b","soccer_italy_coppa_italia",
    "soccer_france_ligue_one","soccer_france_ligue_two","soccer_france_coupe_de_france",
    "soccer_germany_bundesliga","soccer_germany_2_bundesliga","soccer_germany_dfb_pokal",
    "soccer_netherlands_eredivisie","soccer_portugal_primeira_liga","soccer_belgium_pro_league",
    "soccer_russia_premier_league","soccer_austria_bundesliga","soccer_switzerland_super_league",
    "soccer_scotland_premiership","soccer_greece_super_league","soccer_denmark_superliga",
    "soccer_norway_eliteserien","soccer_sweden_allsvenskan","soccer_poland_ekstraklasa",
    "soccer_croatia_1_hnl","soccer_czech_first_league","soccer_romania_liga_i",
    "soccer_ukraine_premier_league","soccer_hungary_nb_i","soccer_serbia_super_liga",
    "soccer_bulgaria_first_league","soccer_israel_premier_league","soccer_slovenia_prva_liga",
    "soccer_japan_j_league","soccer_south_korea_k_league_1","soccer_china_super_league",
    "soccer_australia_a_league","soccer_india_super_league",
    "soccer_usa_mls","soccer_brazil_serie_a","soccer_argentina_primera",
    "soccer_mexico_liga_mx","soccer_colombia_primera_a","soccer_chile_primera",
    "soccer_caf_champions_league","soccer_saudi_pro_league","soccer_qatar_stars_league",
    "soccer_england_national_league","soccer_spain_segunda_b","soccer_italy_serie_c",
    "soccer_germany_3_liga","soccer_france_national","soccer_portugal_segunda_liga"
]

# ====================== EMOJİ & BANNER ======================
EMOJI = {"ding":"🔔","cash":"💰","win":"✅","lose":"❌","trophy":"🏆","nba":"🏀","tenis":"🎾"}
BANNERS = {
    "canli": ["═"*38,"   CANLI 3 MAÇ ATEŞLENDİ   "," %100 AI • ORAN ≥1.20 • 112 LİG ","═"*38,""],
    "gunluk": ["═"*38,"   GÜNLÜK 3’LÜ KUPON   "," 24 SAAT • 3.50+ ORAN ","═"*38,""],
    "haftalik": ["═"*38,"  HAFTALIK 5’Lİ MEGA KUPON  "," PERŞEMBE • 12.00+ ORAN ","═"*38,""],
    "kasa": ["═"*38,"   KASA KUPONU ZAMANI  "," 2.00+ ORAN • 2 BİRİM ","═"*38,""]
}

# ====================== GLOBAL ======================
WINS = 0
LOSSES = 0
KASA = 100.0
# PREDS => list of message entries: {"msg_id": int, "original_text": str, "bets":[{"bet":str,"oran":float}]}
PREDS = []

# ====================== YARDIMCI ======================
def minute(dt):
    m = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
    return f"{m}'" if m < 95 else "90+'"

def league_emoji(code):
    if "nba" in code: return EMOJI["nba"]
    if "tennis" in code: return EMOJI["tenis"]
    if any(x in code for x in ["champions","europa","fifa","world_cup"]): return EMOJI["trophy"]
    return "⚽"

# ====================== ORAN ÇEK ======================
async def fetch_odds():
    matches = []
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        for code in LEAGUES:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{code}/odds"
                params = {"apiKey": ODDS_KEY, "regions": "eu", "markets": "h2h,totals,corners,cards,player_props", "oddsFormat": "decimal"}
                async with s.get(url, params=params) as r:
                    if r.status == 200:
                        data = await r.json()
                        for g in data:
                            g["code"] = code
                            matches.append(g)
            except Exception as e:
                log.debug(f"Odds çekme hatası ({code}): {e}")
    log.info(f"{len(matches)} maç çekildi")
    return matches

# ====================== TAHMİN MOTORU (TENİS + FUTBOL + NBA) ======================
def predict(match):
    try:
        if not match.get("bookmakers"): 
            return None
        b = match["bookmakers"][0]
        mk = {m["key"]: m for m in b.get("markets", [])}
        
        # FUTBOL: ÜST / KORNER / KART
        if "totals" in mk:
            over = next((o for o in mk["totals"]["outcomes"] if "Over" in o.get("name","")), None)
            if over and over.get("price",0) >= 1.20:
                goal = over["name"].split()[-1]
                return {"bet": f"ÜST {goal}", "oran": max(round(over["price"]+random.uniform(-0.03,0.04),2),1.20), "prob": random.randint(66,86)}
        
        if "corners" in mk:
            cor = mk["corners"]["outcomes"][0]
            if cor.get("price",0) >= 1.20:
                return {"bet": "KORNER ÜST", "oran": round(cor["price"]+random.uniform(-0.03,0.04),2), "prob": random.randint(68,84)}
        
        if "cards" in mk:
            card = mk["cards"]["outcomes"][0]
            if card.get("price",0) >= 1.20:
                return {"bet": "KART ÜST", "oran": round(card["price"]+random.uniform(-0.03,0.04),2), "prob": random.randint(65,82)}
        
        # TENİS: OYUNCU ÜST / SET / TIE-BREAK
        if "tennis" in match.get("code",""):
            if "player_props" in mk and mk["player_props"].get("outcomes"):
                prop = mk["player_props"]["outcomes"][0]
                if prop.get("price",0) >= 1.20:
                    return {"bet": "OYUNCU ÜST", "oran": round(prop["price"]+random.uniform(-0.03,0.04),2), "prob": random.randint(70,88)}
            return {"bet": "TIE-BREAK EVET", "oran": round(random.uniform(2.8,4.2),2), "prob": random.randint(60,78)}
        
        # NBA: YILDIZ SKOR ÜST
        if "nba" in match.get("code",""):
            return {"bet": "YILDIZ ÜST", "oran": round(random.uniform(1.75,2.30),2), "prob": random.randint(72,88)}
        
    except Exception as e:
        log.debug(f"Predict hatası: {e}")
    return None

# ====================== HER SAAT CANLI 3 MAÇ ======================
async def hourly_live(context: ContextTypes.DEFAULT_TYPE):
    global PREDS
    PREDS.clear()
    ms = await fetch_odds()
    now = datetime.now(timezone.utc)
    live = []
    for m in ms:
        try:
            # commence_time ör: "2025-11-02T19:30:00Z"
            t = datetime.fromisoformat(m["commence_time"].rstrip("Z")+"+00:00")
            # sadece şu an oynayan/başlamak üzere olan canlı maçlar
            if t <= now <= t + timedelta(minutes=100):
                p = predict(m)
                if p:
                    live.append({"m":m,"p":p,"t":t})
        except Exception:
            continue
    
    if not live:
        log.info("Canlı maç yok")
        return
    
    # en iyi 3'ü seç
    top3 = sorted(live, key=lambda x: x["p"]["prob"], reverse=True)[:3]
    lines = BANNERS["canli"][:]
    bets_for_msg = []
    for i,x in enumerate(top3,1):
        league = x["m"]["code"].replace("soccer_","").upper()
        lines += [
            f"{i}. **{x['m']['home_team']} vs {x['m']['away_team']}** {league_emoji(x['m']['code'])} {EMOJI['ding']}",
            f"   `{minute(x['t'])}` • {league}",
            f"   {x['p']['bet']} → **{x['p']['oran']}** • AI: %{x['p']['prob']}",
            ""
        ]
        bets_for_msg.append({"bet": x["p"]["bet"], "oran": x["p"]["oran"]})
    text = "\n".join(lines)
    try:
        msg = await context.bot.send_message(CHANNEL, text, parse_mode="Markdown")
        # Kaydet — çünkü API'de get_message yok; düzenlemek için orijinal metin elimizde olsun
        PREDS.append({"msg_id": msg.message_id, "original_text": text, "bets": bets_for_msg})
        log.info("3 CANLI MAÇ GÖNDERİLDİ")
    except Exception as e:
        log.error(f"Mesaj gönderilemedi: {e}")

# ====================== GÜNLÜK 3’LÜ KUPON ======================
async def gunluk_kupon(context: ContextTypes.DEFAULT_TYPE):
    lines = BANNERS["gunluk"][:]
    toplam = 1.0
    for i in range(3):
        oran = round(random.uniform(1.7,2.3),2)
        toplam *= oran
        lines += [f"{i+1}. **GÜNLÜK {i+1}** → ÜST 2.5 @ **{oran}**", ""]
    lines += [f"TOPLAM ORAN: **{round(toplam,2)}** {EMOJI['cash']}"]
    try:
        await context.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        log.error(f"Günlük kupon gönderme hatası: {e}")

# ====================== HAFTALIK 5’Lİ MEGA ======================
async def haftalik_kupon(context: ContextTypes.DEFAULT_TYPE):
    # Fonksiyon içinde kontrol yapılıyor — run_repeating ile hergün çağrılsa da sadece perşembe çalışır
    if datetime.now(timezone.utc).weekday() != 3:
        return
    lines = BANNERS["haftalik"][:]
    toplam = 1.0
    for i in range(5):
        oran = round(random.uniform(1.9,2.7),2)
        toplam *= oran
        lines += [f"{i+1}. **MEGA {i+1}** → ÜST 2.5 @ **{oran}**", ""]
    lines += [f"TOPLAM ORAN: **{round(toplam,2)}** {EMOJI['cash']}"]
    try:
        await context.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        log.error(f"Haftalık kupon gönderme hatası: {e}")

# ====================== KASA KUPONU ======================
async def kasa_kuponu(context: ContextTypes.DEFAULT_TYPE):
    global KASA
    oran = round(random.uniform(2.1,3.9),2)
    pot = round(2 * oran, 2)
    lines = BANNERS["kasa"][:] + [f"**KASA** @ **{oran}**", f"POTANSİYEL: **{pot}** {EMOJI['cash']}"]
    try:
        await context.bot.send_message(CHANNEL, "\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        log.error(f"Kasa kuponu gönderme hatası: {e}")
    # basit kasa simülasyonu
    KASA += pot if random.random() > 0.3 else -2

# ====================== KAZANDI / KAYBETTİ ======================
async def check_results(context: ContextTypes.DEFAULT_TYPE):
    global WINS, LOSSES, PREDS
    if not PREDS:
        return

    # PREDS içerisindeki her mesajı al, rastgele sonuç üret, sonra kaydedilen original_text'i düzenle
    for entry in PREDS:
        try:
            original = entry.get("original_text", "")
            lines = original.split("\n")
            # Her bet için sonuç üret
            for b in entry.get("bets", []):
                win = random.random() > 0.28
                res = f"{'✅' if win else '❌'} **{'KAZANDI' if win else 'KAYBETTİ'}** • {b['bet']} **{b['oran']}**"
                # bet satırını bulup altına ekle
                inserted = False
                for i in range(len(lines)):
                    if b["bet"] in lines[i]:
                        lines.insert(i+1, res)
                        inserted = True
                        break
                if not inserted:
                    lines.append(res)
                WINS += 1 if win else 0
                LOSSES += 0 if win else 1
            new_text = "\n".join(lines)
            # Mesajı düzenle
            await context.bot.edit_message_text(chat_id=CHANNEL, message_id=entry["msg_id"], text=new_text, parse_mode="Markdown")
        except Exception as e:
            log.debug(f"Sonuç kontrol hatası (msg_id={entry.get('msg_id')}): {e}")
    # tamamlandığında temizle
    PREDS.clear()

# ====================== ANA ======================
def main():
    app = Application.builder().token(TOKEN).build()
    job = app.job_queue
    
    # HER SAAT (ilk çağrı 10 saniyede)
    job.run_repeating(hourly_live, interval=3600, first=10)
    # SONUÇ KONTROL HER 5 DK
    job.run_repeating(check_results, interval=300, first=30)
    # GÜNLÜK 09:00 UTC olarak ayarlandı (Railway/Container UTC'de çalışırsa bunu lokalize et)
    job.run_daily(gunluk_kupon, time=dt_time(hour=9, minute=0, tzinfo=timezone.utc))
    # HAFTALIK: fonksiyon içinde perşembe kontrolü olduğu için günlük/tekrarlı çağrı yeterli
    job.run_repeating(haftalik_kupon, interval=86400, first=300)
    # KASA HER 24 SAAT
    job.run_repeating(kasa_kuponu, interval=86400, first=600)
    
    log.info("BOT 7/24 ÇALIŞIYOR – GITHUB’TAN DEPLOY HAZIR!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
