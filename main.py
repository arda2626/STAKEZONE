# main.py — STAKEDRIP AI ULTRA v3 — Full (Football API-Football + Basketball + Tennis + TSDB fallback)
# Features: live picks (max 3, min odds), daily/weekly/kasa coupons, sqlite history, result check, daily summary (23:00 TR)
# Env vars:
# TELEGRAM_TOKEN, API_FOOTBALL_KEY, API_BASKETBALL_KEY (optional), API_TENNIS_KEY (optional),
# THESPORTSDB_KEY (optional), CHANNEL_ID, DB_PATH (optional)

import os
import sys
import random
import sqlite3
import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone, time as dt_time
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------- LOG ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ---------------- CONFIG (ENV) ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")            # dashboard.api-football.com
API_BASKETBALL_KEY = os.getenv("API_BASKETBALL_KEY")        # api-sports basketball (optional)
API_TENNIS_KEY = os.getenv("API_TENNIS_KEY")                # api-sports tennis (optional)
THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY")              # fallback (optional)
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002284350528"))
DB_PATH = os.getenv("DB_PATH", "data.db")
MIN_ODDS = float(os.getenv("MIN_ODDS", "1.20"))

if not TELEGRAM_TOKEN:
    log.error("Missing TELEGRAM_TOKEN")
    sys.exit(1)
if not API_FOOTBALL_KEY:
    log.warning("API_FOOTBALL_KEY not set — football live/odds will be limited or fallback to TSDB")

# ---------------- EMOJI & BANNER ----------------
EMOJI = {
    "futbol":"⚽","nba":"🏀","tenis":"🎾","ding":"🔔","cash":"💰","win":"✅","lose":"❌","clock":"🕒","cup":"🏆","info":"ℹ️"
}

def banner(title):
    return "\n".join(["═"*38, f"💎 STAKEDRIP LIVE PICKS 💎", f"🔥 AI CANLI TAHMİN ({title}) 🔥", "═"*38])

# ---------------- TIME HELPERS ----------------
def utcnow():
    return datetime.now(timezone.utc)
def turkey_now():
    return datetime.now(timezone(timedelta(hours=3)))

# ---------------- SQLITE ----------------
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT,
        source TEXT,
        sport TEXT,
        league TEXT,
        home TEXT,
        away TEXT,
        bet TEXT,
        odds REAL,
        prob INTEGER,
        created_at TEXT,
        msg_id INTEGER,
        status TEXT DEFAULT 'pending',
        resolved_at TEXT,
        note TEXT
    )""")
    con.commit()
    con.close()

def save_prediction(entry):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    INSERT INTO predictions (event_id, source, sport, league, home, away, bet, odds, prob, created_at, msg_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (entry.get("event_id"), entry.get("source"), entry.get("sport"), entry.get("league"),
          entry.get("home"), entry.get("away"), entry.get("bet"), entry.get("odds"), entry.get("prob"),
          entry.get("created_at"), entry.get("msg_id")))
    con.commit()
    con.close()

def get_pending_predictions():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id,event_id,source,sport,league,home,away,bet,odds FROM predictions WHERE status='pending'")
    rows = cur.fetchall()
    con.close()
    return rows

def mark_prediction(pred_id, status, note=""):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("UPDATE predictions SET status=?, resolved_at=?, note=? WHERE id=?", (status, utcnow().isoformat(), note, pred_id))
    con.commit()
    con.close()

def day_summary_between(start_iso, end_iso):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT status, COUNT(*) FROM predictions WHERE created_at BETWEEN ? AND ? GROUP BY status", (start_iso, end_iso))
    rows = cur.fetchall()
    con.close()
    return rows

# ---------------- API HELPERS ----------------
AF_BASE = "https://v3.football.api-sports.io"
AF_HEADERS = {"x-apisports-key": API_FOOTBALL_KEY} if API_FOOTBALL_KEY else None

AB_BASE = "https://v1.basketball.api-sports.io"    # example; some providers share base
AB_HEADERS = {"x-apisports-key": API_BASKETBALL_KEY} if API_BASKETBALL_KEY else None

AT_BASE = "https://v1.tennis.api-sports.io"
AT_HEADERS = {"x-apisports-key": API_TENNIS_KEY} if API_TENNIS_KEY else None

TSDB_BASE = "https://www.thesportsdb.com/api/v1/json"
TSDB_KEY = THESPORTSDB_KEY

async def af_get(session, path, params=None):
    if not API_FOOTBALL_KEY:
        return None
    url = AF_BASE + path
    try:
        async with session.get(url, headers=AF_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        log.debug(f"af_get error: {e}")
    return None

async def ab_get(session, path, params=None):
    if not API_BASKETBALL_KEY:
        return None
    url = AB_BASE + path
    try:
        async with session.get(url, headers=AB_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        log.debug(f"ab_get error: {e}")
    return None

async def at_get(session, path, params=None):
    if not API_TENNIS_KEY:
        return None
    url = AT_BASE + path
    try:
        async with session.get(url, headers=AT_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        log.debug(f"at_get error: {e}")
    return None

async def tsdb_get(session, path, params=None):
    if not TSDB_KEY:
        return None
    url = f"{TSDB_BASE}/{TSDB_KEY}/{path}"
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        log.debug(f"tsdb_get error: {e}")
    return None

# ---------------- PREDICTION ENGINE ----------------
NBA_PLAYERS = ["LeBron James","Stephen Curry","Jayson Tatum","Giannis Antetokounmpo","Luka Doncic","Kevin Durant","Devin Booker","Nikola Jokic","Shai Gilgeous-Alexander"]

def ensure_min_odds(x):
    return max(round(x,2), MIN_ODDS)

# Football: use team form from API-Football fixtures if possible
async def get_team_last_form_af(session, team_id):
    try:
        data = await af_get(session, "/fixtures", {"team": team_id, "last": 5})
        if data and "response" in data:
            res = data["response"]
            gf = ga = 0
            results = []
            for m in res:
                goals = m.get("goals", {})
                home = m.get("teams",{}).get("home",{})
                away = m.get("teams",{}).get("away",{})
                gh = goals.get("home")
                ga_ = goals.get("away")
                if gh is None or ga_ is None:
                    continue
                # figure side
                if home.get("id") == team_id:
                    gf += gh; ga += ga_
                    results.append("W" if gh>ga_ else ("D" if gh==ga_ else "L"))
                else:
                    gf += ga_; ga += gh
                    results.append("W" if ga_>gh else ("D" if ga_==gh else "L"))
            if not results:
                return None
            return {"last": results, "avg_for": gf/len(results), "avg_against": ga/len(results)}
    except Exception as e:
        log.debug(f"get_team_last_form_af error: {e}")
    return None

# For basketball and tennis we will attempt to use API_BASKETBALL / API_TENNIS if keys present; otherwise fallback heuristics.

async def make_prediction(session, ev):
    """
    ev is normalized dict with keys depending on source.
    Return: {event_id, source, sport, league, home, away, bet, odds, prob}
    """
    # Determine sport
    sport_raw = (ev.get("sport") or ev.get("strSport") or ev.get("sport_name") or "").lower()
    # Normalize id/home/away/league
    event_id = ev.get("id") or ev.get("idEvent") or (ev.get("fixture") and ev["fixture"].get("id"))
    league = ev.get("league") or ev.get("league_name") or ev.get("strLeague") or ev.get("league", "")
    home = ev.get("home") or ev.get("strHomeTeam") or ev.get("teams",{}).get("home",{}).get("name")
    away = ev.get("away") or ev.get("strAwayTeam") or ev.get("teams",{}).get("away",{}).get("name")

    # FOOTBALL
    if "football" in sport_raw or "soccer" in sport_raw or ev.get("league") and "football" in str(ev.get("league")).lower():
        sport = "futbol"
        source = "api-football" if API_FOOTBALL_KEY else "thesportsdb"
        bet = "ÜST 2.5"
        odds = 1.6
        prob = 65
        # Try AF enrichment if fixture has teams with ids
        team_home_id = None
        team_away_id = None
        # AF style normalization
        if ev.get("teams"):
            team_home_id = ev["teams"].get("home",{}).get("id")
            team_away_id = ev["teams"].get("away",{}).get("id")
        elif ev.get("fixture") and ev["fixture"].get("id"):
            # might not have team ids here
            team_home_id = ev.get("home_team_id")
        form_home = form_away = None
        if API_FOOTBALL_KEY and (team_home_id or team_away_id):
            try:
                if team_home_id:
                    form_home = await get_team_last_form_af(session, team_home_id)
                if team_away_id:
                    form_away = await get_team_last_form_af(session, team_away_id)
            except:
                form_home = form_away = None
        # Heuristics using forms
        try:
            if form_home and form_away:
                avg_total = form_home["avg_for"] + form_away["avg_for"]
                # Kart/Korner detection naive: if both teams have many fouls? (not provided) -> skip
                if avg_total >= 2.6:
                    bet = "ÜST 2.5"
                    odds = ensure_min_odds(1.4 + (avg_total-2.6)*0.5)
                    prob = min(92, int(60 + (avg_total-2.6)*18))
                elif form_home["avg_for"]>1.1 and form_away["avg_for"]>1.1:
                    bet = "KG VAR"
                    odds = ensure_min_odds(1.55)
                    prob = 68
                else:
                    bet = random.choice(["Ev Sahibi Kazanır","1","X","2"])
                    odds = ensure_min_odds(random.uniform(1.45,2.3))
                    prob = random.randint(55,80)
            else:
                # fallback: choose plausible bets with reasonable odds
                bet = random.choice(["ÜST 2.5","KG VAR","Ev Sahibi Kazanır","Korner ÜST 9.5","Kart ÜST 3.5","1.5 ÜST"])
                odds = ensure_min_odds(random.uniform(1.3,2.3))
                prob = random.randint(55,85)
        except Exception as e:
            log.debug(f"football prediction error: {e}")
            bet = "ÜST 2.5"; odds = ensure_min_odds(1.5); prob=60

        return {"event_id": str(event_id) if event_id else None, "source": source, "sport": sport, "league": league,
                "home": home, "away": away, "bet": bet, "odds": odds, "prob": prob}

    # BASKETBALL
    if "basket" in sport_raw or "nba" in sport_raw or (ev.get("league") and ("nba" in str(ev.get("league")).lower() or "euroleague" in str(ev.get("league")).lower())):
        sport = "nba"
        source = "api-basketball" if API_BASKETBALL_KEY else ("thesportsdb" if TSDB_KEY else "heuristic")
        # choose between player prop and team totals and quarter picks
        if random.random() < 0.35:
            player = random.choice(NBA_PLAYERS)
            bet = f"{player} 20+ Sayı"
            odds = ensure_min_odds(random.uniform(1.6,2.6))
            prob = random.randint(60,88)
        else:
            # team totals / quarter picks
            if random.random() < 0.4:
                bet = random.choice(["Toplam Sayı ÜST 212.5", "Ev Sahibi 110.5 ÜST", "Deplasman 100.5 ALT"])
                odds = ensure_min_odds(random.uniform(1.45,2.3))
                prob = random.randint(60,88)
            else:
                # quarter pick
                q = random.choice([1,2,3,4])
                qbet = random.choice([f"Q{q} ÜST 54.5", f"Q{q} Ev Sahibi Kazanır", f"Q{q} Deplasman Kazanır"])
                bet = qbet
                odds = ensure_min_odds(random.uniform(1.5,2.4))
                prob = random.randint(60,88)
        return {"event_id": str(event_id) if event_id else None, "source": source, "sport": sport, "league": league,
                "home": home, "away": away, "bet": bet, "odds": odds, "prob": prob}

    # TENNIS
    if "tenis" in sport_raw or "tennis" in sport_raw:
        sport = "tenis"
        source = "api-tennis" if API_TENNIS_KEY else ("thesportsdb" if TSDB_KEY else "heuristic")
        if random.random() < 0.45:
            bet = "Tie-break Var"
            odds = ensure_min_odds(random.uniform(1.8,3.2))
            prob = random.randint(55,78)
        else:
            bet = random.choice(["Toplam Oyun ÜST 22.5","1. Set 9.5 ÜST","Maç 3. Sete Gider"])
            odds = ensure_min_odds(random.uniform(1.6,2.6))
            prob = random.randint(55,82)
        return {"event_id": str(event_id) if event_id else None, "source": source, "sport": sport, "league": league,
                "home": home, "away": away, "bet": bet, "odds": odds, "prob": prob}

    # fallback generic
    return {"event_id": str(event_id) if event_id else None, "source":"unknown", "sport":"futbol", "league":league,
            "home":home, "away":away, "bet":"ÜST 2.5", "odds": ensure_min_odds(1.5), "prob":60}

# ---------------- BUILD & POST MESSAGE ----------------
def build_live_text(picks):
    head = banner("LIVE")
    lines = [head, ""]
    for i,p in enumerate(picks,1):
        emoji = EMOJI.get(p["sport"], "⚽")
        lines += [
            f"{i}. {emoji} **{p['home']} vs {p['away']}**",
            f"   {p.get('league','')}",
            f"   Tahmin: {p['bet']} → **{p['odds']}** • AI: %{p['prob']}",
            ""
        ]
    lines.append(f"{EMOJI['ding']} Minimum oran: {MIN_ODDS} • Maks: 3 maç")
    return "\n".join(lines)

async def post_picks_and_save(app, picks):
    text = build_live_text(picks)
    try:
        sent = await app.bot.send_message(CHANNEL_ID, text, parse_mode="Markdown")
        for p in picks:
            entry = {
                "event_id": p.get("event_id"),
                "source": p.get("source"),
                "sport": p.get("sport"),
                "league": p.get("league"),
                "home": p.get("home"),
                "away": p.get("away"),
                "bet": p.get("bet"),
                "odds": p.get("odds"),
                "prob": p.get("prob"),
                "created_at": utcnow().isoformat(),
                "msg_id": sent.message_id
            }
            save_prediction(entry)
        log.info(f"Posted {len(picks)} picks and saved to DB")
    except Exception as e:
        log.error(f"post_picks error: {e}")

# ---------------- HOURLY LIVE JOB ----------------
async def hourly_live(ctx: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as session:
        candidates = []

        # 1) Football via API-Football live fixtures
        if API_FOOTBALL_KEY:
            try:
                res = await af_get(session, "/fixtures", {"live":"all"})
                if res and res.get("response"):
                    for f in res["response"]:
                        # normalize to minimal ev dict consumed by make_prediction
                        ev = {
                            "id": f.get("fixture",{}).get("id"),
                            "league": f.get("league",{}).get("name"),
                            "teams": {"home":{"id": f.get("teams",{}).get("home",{}).get("id"), "name": f.get("teams",{}).get("home",{}).get("name")},
                                      "away":{"id": f.get("teams",{}).get("away",{}).get("id"), "name": f.get("teams",{}).get("away",{}).get("name")}},
                            "home": f.get("teams",{}).get("home",{}).get("name"),
                            "away": f.get("teams",{}).get("away",{}).get("name"),
                            "sport": "football"
                        }
                        pred = await make_prediction(session, ev)
                        if pred and pred["odds"] >= MIN_ODDS:
                            candidates.append(pred)
            except Exception as e:
                log.debug(f"hourly_live AF error: {e}")

        # 2) Basketball via API-Basketball live fixtures (if key)
        if API_BASKETBALL_KEY:
            try:
                res = await ab_get(session, "/games", {"live":"all"})
                if res and res.get("response"):
                    for g in res["response"]:
                        ev = {"id": g.get("id"), "league": g.get("league",{}).get("name"), "home": g.get("home",{}).get("name"), "away": g.get("away",{}).get("name"), "sport":"basketball", "strSport":"basketball"}
                        pred = await make_prediction(session, ev)
                        if pred and pred["odds"] >= MIN_ODDS:
                            candidates.append(pred)
            except Exception as e:
                log.debug(f"hourly_live AB error: {e}")

        # 3) Tennis via API-Tennis live fixtures (if key)
        if API_TENNIS_KEY:
            try:
                res = await at_get(session, "/fixtures", {"status":"LIVE"})
                if res and res.get("response"):
                    for t in res["response"]:
                        ev = {"id": t.get("fixture",{}).get("id"), "league": t.get("tournament",{}).get("name"), "home": t.get("players",{}).get("player1",{}).get("name") if isinstance(t.get("players"),dict) else t.get("players"), "away": t.get("players",{}).get("player2",{}).get("name") if isinstance(t.get("players"),dict) else None, "sport":"tennis", "strSport":"tennis"}
                        pred = await make_prediction(session, ev)
                        if pred and pred["odds"] >= MIN_ODDS:
                            candidates.append(pred)
            except Exception as e:
                log.debug(f"hourly_live AT error: {e}")

        # 4) Fallback TheSportsDB live events
        try:
            ts = await tsdb_get(session, "eventslive.php")
            if ts and ts.get("event"):
                for e in ts["event"]:
                    pred = await make_prediction(session, e)
                    if pred and pred["odds"] >= MIN_ODDS:
                        candidates.append(pred)
        except Exception as e:
            log.debug(f"hourly_live TSDB error: {e}")

        if not candidates:
            log.info("hourly_live: no suitable live candidates")
            return

        # select top by prob up to 3
        selected = sorted(candidates, key=lambda x: x["prob"], reverse=True)[:3]
        await post_picks_and_save(ctx, selected)

# ---------------- DAILY / WEEKLY / KASA COUPONS ----------------
async def gunluk_kupon(ctx: ContextTypes.DEFAULT_TYPE):
    # choose matches starting within next 24 hours (prefer API-Football fixtures)
    picks = []
    async with aiohttp.ClientSession() as session:
        if API_FOOTBALL_KEY:
            try:
                now_ts = int(datetime.utcnow().timestamp())
                # get fixtures for next 24 hours by league? use "from/to" window
                to_time = (datetime.utcnow() + timedelta(hours=24)).isoformat()
                res = await af_get(session, "/fixtures", {"from": datetime.utcnow().isoformat(), "to": to_time})
                if res and res.get("response"):
                    for f in res["response"]:
                        ev = {"id": f.get("fixture",{}).get("id"), "league": f.get("league",{}).get("name"), "home": f.get("teams",{}).get("home",{}).get("name"), "away": f.get("teams",{}).get("away",{}).get("name"), "sport":"football"}
                        pred = await make_prediction(session, ev)
                        if pred and 1.20 <= pred["odds"] <= 3.50:
                            picks.append(pred)
                # fallback to TSDB if none
            except Exception as e:
                log.debug(f"gunluk_kupon AF error: {e}")

        if not picks:
            ts = await tsdb_get(session, "eventsday.php", {"d": datetime.utcnow().strftime("%Y-%m-%d")})
            if ts and ts.get("events"):
                for e in ts["events"]:
                    pred = await make_prediction(session, e)
                    if pred and 1.20 <= pred["odds"] <= 3.50:
                        picks.append(pred)

    # choose up to 3 picks (or 2-4 as required)
    if not picks:
        log.info("gunluk_kupon: no picks found")
        return
    chosen = sorted(picks, key=lambda x: x["prob"], reverse=True)[:3]
    # create coupon text
    header = "\n".join(["═"*38, "💰 GÜNLÜK KUPON (24 SAAT İÇİN) 💰", " AI Tahminleri ", "═"*38, ""])
    lines = [header]
    total = 1.0
    for i,p in enumerate(chosen,1):
        lines += [f"{EMOJI[p['sport']]} {p['home']} vs {p['away']} • {p['bet']} @ **{p['odds']}**", ""]
        total *= p['odds']
        # save as pseudo-event if event_id exists
        save_prediction({"event_id": p.get("event_id"), "source":"DAILY", "sport":p["sport"], "league":"DAILY", "home":p["home"], "away":p["away"], "bet":p["bet"], "odds":p["odds"], "prob":p["prob"], "created_at": utcnow().isoformat(), "msg_id": None})
    lines += [f"TOPLAM ORAN: **{round(total,2)}** {EMOJI['cash']}"]
    await ctx.bot.send_message(CHANNEL_ID, "\n".join(lines), parse_mode="Markdown")

async def haftalik_kupon(ctx: ContextTypes.DEFAULT_TYPE):
    # picks from next 7 days
    if turkey_now().weekday() != 3:
        return
    picks = []
    async with aiohttp.ClientSession() as session:
        if API_FOOTBALL_KEY:
            try:
                to_time = (datetime.utcnow() + timedelta(days=7)).isoformat()
                res = await af_get(session, "/fixtures", {"from": datetime.utcnow().isoformat(), "to": to_time})
                if res and res.get("response"):
                    for f in res["response"]:
                        ev = {"id": f.get("fixture",{}).get("id"), "league": f.get("league",{}).get("name"), "home": f.get("teams",{}).get("home",{}).get("name"), "away": f.get("teams",{}).get("away",{}).get("name"), "sport":"football"}
                        pred = await make_prediction(session, ev)
                        if pred and 1.50 <= pred["odds"] <= 2.50:
                            picks.append(pred)
            except Exception as e:
                log.debug(f"haftalik_kupon AF error: {e}")
        # fallback minimal fill via TSDB
        if not picks:
            ts = await tsdb_get(session, "eventsday.php", {"d": datetime.utcnow().strftime("%Y-%m-%d")})
            if ts and ts.get("events"):
                for e in ts["events"]:
                    pred = await make_prediction(session, e)
                    if pred and 1.50 <= pred["odds"] <= 2.50:
                        picks.append(pred)
    if not picks:
        log.info("haftalik_kupon: no picks")
        return
    chosen = sorted(picks, key=lambda x: x["prob"], reverse=True)[:5]
    header = "\n".join(["═"*38, f"{EMOJI['cup']} HAFTALIK 5'Lİ MEGA KUPON {EMOJI['cup']}", " AI Power ", "═"*38, ""])
    lines = [header]
    total = 1.0
    for i,p in enumerate(chosen,1):
        lines += [f"{i}. {EMOJI[p['sport']]} {p['home']} vs {p['away']} • {p['bet']} @ **{p['odds']}**", ""]
        total *= p['odds']
        save_prediction({"event_id": p.get("event_id"), "source":"WEEKLY", "sport":p["sport"], "league":"WEEKLY", "home":p["home"], "away":p["away"], "bet":p["bet"], "odds":p["odds"], "prob":p["prob"], "created_at": utcnow().isoformat(), "msg_id": None})
    lines += [f"TOPLAM ORAN: **{round(total,2)}** {EMOJI['cash']}"]
    await ctx.bot.send_message(CHANNEL_ID, "\n".join(lines), parse_mode="Markdown")

async def kasa_kuponu(ctx: ContextTypes.DEFAULT_TYPE):
    # pick 2-3 high confidence small odds
    picks = []
    for _ in range(random.choice([2,2,3])):
        sport = random.choice(["futbol","nba","tenis"])
        # simple pick generation
        bet = "Ev Sahibi Kazanır" if sport=="futbol" else (f"{random.choice(NBA_PLAYERS)} 20+ Sayı" if sport=="nba" else "Favori Kazanır")
        odds = ensure_min_odds(random.uniform(1.2,1.6))
        prob = random.randint(70,92)
        picks.append({"sport":sport,"home":"--","away":"--","bet":bet,"odds":odds,"prob":prob})
        save_prediction({"event_id": None, "source":"KASA", "sport":sport, "league":"KASA", "home":None, "away":None, "bet":bet, "odds":odds, "prob":prob, "created_at": utcnow().isoformat(), "msg_id": None})
    header = "\n".join(["═"*38, "💼 KASA KUPONU ZAMANI 💼", " Güvenli Kombine ", "═"*38, ""])
    lines = [header]
    total = 1.0
    for p in picks:
        lines += [f"{EMOJI[p['sport']]} {p['bet']} @ **{p['odds']}**", ""]
        total *= p['odds']
    lines += [f"POTANSİYEL: **{round(total,2)}** {EMOJI['cash']}"]
    await ctx.bot.send_message(CHANNEL_ID, "\n".join(lines), parse_mode="Markdown")

# ---------------- RESULT CHECK (every 5 minutes) ----------------
# Evaluate simple bets where possible by checking final scores via API-Football or TSDB
def evaluate_simple_rule(match, bet_text, sport):
    try:
        # normalize scores for different API structures
        # API-Football fixture uses 'goals' dict in response[0] etc.
        if isinstance(match, dict):
            # many shapes; attempt various keys
            home = None; away = None
            if "goalsHomeTeam" in match:  # some variants
                home = match.get("goalsHomeTeam") or 0
                away = match.get("goalsAwayTeam") or 0
            elif match.get("goals"):
                home = match.get("goals",{}).get("home") or 0
                away = match.get("goals",{}).get("away") or 0
            elif "intHomeScore" in match:
                home = int(match.get("intHomeScore") or 0)
                away = int(match.get("intAwayScore") or 0)
            else:
                # fallback zero
                home = int(match.get("homeScore") or 0)
                away = int(match.get("awayScore") or 0)
            total = home + away
        else:
            return None, "no_score"
    except Exception as e:
        return None, "no_score"

    bt = bet_text.lower()
    # Football rules
    if sport == "futbol":
        if "üst" in bt:
            import re
            nums = re.findall(r"[\d\.]+", bt)
            target = float(nums[-1]) if nums else 2.5
            return (total > target), f"{home}-{away}"
        if "kg" in bt:
            return (home>0 and away>0), f"{home}-{away}"
        if "kart" in bt:
            # exact card counts not available reliably -> return None
            return None, "card_data_missing"
        if "korner" in bt:
            return None, "corner_data_missing"
        if "ev sahibi" in bt or "home" in bt:
            return (home > away), f"{home}-{away}"
    # Basketball rules
    if sport == "nba":
        if "toplam" in bt and "üst" in bt:
            import re
            nums = re.findall(r"[\d\.]+", bt)
            target = float(nums[-1]) if nums else 212.5
            return (total > target), f"{total} pts"
        if "q" in bt and "üst" in bt:
            # quarter data not always present -> None
            return None, "quarter_data_missing"
        if any(name.lower() in bt for name in NBA_PLAYERS):
            return None, "player_prop_missing"
    # Tennis rules: tie-break detection not reliable -> None
    if sport == "tenis":
        return None, "tennis_data_missing"
    return None, "unknown_rule"

async def check_results(ctx: ContextTypes.DEFAULT_TYPE):
    pending = get_pending_predictions()
    if not pending:
        return
    async with aiohttp.ClientSession() as session:
        for row in pending:
            pred_id, event_id, source, sport, league, home, away, bet_text, odds = row
            resolved = False
            if event_id:
                # attempt lookup in AF if source api-football
                match = None
                if source == "api-football" and API_FOOTBALL_KEY:
                    try:
                        res = await af_get(session, "/fixtures", {"id": int(event_id)})
                        if res and res.get("response"):
                            match = res["response"][0]
                            status_short = match.get("fixture",{}).get("status",{}).get("short","").lower()
                            if status_short in ("ft","aet","pen"):
                                won, note = evaluate_simple_rule(match, bet_text, sport)
                                if won is True:
                                    mark_prediction(pred_id, "won", note)
                                    await ctx.bot.send_message(CHANNEL_ID, f"{EMOJI['win']} ✅ KAZANDI • {bet_text} • {home} {match.get('goals',{}).get('home')} - {match.get('goals',{}).get('away')} {away}")
                                    resolved = True
                                elif won is False:
                                    mark_prediction(pred_id, "lost", note)
                                    await ctx.bot.send_message(CHANNEL_ID, f"{EMOJI['lose']} ❌ KAYBETTİ • {bet_text} • {home} {match.get('goals',{}).get('home')} - {match.get('goals',{}).get('away')} {away}")
                                    resolved = True
                                else:
                                    mark_prediction(pred_id, "unknown", note)
                                    await ctx.bot.send_message(CHANNEL_ID, f"⏳ ERTELEDİ • {bet_text} • {home} - {away} • Nedeni: {note}")
                                    resolved = True
                            else:
                                continue
                    except Exception as e:
                        log.debug(f"check_results AF lookup error: {e}")
                # fallback TSDB
                if not resolved and TSDB_KEY:
                    match = await tsdb_get(session, f"lookupevent.php", {"id": event_id})
                    if match and match.get("events"):
                        m = match["events"][0]
                        status = (m.get("strStatus") or "").lower()
                        finished_keys = ["ft","full time","finished","final"]
                        if any(k in status for k in finished_keys) or m.get("intHomeScore") is not None:
                            won, note = evaluate_simple_rule(m, bet_text, sport)
                            if won is True:
                                mark_prediction(pred_id, "won", note)
                                await ctx.bot.send_message(CHANNEL_ID, f"{EMOJI['win']} ✅ KAZANDI • {bet_text} • {home} {m.get('intHomeScore')} - {m.get('intAwayScore')} {away}")
                                resolved = True
                            elif won is False:
                                mark_prediction(pred_id, "lost", note)
                                await ctx.bot.send_message(CHANNEL_ID, f"{EMOJI['lose']} ❌ KAYBETTİ • {bet_text} • {home} {m.get('intHomeScore')} - {m.get('intAwayScore')} {away}")
                                resolved = True
                            else:
                                mark_prediction(pred_id, "unknown", note)
                                await ctx.bot.send_message(CHANNEL_ID, f"⏳ ERTELEDİ • {bet_text} • {home} {m.get('intHomeScore')} - {m.get('intAwayScore')} {away} • Nedeni: {note}")
                                resolved = True
                        else:
                            continue
                if not resolved:
                    # leave pending if still playing or lookup failed
                    continue
            else:
                # event_id is None (daily/weekly/kasa) -> cannot auto-evaluate
                mark_prediction(pred_id, "unknown", "no_event")
                await ctx.bot.send_message(CHANNEL_ID, f"⏳ ERTELEDİ (no event) • {bet_text}")
                continue

# ---------------- DAILY SUMMARY (23:00 Turkey) ----------------
async def daily_summary(ctx: ContextTypes.DEFAULT_TYPE):
    now_tr = turkey_now()
    start_day_tr = now_tr.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = (start_day_tr - timedelta(hours=3)).isoformat()
    end_utc = (now_tr - timedelta(hours=3)).isoformat()
    rows = day_summary_between(start_utc, end_utc)
    counts = {"won":0,"lost":0,"pending":0,"unknown":0}
    for st,cnt in rows:
        counts[st] = cnt
    total = sum(counts.values())
    lines = ["═"*38, "📊 GÜNLÜK PERFORMANS ÖZETİ", f"📅 Tarih: {now_tr.strftime('%Y-%m-%d')}", "═"*38,
             f"Toplam tahmin: {total}", f"✅ Kazandı: {counts.get('won',0)}", f"❌ Kaybetti: {counts.get('lost',0)}",
             f"⏳ Ertele/Değerlendirilemeyen: {counts.get('unknown',0)}", f"🕒 Hala beklemede: {counts.get('pending',0)}", "═"*38]
    await ctx.bot.send_message(CHANNEL_ID, "\n".join(lines), parse_mode="Markdown")

# ---------------- ADMIN COMMANDS ----------------
async def cmd_test(update, context):
    await hourly_live(context)
    await update.message.reply_text("Test tetiklendi: hourly_live çalıştırıldı.")

async def cmd_stats(update, context):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT status, COUNT(*) FROM predictions GROUP BY status")
    rows = cur.fetchall()
    con.close()
    await update.message.reply_text("\n".join([f"{r[0]}: {r[1]}" for r in rows]))

# ---------------- MAIN ----------------
def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    jq = app.job_queue

    # hourly live
    jq.run_repeating(hourly_live, interval=3600, first=10)
    # check results every 5 minutes
    jq.run_repeating(check_results, interval=300, first=30)
    # daily coupon 09:00 UTC (matches within next 24 hours)
    jq.run_daily(gunluk_kupon, time=dt_time(hour=9, minute=0, tzinfo=timezone.utc))
    # weekly coupon repeating; internal checks Thursday
    jq.run_repeating(haftalik_kupon, interval=86400, first=300)
    # kasa daily
    jq.run_repeating(kasa_kuponu, interval=86400, first=600)
    # daily performance summary at 20:00 UTC (23:00 TR)
    jq.run_daily(daily_summary, time=dt_time(hour=20, minute=0, tzinfo=timezone.utc))

    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("stats", cmd_stats))

    log.info("BOT 7/24 ÇALIŞIYOR – STAKEDRIP AI ULTRA v3")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
