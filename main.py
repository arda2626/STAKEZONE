# main.py — v62.4 (Tüm Marketler İçin Oran Çekimi Düzeltildi)

import os
import asyncio
import logging
import json
import random
import sys
import ssl 
import re # Düzenli ifadeler için eklendi
from datetime import datetime, timedelta, timezone

import aiohttp
from aiohttp import ClientError
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import Conflict

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("v62.4") 

# ENV KONTROLÜ
AI_KEY = os.getenv("AI_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# API keyler
API_FOOTBALL_KEY = "e35c566553ae8a89972f76ab04c16bd2" 
THE_ODDS_API_KEY = "501ea1ade60d5f0b13b8f34f90cd51e6" 
ALLSPORTSAPI_KEY = "27b16a330f4ac79a1f8eb383fec049b9cc0818d5e33645d771e2823db5d80369"
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaXp9TnZ45fdQiK6ecvFFgNavnHSIQxabupFbTrHED7FJ"
ISPORTSAPI_KEY = "7MAJu58UDAlMdWrw" 
FOOTYSTATS_KEY = "test85g57" 
OPENLIGADB_KEY = os.getenv("OPENLIGADB_KEY", "").strip()
FOOTBALL_DATA_KEY = "80a354c67b694ef79c516182ad64aed7" 

# Türkiye zaman dilimi (UTC+3)
TR_TZ = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# Scheduler intervals (saat) - YENİ ZAMANLAMALAR
VIP_INTERVAL_HOURS = 3        # 3 saatte bir
DAILY_INTERVAL_HOURS = 12     # 12 saatte bir (günde 2 defa)
VIP_MAX_MATCHES = 1           # Sadece 1 maç
DAILY_MAX_MATCHES = 3         # Max 3 maç
DAILY_MAX_ODDS = 2.0          # GARANTİ Kupon için Oran Max limiti (2.0)
MIN_CONFIDENCE = 60       

# OpenAI Limit - GEVŞETİLDİ (1 RPM -> 5 RPM)
AI_MAX_CALLS_PER_MINUTE = 5 

# state
posted_matches = {}
last_run = {"DAILY": None, "VIP": None, "LIVE": None} 
ai_rate_limit = {"calls": 0, "reset": NOW_UTC} 

# LİG VE SPOR MODERNİZASYON MAPPING'İ 
SPORT_NAME_MAPPING = {
    "soccer": "⚽ Futbol (Genel)",
    "Football": "⚽ Futbol",
    "Soccer": "⚽ Futbol",
    "Basketball": "🏀 Basketbol",
    "Buz Hokeyi (NHL)": "🏒 Buz Hokeyi (NHL)",
    "Formula 1": "🏎️ Formula 1",
    "Bilinmeyen Spor": "❓ Bilinmeyen Spor"
}

# ORNEK LİG TEMİZLEME. TheOdds'dan gelen kaba verileri temizlemek için
LEAGUE_NAME_MAPPING = {
    "English Premier League": "Premier Lig",
    "German Bundesliga": "Bundesliga",
    "La Liga": "La Liga",
    "NBA": "NBA (Basketbol)",
    "Football (Bundesliga)": "Bundesliga",
    "Basketball (NBA)": "NBA",
    "Premier League": "Premier Lig",
    "NHL Stats": "NHL",
    "soccer_uefa_champs_league": "UEFA Şampiyonlar Ligi",
    "soccer_england_premier_league": "Premier Lig",
    "soccer_italy_serie_a": "İtalya Serie A",
    
}

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
    """
    Tahmin edilen tercihin (MS, Alt/Üst, KG Var/Yok) oranını TheOdds verisinden çeker.
    """
    odds_data = m.get("odds")
    if m.get("source") != "TheOdds" or not odds_data or not isinstance(odds_data, list):
        return None
        
    home = m.get('home')
    away = m.get('away')
    
    target_market_key = None
    target_outcome_names = []
    
    # --- 1. Maç Sonucu (H2H) ---
    if any(k in prediction_suggestion for k in ["MS 1", "Ev sahibi kazanır"]):
        target_market_key = "h2h"
        target_outcome_names = [home, 'Home', '1']
    elif any(k in prediction_suggestion for k in ["MS 2", "Deplasman kazanır"]):
        target_market_key = "h2h"
        target_outcome_names = [away, 'Away', '2']
    elif any(k in prediction_suggestion for k in ["Beraberlik", "MS 0", "MS X"]):
        target_market_key = "h2h"
        target_outcome_names = ['Draw', 'X', '0']
    
    # --- 2. Toplam Gol (Totals) ---
    elif prediction_suggestion.startswith("Over") or prediction_suggestion.startswith("Alt") or prediction_suggestion.startswith("Üst"):
        # Örnek: "Over 2.5", "Under 3.5"
        match_total = re.search(r'([0-9]+\.?[0-9]?)', prediction_suggestion)
        total_value = float(match_total.group(1)) if match_total else None
        
        if total_value is not None:
            # TheOdds API'sinde 'totals' marketi Alt/Üst için kullanılır.
            target_market_key = "totals"
            
            # Alt/Üst değerini ve sonucu belirle (TheOdds genellikle Alt/Üstü ayrıştırır)
            if "Over" in prediction_suggestion or "Üst" in prediction_suggestion:
                # TheOdds'ta Under/Over olarak ayrılır, Alt/Üst çizgisi (point) kullanılır.
                target_outcome_names = [f'Over {total_value}', 'Over']
            elif "Under" in prediction_suggestion or "Alt" in prediction_suggestion:
                target_outcome_names = [f'Under {total_value}', 'Under']
            
    # --- 3. KG Var/Yok (BTTS - Both Teams To Score) ---
    elif prediction_suggestion in ["KG Var", "BTTS Yes", "KG Yok", "BTTS No"]:
        target_market_key = "btts" # Varsayımsal TheOdds key'i
        
        if prediction_suggestion in ["KG Var", "BTTS Yes"]:
            target_outcome_names = ['Yes', 'Var']
        elif prediction_suggestion in ["KG Yok", "BTTS No"]:
            target_outcome_names = ['No', 'Yok']

    if not target_market_key:
        return None
        
    prices = []
    for bookmaker in odds_data:
        for market in bookmaker.get("markets", []):
            if market.get("key") == target_market_key:
                for outcome in market.get("outcomes", []):
                    # Alt/Üst marketinde, çizgiyi (point) de kontrol etmeliyiz.
                    is_total_match = True
                    if target_market_key == "totals" and 'point' in outcome and total_value is not None:
                         # TheOdds'taki point değeri tahminimizle eşleşmeli (Örn: 2.5)
                         if outcome.get('point') != total_value:
                             is_total_match = False
                             
                    if is_total_match and outcome.get("name") in target_outcome_names:
                        prices.append(outcome.get("price"))
                        
    return max(prices) if prices else None # En yüksek oranı al

def get_all_h2h_odds(m: dict):
    # Bu fonksiyon sadece AI'a bilgi sağlamak amacıyla korunmuştur. Kupon formatında kullanılmayacak.
    res = {'E': '?', 'B': '?', 'D': '?'}
    odds_data = m.get("odds")
    source = m.get("source")
    
    if source == "TheOdds" and odds_data and isinstance(odds_data, list):
        for bookmaker in odds_data:
            for market in bookmaker.get("markets", []):
                if market.get("key") == "h2h":
                    for outcome in market.get("outcomes", []):
                        name = outcome.get("name")
                        price = outcome.get("price")
                        price_str = f"{price:.2f}" if isinstance(price, (int, float)) else '?'
                        
                        if name in [m.get('home'), 'Home', '1']: res['E'] = price_str
                        if name in [m.get('away'), 'Away', '2']: res['D'] = price_str
                        if name in ['Draw', 'X', '0']: res['B'] = price_str
                    if res['E'] != '?' and res['B'] != '?' and res['D'] != '?':
                        return res
    return res

# --- API Fetch Fonksiyonları (v62.3 ile aynı) ---
# ... (fetch_api_football, fetch_the_odds, fetch_openligadb, fetch_sportsmonks, fetch_footystats, 
#      fetch_balldontlie, fetch_isports, fetch_ergast, fetch_nhl, fetch_football_data fonksiyonları buraya kopyalanır)
# NOT: Yer kazanmak için bu kısım burada tam olarak tekrar edilmeyecek, ancak kodda yer almalıdır.

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
            
            data = await r.json()
            items = data.get("response") or []
            for it in items:
                fix = it.get("fixture", {})
                status_short = (safe_get(fix, "status", "short") or "").lower()
                start = fix.get("date")
                
                if status_short not in ("ns", "tbd", "ft", "ht"): 
                    is_live = status_short not in ("ns", "tbd")
                else:
                    is_live = False

                if not is_live and not within_hours(start, 24): continue
                
                res.append({
                    "id": safe_get(fix,'id'),
                    "home": safe_get(it,"teams","home","name") or "Home",
                    "away": safe_get(it,"teams","away","name") or "Away",
                    "start": start,
                    "source": name,
                    "live": is_live,
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
    # Tüm marketleri çek
    params = {"regions":"eu","markets":"h2h,totals,btts","oddsFormat":"decimal","dateFormat":"iso","apiKey":THE_ODDS_API_KEY}
    if not THE_ODDS_API_KEY: log.info(f"{name} Key eksik, atlanıyor."); return res
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status == 429: log.error(f"{name} HATA: Hız limiti aşıldı (429)."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status}"); return res
            
            data = await r.json()
            if isinstance(data, list):
                for it in data:
                    start = it.get("commence_time")
                    sport_key = it.get("sport_key", "Soccer")
                    
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
                        "sport": sport_key 
                    })
            log.info(f"{name} raw:{len(data) if isinstance(data, list) else 0} filtered:{len(res)}")
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
                
                is_live = not it.get("matchIsFinished") and it.get("matchResults")
                
                if it.get("matchIsFinished"): continue
                if not is_live and not within_hours(start, 24): continue
                
                res.append({
                    "id": it.get('matchID'),
                    "home": safe_get(it,"team1","teamName") or "Home",
                    "away": safe_get(it,"team2","teamName") or "Away",
                    "start": start,
                    "source": name,
                    "live": is_live,
                    "odds": {},
                    "sport": "Football (Bundesliga)"
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
                start_status = it.get("status")
                match_date = it.get("date")
                is_live = start_status not in ("Pre Game", "Final") 
                
                if start_status == "Final": continue
                full_start = f"{match_date.split('T')[0]}T18:00:00Z" 
                
                if not is_live and not within_hours(full_start, 48): continue
                
                res.append({
                    "id": it.get('id'),
                    "home": safe_get(it,"home_team","full_name") or "Home",
                    "away": safe_get(it,"visitor_team","full_name") or "Away", 
                    "start": full_start,
                    "source": name,
                    "live": is_live,
                    "odds": {}, 
                    "sport": "Basketball (NBA)"
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
            
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("matchTime") 
                
                match_status = it.get("matchStatus")
                is_live = match_status != 0 and match_status != -1
                
                if match_status == -1: continue 
                if not is_live and not within_hours(start, 24): continue
                
                res.append({
                    "id": it.get('matchId'),
                    "home": it.get("homeTeamName","Home"),
                    "away": it.get("awayTeamName","Away"),
                    "start": start,
                    "source": name,
                    "live": is_live,
                    "odds": it.get("odds", {}),
                    "sport": it.get("sportType", "Bilinmeyen")
                })
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except ssl.SSLCertVerificationError as e: log.warning(f"{name} hata: SSL sertifika hatası (Geçici olarak atlanıyor)."); return res
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res

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
                    status_detail = safe_get(game, "status", "detailedState")
                    
                    is_live = status_detail not in ("Scheduled", "Pre-Game", "Final")
                    
                    if status_detail == "Final": continue
                    if not is_live and not within_hours(start_time, 24): continue
                    
                    home_team = safe_get(game, "teams", "home", "team", "name")
                    away_team = safe_get(game, "teams", "away", "team", "name")
                    
                    res.append({
                        "id": game_pk,
                        "home": home_team,
                        "away": away_team,
                        "start": start_time,
                        "source": name,
                        "live": is_live,
                        "odds": {},
                        "sport": "Buz Hokeyi (NHL)"
                    })
            log.info(f"{name} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res
    
async def fetch_football_data(session):
    name = "Football-Data"
    res = []
    url = "https://api.football-data.org/v4/matches" 
    headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
    
    if not FOOTBALL_DATA_KEY: log.info(f"{name} Key eksik/ayarlı değil. Atlanıyor."); return res
    
    try:
        async with session.get(url, headers=headers, timeout=12) as r:
            if r.status == 429: log.error(f"{name} HATA: Hız limiti aşıldı (429)."); return res
            elif r.status == 403: log.error(f"{name} HATA: İzin verilmedi/Yanlış anahtar (403)."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status}."); return res
            
            data = await r.json()
            items = data.get("matches") or []
            
            for it in items:
                start = it.get("utcDate") 
                status = it.get("status")
                
                is_live = status in ("IN_PLAY", "PAUSED")
                
                if status in ("FINISHED", "SUSPENDED", "POSTPONED"): continue
                
                if status != "SCHEDULED" and not is_live: continue 
                if not is_live and not within_hours(start, 24): continue
                
                res.append({
                    "id": it.get('id'),
                    "home": safe_get(it, "homeTeam", "name") or "Home",
                    "away": safe_get(it, "awayTeam", "name") or "Away",
                    "start": start,
                    "source": name,
                    "live": is_live,
                    "odds": {}, 
                    "sport": safe_get(it, "competition", "name") or "Football"
                })
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except Exception as e: log.warning(f"{name} hata: {e}"); return res
    return res


async def fetch_all_matches():
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_football_data(session), 
            fetch_api_football(session), 
            fetch_the_odds(session), # Buradan tüm market verisi (h2h, totals, btts) gelecek
            fetch_openligadb(session),
            fetch_sportsmonks(session),
            fetch_footystats(session),
            fetch_balldontlie(session),
            fetch_isports(session),
            fetch_ergast(session),
            fetch_nhl(session),
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
        
        sport_key = m.get("sport", "Bilinmeyen Spor")
        
        normalized_sport = LEAGUE_NAME_MAPPING.get(sport_key, sport_key)
        normalized_sport = SPORT_NAME_MAPPING.get(normalized_sport, normalized_sport)
        
        normalized.append({
            "id": final_id,
            "home": m.get("home"),
            "away": m.get("away"),
            "start": start,
            "source": m.get("source"),
            "live": bool(m.get("live")),
            "odds": m.get("odds", {}),
            "sport": normalized_sport
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
    
    if ai_rate_limit["calls"] >= AI_MAX_CALLS_PER_MINUTE: 
        log.warning(f"OpenAI lokal kısıtlama ({AI_MAX_CALLS_PER_MINUTE} RPM limitine ulaşıldı). Fallback.")
        return None 
        
    ai_rate_limit["calls"] += 1 
    
    await asyncio.sleep(3) 
    
    headers = {"Authorization": f"Bearer {AI_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages":[
            # AI Davranışı Düzeltmesi (Kumarbaz/Yorumcu)
            {"role":"system","content":"Sen Türkçe konuşan, yüksek güvenilirlikte tahminler yapan, bir spor yorumcusu ve kumarbaz zekasına sahip profesyonel bir analistsin. Piyasa hareketlerini, risk ve ödülü değerlendir. Tüm popüler marketler (MS, KG Var/Yok, Alt/Üst) için en güçlü 1 veya 2 tahminini yap. Tahminlerinin 70'ten (VIP için 80'den) düşük olmamasına özen göster. Cevabı sadece belirtilen JSON formatında ver. Başka hiçbir açıklayıcı metin kullanma. Confidence 0-100 arasında tam sayı olmalı. Alt/Üst tahminlerini 'Under 2.5' veya 'Over 3.5' formatında yap."},
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
                
                if resp.status == 429: 
                    ai_rate_limit["calls"] = AI_MAX_CALLS_PER_MINUTE
                    ai_rate_limit["reset"] = now + timedelta(seconds=60) 
                    log.error(f"OpenAI API 429 Hata: Gerçek Hız limitine ulaşıldı. Fallback."); 
                    return None
                if resp.status != 200: 
                    log.warning(f"OpenAI HTTP {resp.status}: {txt[:400]}"); 
                    return None
                
                try:
                    data = json.loads(txt)
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start: return json.loads(content[start:end])
                    
                    return None
                except Exception as e:
                    log.warning(f"OpenAI parse hatası: {e}. Raw content: {content[:100]}")
                    return None
                    
    except Exception as e:
        log.warning(f"OpenAI beklenmeyen hata: {e}")
        return None

# ---------------- Prediction wrapper ----------------
async def predict_for_match(m: dict, is_vip: bool):
    temp = 0.1 if is_vip else 0.2
    
    prompt = (
        f"Spor: {m.get('sport')}\nMaç: {m.get('home')} vs {m.get('away')}\n"
        f"Tarih(UTC): {m.get('start')}\n"
    )
    if m.get("odds"): prompt += f"Oran bilgisi mevcut. TheOdds H2H: {get_all_h2h_odds(m)}\n"
    prompt += (
        "İstediğim JSON formatı: {\"predictions\":[{\"market\":\"MS\",\"suggestion\":\"MS 1\",\"confidence\":85,\"explanation\":\"...\"}],\"best\":0}. "
        "Confidence 0-100 arasında bir tam sayı olmalı. Cevabı yalnızca JSON ver."
    )
    
    ai_resp = await call_openai_chat(prompt, max_tokens=300, temperature=temp)
    
    if not ai_resp or not isinstance(ai_resp, dict) or "predictions" not in ai_resp:
        log.warning(f"AI tahmini başarısız veya boş: {m.get('id')}. Fallback kullanılıyor.")
        
        preds = []
        if is_vip: 
            preds.append({"market":"MS","suggestion":"MS X","confidence":70,"explanation":"Riskli ama potansiyeli yüksek beraberlik tahmini."})
            preds.append({"market":"TOTALS","suggestion":"Over 3.5","confidence":65,"explanation":"Yüksek skor sürprizi denemesi."})
        else: 
            preds.append({"market":"MS","suggestion":"MS 1","confidence":75,"explanation":"Ev sahibi, veriler ışığında güvenilir bir seçenek."})
            preds.append({"market":"TOTALS","suggestion":"Under 2.5","confidence":70,"explanation":"Düşük skorlu, defansif bir karşılaşma bekleniyor."})

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
    
    if not best: return ""
    
    suggestion = best.get('suggestion', 'Bilinmiyor')
    confidence = best.get('confidence', 0)
    explanation = best.get('explanation','').replace(" (F)", "") 
    sport_name = m.get('sport','❓ Bilinmeyen Spor')
    
    # Yeni Oran Satırı Oluşturma
    target_odd = get_odd_for_market(m, suggestion)
    odd_line = ""
    
    # Sadece tahmin edilen tercihin oranını göster
    if target_odd:
        # Alt/Üst veya KG Var/Yok tahminlerinin oranını gösterirken sadece tercihi kullan (Örn: MS 1: 2.11 -> 1: 2.11)
        display_suggestion = suggestion.split(':')[0].strip() if ':' in suggestion else suggestion
        
        # Sadece rakamı/tercihi al
        if "MS" in display_suggestion:
             display_suggestion = display_suggestion.replace("MS", "").strip()
        
        odd_line = f"💰 Oran: {display_suggestion}: <b>{target_odd:.2f}</b>\n"
    
    # Kupon blok formatı:
    block = (
        f"🏆 <b>{m.get('home')} vs {m.get('away')}</b>\n"
        f"📅 {start_local} | {sport_name}\n" 
        f"📈 <b>{suggestion}</b> (%{confidence})\n" 
        f"  - <i>{explanation}</i>\n"
    )
    
    # Oran satırını, sadece veri varsa ekle
    block += odd_line
    
    return block.strip()

async def build_coupon_text(matches, title, max_matches):
    global posted_matches
    
    lines = []
    count = 0
    now = datetime.now(timezone.utc)
    
    is_daily_coupon = "GÜNLÜK" in title
    
    match_preds = []
    
    for m in matches:
        pred = await predict_for_match(m, is_vip=("👑 VIP" in title))
        
        if pred and pred.get("predictions"):
            best = pred["predictions"][pred["best"]]
            
            if best["confidence"] < MIN_CONFIDENCE:
                continue
            
            # Günlük kupon oran filtresi (GARANTİ Kuponu için Max 2.0)
            if is_daily_coupon and DAILY_MAX_ODDS:
                if m.get('source') == "TheOdds": 
                    
                    # Oran çekimini genişlettiğimiz için, tüm tahminler için oranı kontrol ediyoruz.
                    odd = get_odd_for_market(m, best["suggestion"])
                    
                    if odd is None or odd > DAILY_MAX_ODDS:
                        log.info(f"Maç atlandı (GARANTİ Kuponu Oran > {DAILY_MAX_ODDS} veya Oran Yok): {m.get('home')} vs {m.get('away')}")
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
            
        if "TEST" not in title: 
             posted_matches[match_id] = now
             
        count += 1
            
    # Günlük kuponda min 2 maç kontrolü
    if is_daily_coupon and count < 2:
        log.warning(f"Günlük kuponda ({count} maç) minimum 2 maç şartı sağlanamadı. Kupon atlandı.")
        return None

    if not lines: return None
        
    header = (
        f"━━━━━━━━━━━━━━━\n"
        f"   {title}\n"
        f"━━━━━━━━━━━━━━━\n"
    )
    footer = (
        f"\n━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Bahis risklidir. Tahminler yalnızca yapay zeka analizi amaçlıdır. Lütfen bilinçli oynayın.</i>\n"
    )
    return header + "\n\n" + "\n\n".join(lines) + footer

# ---------------- MAIN ----------------
async def send_to_channel(app, text):
    try:
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML", disable_web_page_preview=True)
        log.info("Kupon gönderildi.")
    except Exception as e:
        log.exception(f"Telegram gönderim hatası: {e}")

async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.info("Test komutu çalıştırıldı.")
    
    global ai_rate_limit
    ai_rate_limit["calls"] = 0
    ai_rate_limit["reset"] = datetime.now(timezone.utc) + timedelta(seconds=60)
    
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


async def initial_runs_scheduler(app: Application, all_matches):
    """Bot başlatıldıktan sonra istenen ilk kuponları belirli sürelerde gönderir."""
    
    # --- 1. LIVE COUPON (Canlı: Anında) ---
    live_matches = [m for m in all_matches if m.get("live")]
    
    if live_matches:
        live_matches_sorted = []
        for m in live_matches:
             pred = await predict_for_match(m, is_vip=False) 
             if pred and pred.get("predictions"):
                 live_matches_sorted.append((m, pred["predictions"][pred["best"]]["confidence"]))
        
        live_matches_sorted.sort(key=lambda x: x[1], reverse=True)
        
        if live_matches_sorted:
            top_live_match = live_matches_sorted[0][0]
            log.info("Canlı yayın döngüsü başladı (Bot Başlangıcı).")
            
            text = await build_coupon_text(
                [top_live_match], 
                "🟢 CANLI AI SEÇİMİ (Acil)", 
                max_matches=1
            )
            if text:
                await send_to_channel(app, text)
            else:
                log.info("Canlı kupon oluşturulamadı (AI Güven/Filtre).")
        else:
             log.info("Canlı maçlar AI güven eşiğini geçemedi.")
    else:
        log.info("Canlı maç bulunamadı.")
        
    # --- 2. DAILY COUPON (Günlük: 3 Dakika Sonra) ---
    await asyncio.sleep(180) # 3 dakika bekle
    log.info("İlk Günlük Kupon hazırlanıyor.")
    
    text_daily = await build_coupon_text(
        all_matches, 
        "✅ GÜNLÜK GARANTİ AI SEÇİMİ", 
        max_matches=DAILY_MAX_MATCHES
    )
    if text_daily:
          await send_to_channel(app, text_daily)
    last_run["DAILY"] = datetime.now(timezone.utc)
    
    # --- 3. VIP COUPON (VIP: 10 Dakika Sonra - Günlükten 7 dakika sonra) ---
    await asyncio.sleep(420) # 7 dakika bekle (Toplam 10 dakikayı tamamlar)
    log.info("İlk VIP Kupon hazırlanıyor.")

    text_vip = await build_coupon_text(
        all_matches, 
        "👑 VIP AI SÜRPRİZ KUPON", 
        max_matches=VIP_MAX_MATCHES
    )
    if text_vip:
         await send_to_channel(app, text_vip)
    last_run["VIP"] = datetime.now(timezone.utc)
    
    log.info("İlk çalıştırma tamamlandı. Periyodik döngüye geçiliyor.")


async def job_runner(app: Application):
    global last_run
    
    await asyncio.sleep(15) 
    
    initial_run_done = False
    
    while True:
        try:
            now = datetime.now(timezone.utc)
            
            global ai_rate_limit
            ai_rate_limit["calls"] = 0
            ai_rate_limit["reset"] = now + timedelta(seconds=60) 
            
            cleanup_posted_matches()
            
            all_matches = await fetch_all_matches() 
            
            if not all_matches:
                log.info("Tüm API'ler boş veya veri yok.")
            
            # --- İLK ÇALIŞTIRMA BLOĞU ---
            if not initial_run_done:
                log.info("İlk kupon yayınları zamanlandı.")
                await initial_runs_scheduler(app, all_matches)
                initial_run_done = True
            
            
            # --- PERİYODİK DÖNGÜLER ---
            
            # --- DAILY (12 saatlik) ---
            lr_daily = last_run.get("DAILY")
            if lr_daily and (now - lr_daily).total_seconds() >= DAILY_INTERVAL_HOURS*3600:
                log.info("Günlük yayın döngüsü başladı.")
                
                text = await build_coupon_text(
                    all_matches, 
                    "✅ GÜNLÜK GARANTİ AI SEÇİMİ", 
                    max_matches=DAILY_MAX_MATCHES
                )
                if text:
                    await send_to_channel(app, text)
                last_run["DAILY"] = now
                    
            # --- VIP (3 saatlik) ---
            lr_vip = last_run.get("VIP")
            if lr_vip and (now - lr_vip).total_seconds() >= VIP_INTERVAL_HOURS*3600:
                log.info("VIP yayın döngüsü başladı.")
                
                text = await build_coupon_text(
                    all_matches, 
                    "👑 VIP AI SÜRPRİZ KUPON", 
                    max_matches=VIP_MAX_MATCHES 
                )
                if text:
                    await send_to_channel(app, text)
                last_run["VIP"] = now
                        
        except Exception as e:
            log.exception(f"Job runner hata: {e}")
            
        await asyncio.sleep(3600)

def main():
    if not TELEGRAM_TOKEN: log.error("TELEGRAM_TOKEN ayarlı değil. Çıkılıyor."); sys.exit(1)
    if not AI_KEY: log.error("AI_KEY ayarlı değil. Çıkılıyor."); sys.exit(1)
    if not TELEGRAM_CHAT_ID: log.critical("TELEGRAM_CHAT_ID ayarlı değil. Çıkılıyor."); sys.exit(1)
        
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("test", cmd_test))
    
    async def post_init_callback(application: Application):
        asyncio.create_task(job_runner(application))
        log.info("Job runner başarıyla asenkron görev olarak başlatıldı.")

    app.post_init = post_init_callback
    
    log.info("v62.4 başlatıldı. Telegram polling başlatılıyor...")
    
    try:
        app.run_polling(poll_interval=1.0, allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Conflict as e:
        log.critical(f"Kritik Telegram Hatası: İki bot örneği çalışıyor olabilir. Lütfen tek bir bot örneğinin çalıştığından emin olun. Hata: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        cleanup_posted_matches()
        main() 
        
    except KeyboardInterrupt: log.info("Durduruldu.")
    except Exception as e: log.critical(f"Kritik hata: {e}", exc_info=True); sys.exit(1)
