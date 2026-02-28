import os
import json
from pathlib import Path

PARTIDOS_DIR = Path("data/partidos")

for file_path in PARTIDOS_DIR.glob("*.json"):

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            partido = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Error leyendo {file_path.name}")
            continue

    # Si ya es formato nuevo, saltar
    if "data" in partido:
        print(f"✔ {file_path.name} ya está actualizado")
        continue

    print(f"🔄 Convirtiendo {file_path.name}...")

    nuevo_partido = {
        "fecha": partido.get("fecha"),
        "rival": partido.get("rival", "Rival"),
        "competicion": partido.get("competicion", "Competición"),
        "data": {
            "teamA": "Equipo A",
            "teamB": "Equipo B",
            "scoreA": partido.get("scoreA", 0),
            "scoreB": partido.get("scoreB", 0),
            "events": partido.get("events", []),
            "exclusions": partido.get("exclusions", []),
            "players_stats": {"A": {}, "B": {}},
            "started_at": None,
            "elapsed_before_pause": partido.get("elapsed_seconds", 0),
            "part": 1
        }
    }

    # Guardar copia del antiguo
    backup_path = file_path.with_name(file_path.stem + "_old.json")
    os.rename(file_path, backup_path)

    # Guardar nuevo archivo
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(nuevo_partido, f, indent=4)

    print(f"✅ {file_path.name} convertido correctamente")

print("🎉 Conversión finalizada")
