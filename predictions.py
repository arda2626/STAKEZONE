from utils import EMOJI, league_to_flag, utcnow
from db import save_prediction
from messages import post_prediction
from config import MIN_ODDS

async def make_prediction(match):
    """
    match = {
        'event_id': str,
        'sport': 'futbol'|'nba'|'tenis',
        'league': str,
        'home': str,
        'away': str,
        'bet': str,
        'odds': float,
        'prob': int
    }
    """
    if match['odds'] < MIN_ODDS: 
        return None
    match['created_at'] = utcnow().isoformat()
    msg_id = await post_prediction(match)
    match['msg_id'] = msg_id
    save_prediction(match)
    return match
