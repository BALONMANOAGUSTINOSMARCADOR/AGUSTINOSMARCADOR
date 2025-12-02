import json
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"
PARTIDOS_FILE = DATA_DIR / "partidos.json"
JUGADORES_FILE = DATA_DIR / "jugadores.json"

def cargar_partidos_local():
    try:
        with open(PARTIDOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def cargar_jugadores():
    try:
        with open(JUGADORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
