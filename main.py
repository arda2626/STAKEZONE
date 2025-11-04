# main.py — v61.3 (Syntax Error Fix)

import os
import asyncio
import logging
import json
import random
import sys
from datetime import datetime, timedelta, timezone

import aiohttp
from aiohttp import ClientError
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("v61.3") 

# ENV KONTROLÜ
AI_KEY = os.getenv("AI_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# API keyler (Sizin verdiğiniz ve mevcut anahtarlar)
API_FOOTBALL_KEY = "bd1350bea151ef9f56ed417f0c0c3ea2" 
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6" 
BALLDONTLIE_KEY = os.getenv("BALLDONTLIE_KEY", "").strip() 
FOOTYSTATS_KEY = "test85g57" 
ALLSPORTSAPI_KEY = "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369"
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecwFFgNavnHSIQxabupFbTrHED7FJ"
ISPORTSAPI_KEY = "7MAJu58UDAlMdWrw" 
OPENLIGADB_KEY = os.getenv("OPENLIGADB_KEY", "").strip()
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "").strip() 

# Türkiye zaman dilimi (UTC+3)
TR_TZ = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# Scheduler intervals (saat)
DAILY = 12
VIP = 24
VIP_MAX_MATCHES = 2       
DAILY_MAX_MATCHES = 3     
DAILY_MAX_ODDS = 3.0      
MIN_CONFIDENCE = 60       

# state
posted_matches = {}
last_run = {"DAILY": None, "VIP": None} 
ai_rate_limit = {"calls": 0, "reset": NOW_UTC}

# ---------------- helpers ----------------
def to_local_str(iso_ts: str):
    if not iso_ts: return "Bilinmeyen"
    try:
        dt = datetime.fromisoformat(str(iso_ts).replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
             dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TR_TZ).strftime("%d.%m %H:%M") 
    except Exception: return str(iso_ts)

def within_hours(iso_ts: str, hours: int):
    if not iso_ts: return False
    try:
        dt = datetime.fromisoformat(str(iso_ts).replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
             dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = (dt - now).total_seconds()
        return 0 <= delta <= hours * 3600
    except Exception: return False

def safe_get(d, *keys):
    cur = d
    for k in keys:
        if not isinstance(cur, dict): return None
        cur = cur.get(k)
    return cur

def cleanup_posted_matches():
    global posted_matches
    now = datetime.now(timezone.utc)
    posted_matches = {mid: dt for mid, dt in posted_matches.items() if (now - dt).total_seconds() < 24*3600}
    log.info(f"Temizleme sonrası posted_matches boyutu: {len(posted_matches)}")

def get_odd_for_market(m: dict, prediction_suggestion: str):
    odds_data = m.get("odds")
    if m.get("source") != "TheOdds" or not odds_data or not isinstance(odds_data, list):
        return None
        
    home = m.get('home')
    away = m.get('away')
    
    target_outcome_names = []
    if any(k in prediction_suggestion for k in ["MS 1", "Ev sahibi kazanır"]):
        target_outcome_names = [home, 'Home', '1']
    elif any(k in prediction_suggestion for k in ["MS 2", "Deplasman kazanır"]):
        target_outcome_names = [away, 'Away', '2']
    elif any(k in prediction_suggestion for k in ["Beraberlik", "MS 0", "MS X"]):
        target_outcome_names = ['Draw', 'X', '0']
    else:
        return None 
        
    prices = []
    for bookmaker in odds_data:
        for market in bookmaker.get("markets", []):
            if market.get("key") == "h2h":
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") in target_outcome_names:
                        prices.append(outcome.get("price"))
                        
    return max(prices) if prices else None

def get_all_h2h_odds(m: dict):
    odds_data = m.get("odds")
    res = {'E': '?', 'B': '?', 'D': '?'}
    if m.get("source") != "TheOdds" or not odds_data or not isinstance(odds_data, list):
        return res

    for bookmaker in odds_data:
        for market in bookmaker.get("markets", []):
            if market.get("key") == "h2h":
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name")
                    price = outcome.get("price")
                    if name in [m.get('home'), 'Home', '1']: res['E'] = price
                    if name in [m.get('away'), 'Away', '2']: res['D'] = price
                    if name in ['Draw', 'X', '0']: res['B'] = price
                
                if res['E'] != '?' and res['B'] != '?' and res['D'] != '?':
                    return res
    return res


# ---------------- fetch APIs ----------------

async def fetch_api_football(session):
    name = "API-Football"
    res = []
    url = "https://v3.football.api-sports.io/fixtures"
    end_time = datetime.now(timezone.utc) + timedelta(hours=24)
    params = {"from": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "to": end_time.strftime("%Y-%m-%d")}
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    if not API_FOOTBALL_KEY: log.info(f"{name} Key eksik, atlanıyor."); return res
    try:
        async with session.get(url, params=params, headers=headers, timeout=12) as r:
            if r.status == 429: log.error(f"{name} HATA: Hız limiti aşıldı (429)."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status} (Çalışmıyor/Kısıtlı)."); return res
            if r.status != 200: return res
            
            data = await r.json()
            items = data.get("response") or []
            for it in items:
                fix = it.get("fixture", {})
                status_short = (safe_get(fix, "status", "short") or "").lower()
                start = fix.get("date")
                
                if status_short not in ("ns", "tbd"): continue
                if not within_hours(start, 24): continue
                
                res.append({
                    "id": safe_get(fix,'id'),
                    "home": safe_get(it,"teams","home","name") or "Home",
                    "away": safe_get(it,"teams","away","name") or "Away",
                    "start": start,
                    "source": name,
                    "live": False,
                    "odds": safe_get(it, "odds") or {},
                    "sport": "Football"
                })
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res

async def fetch_the_odds(session):
    name = "TheOdds"
    res = []
    url = "https://api.the-odds-api.com/v4/sports/soccer/odds"
    params = {"regions":"eu","markets":"h2h,totals,spreads","oddsFormat":"decimal","dateFormat":"iso","apiKey":THE_ODDS_API_KEY}
    if not THE_ODDS_API_KEY: log.info(f"{name} Key eksik, atlanıyor."); return res
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status == 429: log.error(f"{name} HATA: Hız limiti aşıldı (429)."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status}"); return res
            if r.status != 200: return res
            
            data = await r.json()
            if isinstance(data, list):
                for it in data:
                    start = it.get("commence_time")
                    if not start: continue
                    if not within_hours(start, 24): continue 
                        
                    res.append({
                        "id": it.get('id'),
                        "home": it.get("home_team","Home"),
                        "away": it.get("away_team","Away"),
                        "start": start,
                        "source": name,
                        "live": False,
                        "odds": it.get("bookmakers", []),
                        "sport": it.get("sport_key", "Soccer")
                    })
            log.info(f"{name} raw:{len(data) if isinstance(data, list) else 0} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res

async def fetch_footystats(session):
    name = "FootyStats"
    res = []
    url = "https://api.footystats.org/league-matches"
    params = {"key": FOOTYSTATS_KEY}
    if not FOOTYSTATS_KEY: log.info(f"{name} Key eksik, atlanıyor."); return res
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status == 429: log.error(f"{name} HATA: Hız limiti aşıldı (429)."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status} (Kısıtlı)."); return res
            if r.status != 200: return res
            
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("match_start_iso") or it.get("start_date")
                status = it.get("status")
                
                if status != "upcoming": continue
                if not within_hours(start, 24): continue
                
                res.append({
                    "id": it.get('id'),
                    "home": it.get("home_name","Home"),
                    "away": it.get("away_name","Away"),
                    "start": start,
                    "source": name,
                    "live": False,
                    "odds": {},
                    "sport": "Football"
                })
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res

async def fetch_allsports(session):
    name = "AllSportsAPI"
    res = []
    url = "https://allsportsapi2.p.rapidapi.com/api/football/matches/upcoming" 
    headers = {"x-rapidapi-host":"allsportsapi2.p.rapidapi.com","x-rapidapi-key":ALLSPORTSAPI_KEY}
    if not ALLSPORTSAPI_KEY: log.info(f"{name} Key eksik, atlanıyor."); return res
    try:
        async with session.get(url, headers=headers, timeout=12) as r:
            if r.status == 429 or r.status == 403: log.error(f"{name} HATA: Limit/Erişim sorunu ({r.status})."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status} (Kısıtlı)."); return res
            if r.status != 200: return res
            
            data = await r.json()
            items = data.get("result") or []
            for it in items:
                start = it.get("event_date_start")
                
                if not within_hours(start, 24): continue
                
                res.append({
                    "id": it.get('event_key'),
                    "home": it.get("event_home_team","Home"),
                    "away": it.get("event_away_team","Away"),
                    "start": start,
                    "source": name,
                    "live": False,
                    "odds": {},
                    "sport": "Football"
                })
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res

async def fetch_sportsmonks(session):
    name = "SportsMonks"
    res = []
    url = "https://api.sportmonks.com/v3/football/fixtures"
    params = {"api_token": SPORTSMONKS_KEY, "include": "odds", "filter[starts_between]": f"{NOW_UTC.strftime('%Y-%m-%d')},{ (NOW_UTC + timedelta(days=1)).strftime('%Y-%m-%d')}"}
    if not SPORTSMONKS_KEY: log.info(f"{name} Key eksik, atlanıyor."); return res
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status == 429 or r.status == 403: log.error(f"{name} HATA: Limit/Erişim sorunu ({r.status})."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status} (Kısıtlı)."); return res
            if r.status != 200: return res
            
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("starting_at")
                
                if not within_hours(start, 24): continue
                
                res.append({
                    "id": it.get('id'),
                    "home": it.get("home_team_name","Home"),
                    "away": it.get("away_team_name","Away"),
                    "start": start,
                    "source": name,
                    "live": False,
                    "odds": it.get("odds", {}),
                    "sport": "Football"
                })
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res

async def fetch_isports(session):
    name = "iSportsAPI"
    res = []
    url = "https://api.isportsapi.com/sport/schedule/matches" 
    params = {"api_key": ISPORTSAPI_KEY, "date": NOW_UTC.strftime("%Y-%m-%d")}
    if not ISPORTSAPI_KEY: log.info(f"{name} Key eksik, atlanıyor."); return res
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status == 429 or r.status == 403: log.error(f"{name} HATA: Limit/Erişim sorunu ({r.status})."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status} (Kısıtlı)."); return res
            if r.status != 200: return res
            
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("matchTime") 
                
                if it.get("matchStatus") != 0: continue
                if not within_hours(start, 24): continue
                
                res.append({
                    "id": it.get('matchId'),
                    "home": it.get("homeTeamName","Home"),
                    "away": it.get("awayTeamName","Away"),
                    "start": start,
                    "source": name,
                    "live": False,
                    "odds": it.get("odds", {}),
                    "sport": it.get("sportType", "Bilinmeyen")
                })
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res

# ÜCRETSİZ/AÇIK KAYNAK API'ler

async def fetch_ergast(session):
    name = "Ergast (F1)"
    res = []
    url = "http://ergast.com/api/f1/current/next.json" 
    try:
        async with session.get(url, timeout=12) as r:
            if r.status != 200: log.warning(f"{name} HTTP HATA: {r.status}"); return res
            
            data = await r.json()
            race_table = safe_get(data, "MRData", "RaceTable", "Races")
            if not race_table: return res
            
            for race in race_table:
                race_name = race.get("raceName")
                date = race.get("Date")
                time = race.get("Time", "00:00:00Z")
                start = f"{date}T{time}"
                
                if not within_hours(start, 24): continue
                
                res.append({
                    "id": race.get('raceId'),
                    "home": race_name,
                    "away": race.get("Circuit", {}).get("circuitName", "Pist"),
                    "start": start,
                    "source": name,
                    "live": False,
                    "odds": {},
                    "sport": "Formula 1"
                })
            log.info(f"{name} raw:{len(race_table)} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res

async def fetch_nhl(session):
    name = "NHL Stats"
    res = []
    today = datetime.now(TR_TZ).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(TR_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://statsapi.web.nhl.com/api/v1/schedule?startDate={today}&endDate={tomorrow}"
    try:
        async with session.get(url, timeout=12) as r:
            if r.status != 200: log.warning(f"{name} HTTP HATA: {r.status}"); return res
            
            data = await r.json()
            dates = data.get("dates") or []
            
            for date_data in dates:
                for game in date_data.get("games", []):
                    game_pk = game.get("gamePk")
                    start_time = game.get("gameDate")
                    status = safe_get(game, "status", "detailedState")
                    
                    if status not in ("Scheduled", "Pre-Game"): continue
                    if not within_hours(start_time, 24): continue
                    
                    home_team = safe_get(game, "teams", "home", "team", "name")
                    away_team = safe_get(game, "teams", "away", "team", "name")
                    
                    res.append({
                        "id": game_pk,
                        "home": home_team,
                        "away": away_team,
                        "start": start_time,
                        "source": name,
                        "live": False,
                        "odds": {},
                        "sport": "Buz Hokeyi (NHL)"
                    })
            log.info(f"{name} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res

async def fetch_openligadb(session):
    name = "OpenLigaDB"
    res = []
    url = "https://www.openligadb.de/api/getmatchdata/bl1/2025/1"
    try:
        async with session.get(url, timeout=12) as r:
            if r.status != 200: log.warning(f"{name} HTTP HATA: {r.status} (Kısıtlı)."); return res
            
            items = await r.json()
            if not isinstance(items, list): items = []
            
            for it in items:
                start = it.get("matchDateTimeUTC")
                
                if it.get("matchIsFinished"): continue
                if not within_hours(start, 24): continue
                
                res.append({
                    "id": it.get('matchID'),
                    "home": safe_get(it,"team1","teamName") or "Home",
                    "away": safe_get(it,"team2","teamName") or "Away",
                    "start": start,
                    "source": name,
                    "live": False,
                    "odds": {},
                    "sport": "Football (Bundesliga)"
                })
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res

async def fetch_balldontlie(session):
    name = "BallDontLie"
    res = []
    url = "https://www.balldontlie.io/api/v1/games" 
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    params = {"dates[]": [today, tomorrow]}
    
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status != 200: log.warning(f"{name} HTTP HATA: {r.status} (Kısıtlı)."); return res
            
            data = await r.json()
            items = data.get("data") or []
            
            for it in items:
                start = it.get("status")
                match_date = it.get("date")
                
                if start != "Pre Game": continue
                
                full_start = f"{match_date.split('T')[0]}T00:00:00Z" 
                
                if not within_hours(full_start, 48): continue
                
                res.append({
                    "id": it.get('id'),
                    "home": safe_get(it,"home_team","full_name") or "Home",
                    # Hata giderildi: Fazla parantez kaldırıldı.
                    "away": safe_get(it,"visitor_team","full_name") or "Away", 
                    "start": full_start,
                    "source": name,
                    "live": False,
                    "odds": {}, 
                    "sport": "Basketball (NBA)"
                })
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
            
    except Exception as e: 
        log.warning(f"{name} hata: {e}"); return res
    return res

async def fetch_footballdata(session):
    name = "FootballData"
    res = []
    url = "https://api.football-data.org/v4/matches" 
    headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
    if not FOOTBALL_DATA_KEY: log.info(f"{name} Key eksik, atlanıyor."); return res
    try:
        async with session.get(url, headers=headers, timeout=12) as r:
            if r.status == 429 or r.status == 403: log.error(f"{name} HATA: Limit/Erişim sorunu ({r.status})."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status} (Kısıtlı)."); return res
            
            data = await r.json()
            items = data.get("matches") or []
            
            for it in items:
                start = it.get("utcDate")
                
                if it.get("status") not in ("SCHEDULED", "TIMED"): continue
                if not within_hours(start, 24): continue
                
                res.append({
                    "id": it.get('id'),
                    "home": safe_get(it,"homeTeam","name") or "Home",
                    "away": safe_get(it,"awayTeam","name") or "Away",
                    "start": start,
                    "source": name,
                    "live": False,
                    "odds": {},
                    "sport": "Football"
                })
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res


# ---------------- FETCH ALL MATCHES ----------------
async def fetch_all_matches():
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_api_football(session),
            fetch_the_odds(session),
            fetch_footystats(session),
            fetch_allsports(session),
            fetch_sportsmonks(session),
            fetch_isports(session),
            fetch_ergast(session),
            fetch_nhl(session),
            fetch_openligadb(session),
            fetch_balldontlie(session),
            fetch_footballdata(session),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_matches = []
    for r in results:
        if isinstance(r, Exception):
            log.warning(f"fetch task exception: {r}")
            continue
        all_matches.extend(r or [])
        
    normalized = []
    for m in all_matches:
        start = m.get("start") or m.get("date") or ""
        if isinstance(start, (int, float)):
            try:
                start = datetime.fromtimestamp(int(start), tz=timezone.utc).isoformat().replace('+00:00', 'Z')
            except:
                start = ""
        
        match_id_base = m.get("id") or hash(json.dumps(m, default=str))
        final_id = f"{m.get('source')}_{match_id_base}"
        
        normalized.append({
            "id": final_id,
            "home": m.get("home"),
            "away": m.get("away"),
            "start": start,
            "source": m.get("source"),
            "live": bool(m.get("live")),
            "odds": m.get("odds", {}),
            "sport": m.get("sport", "Bilinmeyen Spor")
        })
        
    seen = set()
    final = []
    for m in normalized:
        key = m.get("id")
        if not key: continue
        if key in seen:
            continue
        seen.add(key)
        final.append(m)
        
    log.info(f"Toplam çekilen maç (normalized, dedup): {len(final)}")
    return final

# ---------------- OpenAI integration ----------------
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

async def call_openai_chat(prompt: str, max_tokens=300, temperature=0.2):
    global ai_rate_limit
    now = datetime.now(timezone.utc)
    
    if ai_rate_limit["reset"] < now:
        ai_rate_limit["calls"] = 0
        ai_rate_limit["reset"] = now + timedelta(seconds=60) 
    
    if ai_rate_limit["calls"] >= 2: 
        log.warning("OpenAI lokal kısıtlama (3 RPM limitine ulaşıldı). Fallback.")
        return None 
        
    ai_rate_limit["calls"] += 1 
    
    headers = {"Authorization": f"Bearer {AI_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages":[
            {"role":"system","content":"Sen Türkçe konuşan spor analisti ve veri bilimcisisin. Verilen maç bilgisine göre en anlamlı bahis piyasalarını (MS, TOTALS, BTTS/KG) JSON formatında sırala. Cevapta başka metin olmamalı, sadece JSON olmalı."},
            {"role":"user","content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OPENAI_URL, headers=headers, json=payload) as resp:
                txt = await resp.text()
                
                if resp.status == 429: log.error(f"OpenAI API 429 Hata: Hız limitine ulaşıldı. Fallback."); return None
                if resp.status != 200: log.warning(f"OpenAI HTTP {resp.status}: {txt[:400]}"); return None
                
                try:
                    data = json.loads(txt)
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start: return json.loads(content[start:end])
                    return json.loads(content)
                except Exception as e:
                    log.warning(f"OpenAI parse hatası: {e}. Raw content: {content[:100]}")
                    return None
                    
    except Exception as e:
        log.warning(f"OpenAI beklenmeyen hata: {e}")
        return None

# ---------------- Prediction wrapper ----------------
async def predict_for_match(m: dict, vip_surprise=False):
    temp = 0.2 if not vip_surprise else 0.05 
    
    prompt = (
        f"Spor: {m.get('sport')}\nMaç: {m.get('home')} vs {m.get('away')}\n"
        f"Tarih(UTC): {m.get('start')}\n"
    )
    if m.get("odds"): prompt += "Oran bilgisi mevcut.\n"
    prompt += (
        "İstediğim JSON formatı: {\"predictions\":[{\"market\":\"MS\",\"suggestion\":\"MS 1\",\"confidence\":85,\"explanation\":\"...\"}],\"best\":0}. "
        "Confidence 0-100 arasında bir tam sayı olmalı. Cevabı yalnızca JSON ver."
    )
    
    ai_resp = await call_openai_chat(prompt, max_tokens=300, temperature=temp)
    
    if not ai_resp or not isinstance(ai_resp, dict) or "predictions" not in ai_resp:
        log.warning(f"AI tahmini başarısız veya boş: {m.get('id')}. Fallback kullanılıyor.")
        
        preds = []
        if vip_surprise: 
            preds.append({"market":"TOTALS","suggestion":"Over 3.5","confidence":61,"explanation":"Yüksek skorlu sürpriz beklentisi."})
            preds.append({"market":"MS","suggestion":"MS X","confidence":55,"explanation":"Eşit güçler, riskli beraberlik."})
        else: 
            preds.append({"market":"MS","suggestion":"MS 1","confidence":60,"explanation":"Ev sahibi avantajlı görünüyor."})
            preds.append({"market":"TOTALS","suggestion":"Under 2.5","confidence":55,"explanation":"Düşük skorlu mücadele bekleniyor."})

        best_idx = max(range(len(preds)), key=lambda i: preds[i]["confidence"])
        return {"predictions": preds, "best": best_idx, "fallback": True}
        
    preds = ai_resp.get("predictions", [])
    for p in preds:
        try: p["confidence"] = max(0, min(100, int(p.get("confidence",50))))
        except: p["confidence"] = 50
            
    best = ai_resp.get("best", 0)
    if not isinstance(best, int) or best < 0 or best >= len(preds):
        best = max(range(len(preds)), key=lambda i: preds[i]["confidence"]) if preds else 0
        
    return {"predictions": preds, "best": best, "fallback": False}

# ---------------- Build coupon ----------------
def format_match_block(m, pred):
    start_local = to_local_str(m.get("start") or "")
    best = pred["predictions"][pred["best"]] if pred["predictions"] else None
    
    h2h_odds = get_all_h2h_odds(m)
    odd_display = f"E:{h2h_odds['E']} | B:{h2h_odds['B']} | D:{h2h_odds['D']}"
    
    suggestion = best.get('suggestion', 'Bilinmiyor')
    confidence = best.get('confidence', 0)
    explanation = best.get('explanation','').replace(" (F)", "") 
    
    # Spor adını parantez içinde değil, sadece adını göster
    sport_name = m.get('sport','Bilinmeyen Spor').split('(')[0].strip()
    
    block = (
        f"🏆 <b>{m.get('home')} vs {m.get('away')}</b>\n"
        f"📅 {start_local} | {sport_name}\n"
        f"📈 <b>{suggestion}</b> <tg-spoiler>(%{confidence})</tg-spoiler>\n"
        f"  - <i>{explanation}</i>\n"
        f"💸 <tg-spoiler>MS Oran: {odd_display}</tg-spoiler>"
    )
    
    return block

async def build_coupon_text(matches, title, max_matches):
    global posted_matches
    
    lines = []
    count = 0
    now = datetime.now(timezone.utc)
    
    is_daily_coupon = "GÜNLÜK" in title
    
    match_preds = []
    for m in matches:
        pred = await predict_for_match(m, vip_surprise=("👑 VIP" in title))
        if pred and pred.get("predictions"):
            best = pred["predictions"][pred["best"]]
            
            if best["confidence"] < MIN_CONFIDENCE:
                continue
            
            if is_daily_coupon and DAILY_MAX_ODDS:
                if any(k in best["suggestion"] for k in ["MS 1", "MS 2", "Beraberlik"]):
                    odd = get_odd_for_market(m, best["suggestion"])
                    
                    if odd is None or odd > DAILY_MAX_ODDS:
                        continue
            
            match_preds.append((m, pred, best["confidence"]))

    match_preds.sort(key=lambda x: x[2], reverse=True)
    
    for m, pred, confidence in match_preds:
        if count >= max_matches: break
            
        match_id = m.get("id")
        if match_id in posted_matches and (now - posted_matches[match_id]).total_seconds() < 24*3600:
            log.info(f"Maç atlandı (zaten yayınlandı): {m.get('home')} vs {m.get('away')}")
            continue
            
        lines.append(format_match_block(m, pred))
            
        # Maç yayınlanmadan önce tekrar yayınlanmasını önlemek için id'yi kaydedin.
        if "TEST" not in title: 
             posted_matches[match_id] = now
             
        count += 1
            
    if not lines: return None
        
    header = (
        f"━━━━━━━━━━━━━━━\n"
        f"   {title}\n"
        f"━━━━━━━━━━━━━━━\n"
    )
    footer = (
        f"\n━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Bahis risklidir. Tahminler yalnızca yapay zeka analizi amaçlıdır.</i>\n"
    )
    return header + "\n\n" + "\n\n".join(lines) + footer

# ---------------- Job runner ----------------
async def job_runner(app: Application):
    global last_run
    
    # İlk çalıştırma için bekleme süresi
    await asyncio.sleep(15) 
    
    while True:
        try:
            now = datetime.now(timezone.utc)
            cleanup_posted_matches()
            
            matches = await fetch_all_matches() 
            
            if not matches:
                log.info("Tüm API'ler boş veya veri yok.")
            else:
                
                # --- DAILY (12 saatlik) ---
                lr_daily = last_run.get("DAILY")
                if not lr_daily or (now - lr_daily).total_seconds() >= DAILY*3600:
                    log.info("Günlük yayın döngüsü başladı.")
                    
                    text = await build_coupon_text(
                        matches, 
                        "🗓️ GÜNLÜK AI SEÇİMİ (Oran Max 3.0)", 
                        max_matches=DAILY_MAX_MATCHES
                    )
                    if text:
                        await send_to_channel(app, text)
                    last_run["DAILY"] = now
                        
                # --- VIP (24 saatlik, sürpriz) ---
                lr_vip = last_run.get("VIP")
                if not lr_vip or (now - lr_vip).total_seconds() >= VIP*3600:
                    log.info("VIP yayın döngüsü başladı.")
                    
                    text = await build_coupon_text(
                        matches, 
                        "👑 VIP AI SÜRPRİZ KUPON", 
                        max_matches=VIP_MAX_MATCHES
                    )
                    if text:
                        await send_to_channel(app, text)
                    last_run["VIP"] = now
                        
        except Exception as e:
            log.exception(f"Job runner hata: {e}")
            
        # 1 saat bekle
        await asyncio.sleep(3600)

async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.info("Test komutu çalıştırıldı.")
    await update.message.reply_text("Test başlatılıyor, lütfen bekleyin. Maçlar çekiliyor...")
    
    matches = await fetch_all_matches() 
    if not matches:
        await update.message.reply_text("Maç bulunamadı (24 saat içinde başlayacak).")
        return
        
    text = await build_coupon_text(
        matches, 
        "🚨 TEST AI KUPON (MANUEL)", 
        max_matches=5
    )
    
    if text:
        await update.message.reply_text(text, parse_mode="HTML") 
    else:
        await update.message.reply_text("Kupon oluşturulamadı (Filtrelere takılmış olabilir).")

# ---------------- MAIN ----------------
async def send_to_channel(app, text):
    try:
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML", disable_web_page_preview=True)
        log.info("Kupon gönderildi.")
    except Exception as e:
        log.exception(f"Telegram gönderim hatası: {e}")

def main():
    # ... (Gerekli anahtar kontrolü) ...
    if not TELEGRAM_TOKEN: log.error("TELEGRAM_TOKEN ayarlı değil. Çıkılıyor."); sys.exit(1)
    if not AI_KEY: log.error("AI_KEY ayarlı değil. Çıkılıyor."); sys.exit(1)
    if not TELEGRAM_CHAT_ID: log.critical("TELEGRAM_CHAT_ID ayarlı değil. Çıkılıyor."); sys.exit(1)
        
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("test", cmd_test))
    
    async def post_init_callback(application: Application):
        asyncio.create_task(job_runner(application))
        log.info("Job runner başarıyla asenkron görev olarak başlatıldı.")

    app.post_init = post_init_callback
    
    log.info("v61.3 başlatıldı. Telegram polling başlatılıyor...")
    
    app.run_polling(poll_interval=1.0, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        cleanup_posted_matches()
        main() 
        
    except KeyboardInterrupt: log.info("Durduruldu.")
    except Exception as e: log.critical(f"Kritik hata: {e}", exc_info=True); sys.exit(1)
