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

# modules/loader.py

import requests
import base64
import json

def cargar_partidos_github(owner, repo, folder_path, token):
    """
    Lee todos los archivos JSON de una carpeta del repo GitHub
    y devuelve una lista de partidos (dict).
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{folder_path}"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return []

    files = response.json()
    partidos = []

    for f in files:
        if f["name"].endswith(".json"):
            file_url = f["url"]
            r = requests.get(file_url, headers=headers)

            if r.status_code == 200:
                content = r.json().get("content")
                if content:
                    decoded = base64.b64decode(content).decode("utf-8")
                    try:
                        partido = json.loads(decoded)
                        partidos.append(partido)
                    except Exception:
                        pass

    return partidos

