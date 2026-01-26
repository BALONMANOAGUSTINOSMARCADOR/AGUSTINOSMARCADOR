import requests
import base64
import json


def cargar_partidos_github(owner, repo, folder_path, token):
    """
    Lee todos los archivos JSON de una carpeta del repo GitHub
    y devuelve una lista de partidos (dict).
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{folder_path}?ref=main"

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
        if f.get("type") != "file":
            continue

        if f["name"].endswith(".json"):
            file_url = f["url"]
            r = requests.get(file_url, headers=headers)

            if r.status_code == 200:
                content = r.json().get("content")
                if content:
                    try:
                        decoded = base64.b64decode(content).decode("utf-8")
                        partido = json.loads(decoded)
                        partidos.append(partido)
                    except Exception:
                        pass

    return partidos
