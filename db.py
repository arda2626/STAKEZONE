# db.py
from utils import init_db
from config import DB_PATH

def ensure():
    init_db(DB_PATH)

if __name__ == "__main__":
    ensure()
    print("DB initialized:", DB_PATH)
