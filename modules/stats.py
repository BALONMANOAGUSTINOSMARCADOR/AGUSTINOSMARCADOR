from collections import defaultdict

def resumen_partido(partido):
    # partido es dict con keys: fecha, events (lista), exclusions...
    resumen = {}
    events = partido.get("events", [])
    resumen["goles_totales"] = len([e for e in events if e.get("type","goal")=="goal"])
    # goles por equipo
    resumen["goles_a"] = sum(1 for e in events if e.get("team")=="A" and e.get("type","goal")=="goal")
    resumen["goles_b"] = sum(1 for e in events if e.get("team")=="B" and e.get("type","goal")=="goal")
    # goles por zona
    zonas = defaultdict(int)
    for e in events:
        if e.get("type","goal")=="goal":
            zonas[e.get("zone",0)] += 1
    resumen["goles_por_zona"] = dict(zonas)
    return resumen

def estadisticas_por_jugador(partido):
    events = partido.get("events", [])
    stats = {}
    for e in events:
        if e.get("player") is None:
            continue
        p = str(e.get("player"))
        if p not in stats:
            stats[p] = {"goles":0, "lanzamientos":0, "exclusiones":0}
        if e.get("type","goal")=="goal":
            stats[p]["goles"] += 1
        # si quieres contar lanzamientos, se puede añadir evento type='shot'
        stats[p]["lanzamientos"] += 1
    # exclusiones
    for ex in partido.get("exclusions", []):
        player = ex.get("player")
        if player:
            stats.setdefault(str(player), {"goles":0,"lanzamientos":0,"exclusiones":0})
            stats[str(player)]["exclusiones"] += 1
    return stats
