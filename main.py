import telepot
import requests
import schedule
import time
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
import joblib
import os
import warnings

# === UYARILARI KAPAT (Temiz Log) ===
warnings.filterwarnings("ignore")

# === STAKEZONE AYARLARI ===
BOT_TOKEN = os.getenv('BOT_TOKEN', '8393964009:AAGif15CiCgyXs33VFoF-BnaTUVf8xcMKVE')
CHANNEL_ID = '@stakedrip'
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '8393964009:AAFQslrVuWh8ecoLQhguEdF-BUViI37cFFk')
RAPIDAPI_HOST = 'api-nba-v1.p.rapidapi.com'

bot = telepot.Bot(BOT_TOKEN)

# === MODEL (İlk seferde eğit) ===
MODEL_FILE = '/tmp/stakezone_model.pkl'
SCALER_FILE = '/tmp/stakezone_scaler.pkl'

def train_model():
    print("STAKEZONE: Model eğitiliyor...")
    np.random.seed(42
