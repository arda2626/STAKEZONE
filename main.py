import os
import asyncio
import logging
import json
import random
import sys
import ssl 
import re 
from datetime import datetime, timedelta, timezone

import aiohttp
from aiohttp import ClientError
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import Conflict

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("v62.9.4") 

# ENV KONTROLÜ
AI_KEY = os.getenv("AI_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# API keyler
API_FOOTBALL_KEY = "e35c566553ae8a89972f76ab04c16bd2" 
THE_ODDS_API_KEY = "0180c1cbedb086bdcd526bc0464ee771" 
SPORTSMONKS_KEY = "AirVTC8HLItQs55iaPnxp9TnZ45fdQiK6ecvFFgNavnHSIQxabupFbTrhED7FJ"
ISPORTSAPI_KEY = "7MAJu58UDAlMdWrw" 
FOOTYSTATS_KEY = "test85g57" 
OPENLIGADB_KEY = os.getenv("OPENLIGADB_KEY", "").strip()
FOOTBALL_DATA_KEY = "80a354c67b694ef79c516182ad64aed7" 

# Türkiye zaman dilimi (UTC+3)
TR_TZ = timezone(timedelta(hours=3))
NOW_UTC = datetime.now(timezone.utc)

# Scheduler intervals (saat) 
VIP_INTERVAL_HOURS = 3        
DAILY_INTERVAL_HOURS = 12     
LIVE_INTERVAL_HOURS = 1       
NBA_INTERVAL_HOURS = 24    

# Yeni Anlık Analiz Ayarları
INSTANT_ANALYSIS_INTERVAL_MINUTES = 20 # 20 dakikada bir kontrol
INSTANT_ANALYSIS_MIN_CONFIDENCE = 65 # Minimum %65 kazanma ihtimali (DÜZELTİLDİ: 75'ten 65'e düşürüldü)
INSTANT_ANALYSIS_MAX_ODDS = 10.0 
INSTANT_ANALYSIS_COOLDOWN_MINUTES = 120 # Bir maç tekrar denenmeden önce bekleme süresi

LIVE_STAGGER_INTERVAL_MINUTES = 20 

VIP_MAX_MATCHES = 1           
DAILY_MAX_MATCHES = 3         
LIVE_MAX_MATCHES = 3          
NBA_MAX_MATCHES = 3           

DAILY_MAX_ODDS = 2.0          
MIN_CONFIDENCE = 60           
LIVE_MIN_CONFIDENCE = 80      
NBA_MIN_CONFIDENCE = 85       
NBA_MIN_ODDS = 1.20           
NO_ODDS_MIN_CONFIDENCE = 80   

# Dinamik Maç Başlama Saatleri (Saat cinsinden fark)
MATCH_TIME_HORIZON = {
    "VIP": {"min": 0.5, "max": 168},   # Genişletildi
    "DAILY": {"min": 6, "max": 168},   # Genişletildi
    "NBA": {"min": 0.5, "max": 168},   # Genişletildi
    "INSTANT": {"min": 0.5, "max": 168},
    "LIVE": {"min": -1, "max": 0.5},  
    "TEST": {"min": 0.5, "max": 168},
}

# OpenAI Limit
AI_MAX_CALLS_PER_MINUTE = 5 

# state
posted_matches = {}
last_run = {"DAILY": None, "VIP": None, "LIVE": None, "NBA": None, "INSTANT": None, "LAST_COUPON_POSTED": None} 
ai_rate_limit = {"calls": 0, "reset": NOW_UTC} 

# LİG VE SPOR MODERNİZASYON MAPPING'İ 
SPORT_NAME_MAPPING = {
    "soccer": "⚽ Futbol (Genel)",
    "Football": "⚽ Futbol",
    "Soccer": "⚽ Futbol",
    "Basketball": "🏀 Basketbol",
    "Buz Hokeyi (NHL)": "🏒 Buz Hokeyi (NHL)",
    "Formula 1": "🏎️ Formula 1",
    "basketball_nba": "🏀 NBA", 
    "Bilinmeyen Spor": "❓ Bilinmeyen Spor"
}

LEAGUE_NAME_MAPPING = {
    "English Premier League": "Premier Lig",
    "NBA": "NBA (Basketbol)",
    "basketball_nba": "NBA (Basketbol)",
    "Premier League": "Premier Lig",
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

def within_time_range(iso_ts: str, min_hours: float, max_hours: float):
    """Belirtilen saat aralığında (min_hours ve max_hours) olup olmadığını kontrol eder."""
    if not iso_ts: return False
    try:
        dt = datetime.fromisoformat(str(iso_ts).replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
             dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta_seconds = (dt - now).total_seconds()
        
        min_seconds = min_hours * 3600
        max_seconds = max_hours * 3600
        
        return min_seconds <= delta_seconds <= max_seconds
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
    posted_matches = {mid: dt for mid, dt in posted_matches.items() if (now - dt).total_seconds() < INSTANT_ANALYSIS_COOLDOWN_MINUTES * 60}
    log.info(f"Temizleme sonrası posted_matches boyutu: {len(posted_matches)}")
    
def get_odd_for_market(m: dict, prediction_suggestion: str):
    """
    Tahmin edilen tercihin (MS, Alt/Üst, KG Var/Yok, Handikap) oranını TheOdds verisinden çeker.
    """
    odds_data = m.get("odds")
    if m.get("source") != "TheOdds" and not any(isinstance(odds_data, list) and len(odds_data)>0 for odds_data in m.get("odds", {})):
        if m.get('source') not in ["TheOdds", "BallDontLie"]: 
            return None
        
    odds_data = m.get("odds")
    if not odds_data or not isinstance(odds_data, list):
        return None 
        
    home = m.get('home')
    away = m.get('away')
    
    target_market_key = None
    target_outcome_names = []
    total_value = None
    point_value = None 
    
    # --- 1. Maç Sonucu (H2H) ---
    if any(k in prediction_suggestion for k in ["MS 1", "Ev sahibi kazanır", "H2H 1", "1"]):
        target_market_key = "h2h"
        target_outcome_names = [home, 'Home', '1']
    elif any(k in prediction_suggestion for k in ["MS 2", "Deplasman kazanır", "H2H 2", "2"]):
        target_market_key = "h2h"
        target_outcome_names = [away, 'Away', '2']
    elif any(k in prediction_suggestion for k in ["Beraberlik", "MS 0", "MS X", "X"]):
        target_market_key = "h2h"
        target_outcome_names = ['Draw', 'X', '0']
    
    # --- 2. Toplam Gol/Puan (Totals) ---
    elif prediction_suggestion.startswith("Over") or prediction_suggestion.startswith("Alt") or prediction_suggestion.startswith("Üst"):
        match_total = re.search(r'([0-9]+\.?[0-9]?)', prediction_suggestion)
        total_value = float(match_total.group(1)) if match_total else None
        
        if total_value is not None:
            target_market_key = "totals"
            
            if "Over" in prediction_suggestion or "Üst" in prediction_suggestion:
                target_outcome_names = [f'Over {total_value}', 'Over']
            elif "Under" in prediction_suggestion or "Alt" in prediction_suggestion:
                target_outcome_names = [f'Under {total_value}', 'Under']
            
    # --- 3. KG Var/Yok (BTTS - Sadece Futbol) ---
    elif prediction_suggestion in ["KG Var", "BTTS Yes", "KG Yok", "BTTS No"]:
        if m.get('sport') in ["⚽ Futbol", "⚽ Futbol (Genel)"]:
            target_market_key = "btts" 
            if prediction_suggestion in ["KG Var", "BTTS Yes"]:
                target_outcome_names = ['Yes', 'Var']
            elif prediction_suggestion in ["KG Yok", "BTTS No"]:
                target_outcome_names = ['No', 'Yok']
    
    # --- 4. Handikap (Spreads) ---
    elif "Handikap" in prediction_suggestion or "Spread" in prediction_suggestion:
        target_market_key = "spreads"
        if "1" in prediction_suggestion or home in prediction_suggestion:
            target_outcome_names = [home, 'Home', '1']
        elif "2" in prediction_suggestion or away in prediction_suggestion:
            target_outcome_names = [away, 'Away', '2']
            
        match_point = re.search(r'([+-][0-9]+\.?[0-9]?)', prediction_suggestion)
        if match_point:
            try: point_value = float(match_point.group(1))
            except: point_value = None

    # --- 5. Oyuncu Prop (Player Props - Oran Çekimi Zor) ---
    if "Player Prop" in prediction_suggestion or "Oyuncu" in prediction_suggestion:
        return None


    if not target_market_key:
        return None
        
    prices = []
    for bookmaker in odds_data:
        for market in bookmaker.get("markets", []):
            if market.get("key") == target_market_key:
                for outcome in market.get("outcomes", []):
                    
                    is_match = False
                    
                    if outcome.get("name") in target_outcome_names or any(name in outcome.get("name", "") for name in target_outcome_names):
                        is_match = True
                    
                    if target_market_key == "totals" and total_value is not None:
                         # TheOdds bazen 'point' alanını dize olarak döndürür
                         outcome_point = outcome.get('point')
                         if isinstance(outcome_point, str):
                            try: outcome_point = float(outcome_point)
                            except: outcome_point = None
                            
                         if outcome_point != total_value:
                             is_match = False
                    
                    if target_market_key == "spreads" and point_value is not None:
                         # TheOdds bazen 'point' alanını dize olarak döndürür
                         outcome_point = outcome.get('point')
                         if isinstance(outcome_point, str):
                            try: outcome_point = float(outcome_point)
                            except: outcome_point = None

                         if outcome_point != point_value:
                             is_match = False

                    if is_match and outcome.get("price") is not None:
                        prices.append(outcome.get("price"))
                        
    return max(prices) if prices else None 

# ---------------- API Fetch Fonksiyonları ----------------
async def fetch_football_data(session):
    name = "Football-Data"
    res = []
    now = datetime.now(timezone.utc)
    from_date = now.strftime("%Y-%m-%d")
    to_date = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    url = "https://api.football-data.org/v4/competitions/PL/matches"  # Premier Lig için örnek, diğer ligler eklenebilir
    params = {"dateFrom": from_date, "dateTo": to_date}
    headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
    if not FOOTBALL_DATA_KEY: log.info(f"{name} Key eksik/ayarlı değil. Atlanıyor."); return res
    try:
        async with session.get(url, params=params, headers=headers, timeout=12) as r:
            if r.status == 429: log.error(f"{name} HATA: Hız limiti aşıldı (429)."); return res
            elif r.status == 403: log.error(f"{name} HATA: İzin verilmedi/Yanlış anahtar (403)."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status}."); return res
            data = await r.json()
            items = data.get("matches") or []
            for it in items:
                start = it.get("utcDate") 
                status = it.get("status")
                is_live = status in ("IN_PLAY", "PAUSED")
                if status in ("FINISHED", "SUSPENDED", "POSTPONED") or (status != "SCHEDULED" and not is_live) or (not is_live and not within_time_range(start, 0, 168)): continue 
                res.append({"id": it.get('id'),"home": safe_get(it, "homeTeam", "name"),"away": safe_get(it, "awayTeam", "name"),"start": start,"source": name,"live": is_live,"odds": {},"sport": safe_get(it, "competition", "name") or "Football"})
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except aiohttp.ClientError as e: log.warning(f"{name} Aiohttp hata: {e}"); return res
    except Exception as e: log.warning(f"{name} genel hata: {e}"); return res
    return res

async def fetch_api_football(session):
    name = "API-Football"
    res = []
    url = "https://v3.football.api-sports.io/fixtures"
    end_time = datetime.now(timezone.utc) + timedelta(days=7)  # Genişletildi
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
                is_live = status_short not in ("ns", "tbd", "ft", "ht") and status_short not in ("ns", "tbd")
                if not is_live and not within_time_range(start, 0, 168): continue
                res.append({"id": safe_get(fix,'id'),"home": safe_get(it,"teams","home","name") or "Home","away": safe_get(it,"teams","away","name") or "Away","start": start,"source": name,"live": is_live,"odds": safe_get(it, "odds") or {},"sport": "Football"})
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except aiohttp.ClientError as e: log.warning(f"{name} Aiohttp hata: {e}"); return res
    except Exception as e: log.warning(f"{name} genel hata: {e}"); return res
    return res

async def fetch_the_odds(session):
    name = "TheOdds"
    res = []
    url = "https://api.the-odds-api.com/v4/sports/upcoming/odds" 
    params = {"regions":"eu","markets":"h2h,totals,btts,spreads","oddsFormat":"decimal","dateFormat":"iso","apiKey":THE_ODDS_API_KEY}  # sports parametresi kaldırıldı
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
                    if not start or not within_time_range(start, 0, 168): continue # Genişletildi
                    res.append({"id": it.get('id'),"home": it.get("home_team","Home"),"away": it.get("away_team","Away"),"start": start,"source": name,"live": False,"odds": it.get("bookmakers", []),"sport": sport_key})
            log.info(f"{name} raw:{len(data) if isinstance(data, list) else 0} filtered:{len(res)}")
    except aiohttp.ClientError as e: log.warning(f"{name} Aiohttp hata: {e}"); return res
    except Exception as e: log.warning(f"{name} genel hata: {e}"); return res
    return res

async def fetch_balldontlie(session):
    name = "BallDontLie"
    res = []
    url = "https://api.balldontlie.io/api/v1/games"  # Düzeltilmiş URL
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")  # Genişletildi
    params = {"start_date": today, "end_date": tomorrow}
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
                if not is_live and not within_time_range(full_start, 0, 168): continue # Genişletildi
                res.append({"id": it.get('id'),"home": safe_get(it,"home_team","full_name") or "Home","away": safe_get(it,"visitor_team","full_name") or "Away","start": full_start,"source": name,"live": is_live,"odds": {},"sport": "basketball_nba"})
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except aiohttp.ClientError as e: log.warning(f"{name} Aiohttp hata: {e}"); return res
    except Exception as e: log.warning(f"{name} genel hata: {e}"); return res
    return res

async def fetch_openligadb(session):
    name = "OpenLigaDB"
    res = []
    current_url = "https://api.openligadb.de/getcurrentgroup/bl1"
    try:
        async with session.get(current_url, timeout=12) as r:
            if r.status != 200: 
                log.warning(f"{name} Current group HTTP HATA: {r.status}")
                return res
            data = await r.json()
            group_order_id = data.get("groupOrderID")
            if not group_order_id:
                log.warning(f"{name} Current group not found.")
                return res
            url = f"https://api.openligadb.de/getmatchdata/bl1/2025/{group_order_id}"
            async with session.get(url, timeout=12) as r:
                if r.status != 200: log.warning(f"{name} HTTP HATA: {r.status}."); return res
                data = await r.json()
                items = data if isinstance(data, list) else []
                for it in items:
                    start = it.get("matchDateTimeUTC")
                    is_live = not it.get("matchIsFinished") and it.get("matchResults")
                    if it.get("matchIsFinished") or (not is_live and not within_time_range(start, 0, 168)): continue # Genişletildi
                    res.append({"id": it.get('matchID'),"home": safe_get(it,"team1","teamName"),"away": safe_get(it,"team2","teamName"),"start": start,"source": name,"live": is_live,"odds": {},"sport": "Football (Bundesliga)"})
                log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except aiohttp.ClientError as e: log.warning(f"{name} Aiohttp hata: {e}"); return res
    except Exception as e: log.warning(f"{name} genel hata: {e}"); return res
    return res

async def fetch_sportsmonks(session):
    name = "SportsMonks"
    res = []
    start_date = NOW_UTC.strftime('%Y-%m-%d')
    end_date = (NOW_UTC + timedelta(days=7)).strftime('%Y-%m-%d') # Genişletildi
    url = f"https://api.sportmonks.com/v3/football/fixtures/between/{start_date}/{end_date}"  
    params = {"api_token": SPORTSMONKS_KEY, "include": "odds"}
    if not SPORTSMONKS_KEY: log.info(f"{name} Key eksik, atlanıyor."); return res
    try:
        async with session.get(url, params=params, timeout=12) as r:
            if r.status == 429 or r.status == 403: log.error(f"{name} HATA: Limit/Erişim sorunu ({r.status})."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status} (Kısıtlı)."); return res
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("starting_at")
                if not within_time_range(start, 0, 168): continue
                res.append({"id": it.get('id'),"home": it.get("home_team_name"),"away": it.get("away_team_name"),"start": start,"source": name,"live": False,"odds": it.get("odds", {}),"sport": "Football"})
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except aiohttp.ClientError as e: log.warning(f"{name} Aiohttp hata: {e}"); return res
    except Exception as e: log.warning(f"{name} genel hata: {e}"); return res
    return res

async def fetch_footystats(session):
    name = "FootyStats"
    res = []
    url = "https://api.footystats.org/upcoming-matches"  # Orijinale döndürüldü
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
                if it.get("status") != "upcoming" or not within_time_range(start, 0, 168): continue # Genişletildi
                res.append({"id": it.get('id'),"home": it.get("home_name"),"away": it.get("away_name"),"start": start,"source": name,"live": False,"odds": {},"sport": "Football"})
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except aiohttp.ClientError as e: log.warning(f"{name} Aiohttp hata: {e}"); return res
    except Exception as e: log.warning(f"{name} genel hata: {e}"); return res
    return res

async def fetch_isports(session):
    name = "iSportsAPI"
    res = []
    url = "https://api.isportsapi.com/sport/football/schedule"  
    params = {"api_key": ISPORTSAPI_KEY, "date": NOW_UTC.strftime("%Y-%m-%d")}
    if not ISPORTSAPI_KEY: log.info(f"{name} Key eksik, atlanıyor."); return res
    try:
        # SSL ignore eklendi
        async with session.get(url, params=params, timeout=12, ssl=False) as r: 
            if r.status == 429 or r.status == 403: log.error(f"{name} HATA: Limit/Erişim sorunu ({r.status})."); return res
            elif r.status != 200: log.warning(f"{name} HTTP HATA: {r.status} (Kısıtlı)."); return res
            data = await r.json()
            items = data.get("data") or []
            for it in items:
                start = it.get("matchTime") 
                match_status = it.get("matchStatus")
                is_live = match_status != 0 and match_status != -1
                if match_status == -1 or (not is_live and not within_time_range(start, 0, 168)): continue # Genişletildi
                res.append({"id": it.get('matchId'),"home": it.get("homeTeamName"),"away": it.get("awayTeamName"),"start": start,"source": name,"live": is_live,"odds": it.get("odds", {}),"sport": it.get("sportType", "Bilinmeyen")})
            log.info(f"{name} raw:{len(items)} filtered:{len(res)}")
    except aiohttp.ClientError as e: log.warning(f"{name} Aiohttp hata: {e}"); return res
    except Exception as e: log.warning(f"{name} genel hata: {e}"); return res
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
                if not within_time_range(start, 0, 168): continue # Genişletildi
                res.append({"id": race.get('raceId'),"home": race_name,"away": race.get("Circuit", {}).get("circuitName"),"start": start,"source": name,"live": False,"odds": {},"sport": "Formula 1"})
            log.info(f"{name} raw:{len(race_table)} filtered:{len(res)}")
    except aiohttp.ClientError as e: log.warning(f"{name} Aiohttp hata: {e}"); return res
    except Exception as e: log.warning(f"{name} genel hata: {e}"); return res
    return res

async def fetch_nhl(session):
    name = "NHL Stats"
    res = []
    today = datetime.now(TR_TZ).strftime("%Y-%m-%d")
    end_date = (datetime.now(TR_TZ) + timedelta(days=7)).strftime("%Y-%m-%d") # Genişletildi
    url = f"https://statsapi.web.nhl.com/api/v1/schedule?startDate={today}&endDate={end_date}"
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
                    if status_detail == "Final" or (not is_live and not within_time_range(start_time, 0, 168)): continue # Genişletildi
                    home_team = safe_get(game, "teams", "home", "team", "name")
                    away_team = safe_get(game, "teams", "away", "team", "name")
                    res.append({"id": game_pk,"home": home_team,"away": away_team,"start": start_time,"source": name,"live": is_live,"odds": {},"sport": "Buz Hokeyi (NHL)"})
            log.info(f"{name} filtered:{len(res)}")
    except aiohttp.ClientError as e: log.warning(f"{name} Aiohttp hata: {e}"); return res
    except Exception as e: log.warning(f"{name} genel hata: {e}"); return res
    return res

async def fetch_all_matches():
    # DÜZELTİLDİ: SSL doğrulamasını atlamak için connector eklendi (API bağlantı sorununu çözmek için)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        tasks = [
            fetch_football_data(session), 
            fetch_api_football(session), 
            fetch_the_odds(session),
            fetch_openligadb(session),
            fetch_sportsmonks(session),
            fetch_footystats(session),
            fetch_balldontlie(session), 
            fetch_isports(session),
            fetch_ergast(session),
            fetch_nhl(session),
        ]
        
        # Güçlendirilmiş toplu çağrı
        results = await asyncio.gather(*tasks, return_exceptions=True) 
    
    all_matches = []
    for r in results:
        # İstisna yakalama eklendi. API'den hata gelirse, görevi atla.
        if isinstance(r, Exception): 
            log.warning(f"fetch task exception: {r}"); continue
        all_matches.extend(r or [])
        
    normalized = []
    odds_map = {}
    
    # Odds Map oluşturma (TheOdds)
    for m in all_matches:
        if m.get('source') == "TheOdds":
            key = (m.get('home'), m.get('away'), m.get('start')[:10], m.get('sport'))
            odds_map[key] = m.get('odds', {})
            
    # Maçları normalize etme ve Odds birleştirme
    for m in all_matches:
        start = m.get("start") or m.get("date") or ""
        if isinstance(start, (int, float)):
            try: start = datetime.fromtimestamp(int(start), tz=timezone.utc).isoformat().replace('+00:00', 'Z')
            except: start = ""
        
        match_id_base = m.get("id") or hash(json.dumps(m, default=str))
        final_id = f"{m.get('source')}_{match_id_base}"
        
        sport_key = m.get("sport", "Bilinmeyen Spor")
        normalized_sport = LEAGUE_NAME_MAPPING.get(sport_key, sport_key)
        normalized_sport = SPORT_NAME_MAPPING.get(normalized_sport, normalized_sport)
        
        m_odds = m.get('odds', {})
        if not m_odds:
            key = (m.get('home'), m.get('away'), start[:10], sport_key)
            m_odds = odds_map.get(key, {})
            m['odds'] = m_odds
            
        normalized.append({
            "id": final_id,
            "home": m.get("home"),
            "away": m.get("away"),
            "start": start,
            "source": m.get("source"),
            "live": bool(m.get("live")),
            "odds": m_odds,
            "sport": normalized_sport
        })
        
    # Tekrarlanan maçları ayıklama
    seen = set()
    final = []
    for m in normalized:
        key = (m.get("home"), m.get("away"), m.get("start")) 
        if key in seen: continue
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
    
    # Hızlı kontrol
    if ai_rate_limit["calls"] >= AI_MAX_CALLS_PER_MINUTE: 
        log.warning(f"OpenAI lokal kısıtlama ({AI_MAX_CALLS_PER_MINUTE} RPM limitine ulaşıldı). Atlanıyor.")
        return None 
        
    ai_rate_limit["calls"] += 1 
    
    await asyncio.sleep(3) 
    
    headers = {"Authorization": f"Bearer {AI_KEY}", "Content-Type": "application/json"}
    market_list = "MS, Alt/Üst (Over/Under), Handikap (Spread), KG Var/Yok (Sadece futbol için), Yarı Sonucu, Oyuncu İstatistikleri (Player Props: Puan/Asist/Ribaund)"

    payload = {
        "model": MODEL,
        "messages":[
            {"role":"system","content":f"Sen Türkçe konuşan, yüksek güvenilirlikte tahminler yapan, bir spor yorumcusu ve kumarbaz zekasına sahip profesyonel bir analistsin. Piyasa hareketlerini, risk ve ödülü değerlendir. Tüm popüler marketler ({market_list}) için en güçlü 1 veya 2 tahminini yap. Tahminlerinin 70'ten (VIP/CANLI/NBA için 85'ten, Oransız maçlar için min 80'den) düşük olmamasına özen göster. Cevabı sadece belirtilen JSON formatında ver. Başka hiçbir açıklayıcı metin kullanma. Confidence 0-100 arasında tam sayı olmalı. Alt/Üst tahminlerini 'Under 2.5' veya 'Over 3.5' formatında yap. Oyuncu prop tahminlerini 'Oyuncu: LeBron James, Tercih: Over 25.5 Sayı' formatında yap."},
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
async def predict_for_match(m: dict, coupon_type: str):
    is_high_conf = coupon_type in ["VIP", "LIVE", "NBA"]
    is_instant_analysis = coupon_type == "INSTANT"
    temp = 0.1 if is_high_conf or is_instant_analysis else 0.2
    
    prompt = (
        f"Spor: {m.get('sport')}\nMaç: {m.get('home')} vs {m.get('away')}\n"
        f"Tarih(UTC): {m.get('start')}\n"
    )
    
    prompt += (
        "İstediğim JSON formatı: {\"predictions\":[{\"market\":\"MS\",\"suggestion\":\"MS 1\",\"confidence\":85,\"explanation\":\"...\"}],\"best\":0}. "
        "Confidence 0-100 arasında bir tam sayı olmalı. Cevabı yalnızca JSON ver."
    )
    
    ai_resp = await call_openai_chat(prompt, max_tokens=300, temperature=temp)
    
    # Fallback kısmı
    if not ai_resp or not isinstance(ai_resp, dict) or "predictions" not in ai_resp:
        log.warning(f"AI tahmini başarısız veya boş: {m.get('id')}. Fallback kullanılıyor.")
        
        preds = []
        if is_high_conf or is_instant_analysis: 
            preds.append({"market":"MS","suggestion":"MS 1 (Riskli Fallback)","confidence":75,"explanation":"AI çağrısı başarısız olduğu için yüksek güvenilirliğe sahip varsayılan fallback."})
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
def format_match_block(m, pred, coupon_type):
    start_local = to_local_str(m.get("start") or "")
    best = pred["predictions"][pred["best"]] if pred["predictions"] else None
    
    if not best: return ""
    
    suggestion = best.get('suggestion', 'Bilinmiyor')
    confidence = best.get('confidence', 0)
    explanation = best.get('explanation','').replace(" (F)", "") 
    sport_name = m.get('sport','❓ Bilinmeyen Spor')
    
    is_nba_coupon = coupon_type == "NBA"
    
    target_odd = get_odd_for_market(m, suggestion)
    odd_line = ""
    
    if target_odd:
        display_suggestion = suggestion.split(':')[0].strip() if ':' in suggestion and not is_nba_coupon else suggestion
        if "MS" in display_suggestion and coupon_type not in ["INSTANT", "LIVE"]:
             display_suggestion = display_suggestion.replace("MS", "").strip()
        
        odd_line = f"💰 Oran: {display_suggestion}: <b>{target_odd:.2f}</b>"
    
    block = (
        f"🏅 <b>{m.get('home')} vs {m.get('away')}</b>\n"
        f"  - 📅 {start_local} | {sport_name}\n" 
        f"  - 📈 Seçim: <b>{suggestion}</b> (%{confidence})\n" 
        f"  - 💡 Analiz: <i>{explanation}</i>\n"
    )
    
    if odd_line:
         block += f"  - {odd_line}\n"
    
    return block.strip()

async def build_coupon_text(matches: list, title: str, max_matches: int, coupon_type: str):
    global posted_matches
    
    lines = []
    count = 0
    now = datetime.now(timezone.utc)
    
    # Maçları kupon tipine göre filtrele
    time_bounds = MATCH_TIME_HORIZON.get(coupon_type, {"min": 0, "max": 72})
    
    filtered_matches = []
    
    for m in matches:
        if m.get("live") and coupon_type != "LIVE": continue
        if not m.get("live") and coupon_type == "LIVE": continue
        
        # Dinamik zaman aralığı kontrolü
        if within_time_range(m.get("start"), time_bounds["min"], time_bounds["max"]):
            filtered_matches.append(m)
        else:
             log.debug(f"Maç zaman aralığına uymadı ({coupon_type}): {m.get('home')} - {m.get('start')}")
             
    if coupon_type == "NBA":
        filtered_matches = [m for m in filtered_matches if m.get("sport") == "🏀 NBA"]
        
    # Güven ve Oran limitlerini belirle
    is_daily_coupon = coupon_type == "DAILY"
    is_nba_coupon = coupon_type == "NBA"
    is_instant_coupon = coupon_type == "INSTANT"
    
    if is_instant_coupon:
        min_conf = INSTANT_ANALYSIS_MIN_CONFIDENCE
        min_odd = None 
        max_odd = INSTANT_ANALYSIS_MAX_ODDS
    elif is_nba_coupon:
        min_conf = NBA_MIN_CONFIDENCE
        min_odd = NBA_MIN_ODDS
        max_odd = None
    elif coupon_type == "LIVE":
        min_conf = LIVE_MIN_CONFIDENCE
        min_odd = None
        max_odd = None
    else: # DAILY, VIP, TEST
        min_conf = MIN_CONFIDENCE
        min_odd = None 
        max_odd = DAILY_MAX_ODDS if is_daily_coupon else None
    
    match_preds = []
    
    for m in filtered_matches: 
        
        # Cooldown kontrolü (Canlı hariç)
        match_id = m.get("id")
        if coupon_type not in ["LIVE", "TEST"]: 
             if match_id in posted_matches and (now - posted_matches[match_id]).total_seconds() < INSTANT_ANALYSIS_COOLDOWN_MINUTES * 60:
                log.info(f"Maç atlandı (zaten yayınlandı ve cooldown: {INSTANT_ANALYSIS_COOLDOWN_MINUTES}dk): {m.get('home')} vs {m.get('away')}")
                continue
                
        pred = await predict_for_match(m, coupon_type)
        
        if pred and pred.get("predictions"):
            best = pred["predictions"][pred["best"]]
            
            odd = get_odd_for_market(m, best["suggestion"])
            
            if odd is None and not is_instant_coupon:
                if best["confidence"] < NO_ODDS_MIN_CONFIDENCE:
                    log.info(f"Maç atlandı (Oran Yok & Güven < %{NO_ODDS_MIN_CONFIDENCE}): {m.get('home')} vs {m.get('away')}")
                    continue
            
            elif best["confidence"] < min_conf:
                 log.info(f"Maç atlandı (Güven < %{min_conf}): {m.get('home')} vs {m.get('away')}")
                 continue
                 
            if odd is not None:
                if min_odd and odd < min_odd:
                    log.info(f"Maç atlandı (Oran < {min_odd}): {m.get('home')} vs {m.get('away')}")
                    continue
                    
                if max_odd and odd > max_odd:
                    log.info(f"Maç atlandı (Oran > {max_odd}): {m.get('home')} vs {m.get('away')}")
                    continue
                
            match_preds.append((m, pred, best["confidence"]))

    match_preds.sort(key=lambda x: x[2], reverse=True)
    
    for m, pred, confidence in match_preds:
        if count >= max_matches: break
            
        match_id = m.get("id")
        
        lines.append(format_match_block(m, pred, coupon_type))
            
        if "TEST" not in title and coupon_type != "LIVE":
             posted_matches[match_id] = now
             
        count += 1
            
    if not is_instant_coupon and (is_daily_coupon or is_nba_coupon) and count < 2:
        log.warning(f"{coupon_type} kuponunda ({count} maç) minimum 2 maç şartı sağlanamadı. Kupon atlandı.")
        return None

    if not lines: return None
        
    # Kupon Başlığı Formatı
    header = (
        f"➖➖➖ 💎 AI Betting Bot 💎 ➖➖➖\n"
        f"   🏆 {title} 🏆\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
    )
    footer = (
        f"\n➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"⚠️ <i>Bahis risklidir. Tahminler yalnızca yapay zeka analizi amaçlıdır. Lütfen bilinçli oynayın.</i>\n"
    )
    return header + "\n\n" + "\n\n".join(lines) + footer

async def post_coupon_after_delay(app, text, delay_minutes):
    """Belirtilen gecikmeden sonra kuponu Telegram'a gönderir."""
    if delay_minutes > 0:
        await asyncio.sleep(delay_minutes * 60)
    await send_to_channel(app, text)
    global last_run
    last_run["LAST_COUPON_POSTED"] = datetime.now(timezone.utc)


# ---------------- INSTANT ANALYSIS JOB (YENİ) ----------------
async def run_instant_analysis_job(app: Application, all_matches: list):
    global last_run
    log.info(f"Anlık Analiz döngüsü başlatılıyor. (Min %{INSTANT_ANALYSIS_MIN_CONFIDENCE} güven aranıyor)")
    
    # Dinamik filtreleme artık build_coupon_text içinde yapılıyor
    text = await build_coupon_text(
        all_matches, 
        "⚡ ANLIK AI ANALİZ (Continuity Bet)", 
        max_matches=1,
        coupon_type="INSTANT"
    )
    
    if text:
        await send_to_channel(app, text)
        last_run["LAST_COUPON_POSTED"] = datetime.now(timezone.utc)
    else:
        log.info(f"Anlık Analiz kuponu oluşturulamadı (Filtreler veya Min %{INSTANT_ANALYSIS_MIN_CONFIDENCE} güven).")
        
    last_run["INSTANT"] = datetime.now(timezone.utc)


# ---------------- NBA COUPON JOB ----------------
async def run_nba_coupon_job(app: Application, all_matches: list):
    global last_run
    log.info(f"NBA kupon döngüsü başlatılıyor. (Min %{NBA_MIN_CONFIDENCE} güven, Min {NBA_MIN_ODDS} oran aranıyor)")
    
    # Dinamik filtreleme artık build_coupon_text içinde yapılıyor
    text = await build_coupon_text(
        all_matches, 
        "🏀 NBA GOLDEN BET AI SEÇİMİ", 
        max_matches=NBA_MAX_MATCHES,
        coupon_type="NBA"
    )
    
    if text:
        await send_to_channel(app, text)
        last_run["LAST_COUPON_POSTED"] = datetime.now(timezone.utc)
    else:
        log.info("NBA kuponu oluşturulamadı (Filtreler veya Min Maç Sayısı).")
        
    last_run["NBA"] = datetime.now(timezone.utc)

# ---------------- LIVE COUPON JOB ----------------
async def run_live_coupon_job(app: Application, all_matches: list):
    global last_run
    log.info(f"Canlı kupon döngüsü başlatılıyor. (Min %{LIVE_MIN_CONFIDENCE} güven aranıyor)")
    
    live_matches = [m for m in all_matches if m.get("live")]
    if not live_matches:
        log.info("Canlı kupon için uygun maç bulunamadı.")
        last_run["LIVE"] = datetime.now(timezone.utc)
        return

    match_preds = []
    
    # Canlı maçlar için filtreleme ve tahmin yapma (hızlı olması için)
    for m in live_matches:
        pred = await predict_for_match(m, coupon_type="LIVE") 
        
        if pred and pred.get("predictions"):
            best = pred["predictions"][pred["best"]]
            
            if best["confidence"] >= LIVE_MIN_CONFIDENCE:
                match_preds.append((m, pred, best["confidence"]))
    
    if not match_preds:
        log.info(f"Canlı maçlar arasında min %{LIVE_MIN_CONFIDENCE} güven eşiğini geçen bulunamadı.")
        last_run["LIVE"] = datetime.now(timezone.utc)
        return

    match_preds.sort(key=lambda x: x[2], reverse=True)
    selected_matches = match_preds[:LIVE_MAX_MATCHES]
    
    log.info(f"Canlı kupon için {len(selected_matches)} adet maç seçildi. Kademeli dağıtım ({LIVE_STAGGER_INTERVAL_MINUTES}dk arayla) planlanıyor.")
    
    for i, (m, pred, confidence) in enumerate(selected_matches):
        delay = i * LIVE_STAGGER_INTERVAL_MINUTES
        title = f"🟢 CANLI AI SEÇİMİ (Güven: %{confidence})"
        
        # Sadece seçilen maçı tek bir kupon metnine dönüştürmek için format_match_block kullanıldı
        match_block = format_match_block(m, pred, coupon_type="LIVE")
        
        if match_block:
            text = (
                f"➖➖➖ 💎 AI Betting Bot 💎 ➖➖➖\n"
                f"   🏆 {title} 🏆\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖\n\n"
                f"{match_block}\n\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"⚠️ <i>Bahis risklidir. Lütfen bilinçli oynayın.</i>\n"
            )

            asyncio.create_task(post_coupon_after_delay(app, text, delay))
            log.info(f"Canlı maç '{m.get('home')}' için {delay} dakika gecikmeli gönderim planlandı.")
        
    last_run["LIVE"] = datetime.now(timezone.utc)


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
        await update.message.reply_text("Maç bulunamadı (Filtreler genişletilmelidir).")
        return
        
    text = await build_coupon_text(
        matches, 
        "🚨 TEST AI KUPON (MANUEL)", 
        max_matches=5,
        coupon_type="TEST"
    )
    
    if text:
        await update.message.reply_text(text, parse_mode="HTML") 
    else:
        await update.message.reply_text("Kupon oluşturulamadı (Filtrelere takılmış olabilir).")


async def initial_runs_scheduler(app: Application, all_matches):
    """Bot başlatıldıktan sonra istenen ilk kuponları belirli sürelerde gönderir."""
    
    global last_run
    
    # --- 1. LIVE COUPON (Anında) ---
    await asyncio.sleep(5)
    log.info("İlk Canlı Kupon çalıştırması hemen başlatılıyor.")
    await run_live_coupon_job(app, all_matches)
    
    # --- 2. INSTANT ANALYSIS COUPON (Anında Çalışsın) ---
    await asyncio.sleep(60)
    log.info("İlk Anlık Analiz Kuponu hazırlanıyor.")
    await run_instant_analysis_job(app, all_matches)

    # --- 3. NBA COUPON (NBA: 2 Dakika Sonra) ---
    await asyncio.sleep(60)
    log.info("İlk NBA Kuponu hazırlanıyor.")
    await run_nba_coupon_job(app, all_matches)

    # --- 4. DAILY COUPON (Günlük: 4 Dakika Sonra) ---
    await asyncio.sleep(120) 
    log.info("İlk Günlük Kupon hazırlanıyor.")
    
    text_daily = await build_coupon_text(
        all_matches, 
        "✅ GÜNLÜK GARANTİ AI SEÇİMİ", 
        max_matches=DAILY_MAX_MATCHES,
        coupon_type="DAILY"
    )
    if text_daily:
          await send_to_channel(app, text_daily)
          last_run["LAST_COUPON_POSTED"] = datetime.now(timezone.utc)
    last_run["DAILY"] = datetime.now(timezone.utc)
    
    # --- 5. VIP COUPON (VIP: 11 Dakika Sonra) ---
    await asyncio.sleep(240) 
    log.info("İlk VIP Kupon hazırlanıyor.")

    text_vip = await build_coupon_text(
        all_matches, 
        "👑 VIP AI SÜRPRİZ KUPON", 
        max_matches=VIP_MAX_MATCHES,
        coupon_type="VIP"
    )
    if text_vip:
         await send_to_channel(app, text_vip)
         last_run["LAST_COUPON_POSTED"] = datetime.now(timezone.utc)
    last_run["VIP"] = datetime.now(timezone.utc)
    
    log.info("İlk çalıştırma tamamlandı. Periyodik döngüye geçiliyor.")


async def job_runner(app: Application):
    # Global değişken deklarasyonları fonksiyonun en başında
    global last_run 
    global ai_rate_limit
    
    await asyncio.sleep(15) 
    
    initial_run_done = False
    
    while True:
        try:
            now = datetime.now(timezone.utc)
            
            # AI Rate Limit sıfırlama (Her döngü başında)
            ai_rate_limit["calls"] = 0
            ai_rate_limit["reset"] = now + timedelta(seconds=60) 
            
            cleanup_posted_matches()
            
            all_matches = await fetch_all_matches() 
            
            if not all_matches:
                log.info("Tüm API'ler boş veya veri yok.")
            
            # --- İLK ÇALIŞTIRMA BLOĞU ---
            if not initial_run_done:
                log.info("İlk kupon yayınları zamanlandı.")
                # İlk çalıştırmada job_runner asenkron bir görev olarak başlatıldığı için,
                # initial_runs_scheduler'ı çağırdığımızda, görevler zamanlanacaktır.
                await initial_runs_scheduler(app, all_matches)
                initial_run_done = True
            
            
            # --- PERİYODİK DÖNGÜLER ---
            
            # --- LIVE (1 saatlik) ---
            lr_live = last_run.get("LIVE")
            if lr_live and (now - lr_live).total_seconds() >= LIVE_INTERVAL_HOURS*3600:
                await run_live_coupon_job(app, all_matches)
            
            # --- DAILY (12 saatlik) ---
            lr_daily = last_run.get("DAILY")
            if lr_daily and (now - lr_daily).total_seconds() >= DAILY_INTERVAL_HOURS*3600:
                log.info("Günlük yayın döngüsü başladı.")
                
                text = await build_coupon_text(
                    all_matches, 
                    "✅ GÜNLÜK GARANTİ AI SEÇİMİ", 
                    max_matches=DAILY_MAX_MATCHES,
                    coupon_type="DAILY"
                )
                if text:
                    await send_to_channel(app, text)
                    last_run["LAST_COUPON_POSTED"] = datetime.now(timezone.utc)
                last_run["DAILY"] = now
                    
            # --- VIP (3 saatlik) ---
            lr_vip = last_run.get("VIP")
            if lr_vip and (now - lr_vip).total_seconds() >= VIP_INTERVAL_HOURS*3600:
                log.info("VIP yayın döngüsü başladı.")
                
                text = await build_coupon_text(
                    all_matches, 
                    "👑 VIP AI SÜRPRİZ KUPON", 
                    max_matches=VIP_MAX_MATCHES,
                    coupon_type="VIP"
                )
                if text:
                    await send_to_channel(app, text)
                    last_run["LAST_COUPON_POSTED"] = datetime.now(timezone.utc)
                last_run["VIP"] = now
            
            # --- NBA (24 saatlik) ---
            lr_nba = last_run.get("NBA")
            if lr_nba and (now - lr_nba).total_seconds() >= NBA_INTERVAL_HOURS*3600:
                await run_nba_coupon_job(app, all_matches)
            
            # --- INSTANT ANALYSIS (20 dakikada bir kontrol) ---
            lr_instant = last_run.get("INSTANT")
            
            last_post_time = last_run.get("LAST_COUPON_POSTED")
            is_gap = last_post_time is None or (now - last_post_time).total_seconds() >= 1200 # 20 dakika
            
            is_instant_due = lr_instant is None or (now - lr_instant).total_seconds() >= INSTANT_ANALYSIS_INTERVAL_MINUTES*60
            
            if is_gap and is_instant_due:
                log.info("Boşluk algılandı. Anlık Analiz döngüsü başlatılıyor.")
                await run_instant_analysis_job(app, all_matches)
                        
        except Exception as e:
            log.exception(f"Job runner hata: {e}")
            
        await asyncio.sleep(60) # Her dakika kontrol et

async def run_app():
    if not TELEGRAM_TOKEN: log.error("TELEGRAM_TOKEN ayarlı değil. Çıkılıyor."); sys.exit(1)
    if not AI_KEY: log.error("AI_KEY ayarlı değil. Çıkılıyor."); sys.exit(1)
    if not TELEGRAM_CHAT_ID: log.critical("TELEGRAM_CHAT_ID ayarlı değil. Çıkılıyor."); sys.exit(1)
        
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("test", cmd_test))
    async def post_init_callback(application: Application):
        # post_init, initialize tamamlandıktan sonra çağrılır.
        asyncio.create_task(job_runner(application))
        log.info("Job runner başarıyla asenkron görev olarak başlatıldı.")

    app.post_init = post_init_callback
    
    log.info("v62.9.4 (Kritik Hatalar Giderildi) başlatılıyor.")
    
    log.info("Telegram polling başlatılıyor...")
    
    # ✅ KRİTİK DÜZELTME: stop_signals=None eklendi.
    # Bu, 'event loop already running' ve 'Cannot close a running event loop' hatalarını önler.
    await app.run_polling(
        allowed_updates=Update.ALL_TYPES, 
        drop_pending_updates=True, 
        stop_signals=None 
    ) 

if __name__ == "__main__":
    try:
        cleanup_posted_matches()
        # Dış asyncio döngüsü
        asyncio.run(run_app())
    except KeyboardInterrupt:
        log.info("Durduruldu.")
    except Exception as e:
        log.critical(f"Kritik hata: {e}", exc_info=True)
        sys.exit(1)

