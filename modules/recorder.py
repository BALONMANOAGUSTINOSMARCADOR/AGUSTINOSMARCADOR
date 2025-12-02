import base64
import json
import requests
from datetime import datetime
from pathlib import Path

# Ajusta: propietario/repo
# Si el repo es tu usuario y repo AGUSTINOSMARCADOR, el owner será tu usuario GitHub.
# Vamos a leer el owner del entorno de secrets o de la URL
GITHUB_OWNER = ""  # deja vacío y lo determinaremos en app.py
GITHUB_REPO = ""   # idem

API_URL = "https://api.github.com"

def github_get_file(owner, repo, path, token):
    url = f"{API_URL}/repos/{owner}/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

def github_create_or_update_file(owner, repo, path, content_bytes, message, token):
    """Crea o actualiza un archivo en el repo. content_bytes debe ser bytes."""
    url = f"{API_URL}/repos/{owner}/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    b64 = base64.b64encode(content_bytes).decode('utf-8')
    # comprobar si ya existe para enviar sha
    r_get = requests.get(url, headers=headers)
    if r_get.status_code == 200:
        sha = r_get.json().get("sha")
        payload = {"message": message, "content": b64, "sha": sha}
    else:
        payload = {"message": message, "content": b64}
    r = requests.put(url, headers=headers, data=json.dumps(payload))
    return r.status_code, r.json()

def guardar_partido_github(owner, repo, path_in_repo, partido_obj, token):
    content = json.dumps(partido_obj, ensure_ascii=False, indent=2).encode('utf-8')
    message = f"Guardar partido {partido_obj.get('fecha','')}"
    status, res = github_create_or_update_file(owner, repo, path_in_repo, content, message, token)
    return status, res
