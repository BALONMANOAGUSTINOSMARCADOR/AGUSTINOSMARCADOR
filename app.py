# =========================================================
# AGUSTINOS MARCADOR — VERSIÓN COMPLETA Y ESTABLE
# =========================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime, json, glob
from PIL import Image
from streamlit_autorefresh import st_autorefresh

from modules import recorder, loader

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="AGUSTINOS MARCADOR",
    layout="wide",
    page_icon="🏐"
)

DEFAULT_EXCLUSION_SECONDS = 120

ZONE_COORDS = {
    1: (0.12, 0.92), 2: (0.5, 0.92), 3: (0.88, 0.92),
    4: (0.12, 0.62), 5: (0.5, 0.62), 6: (0.88, 0.62),
    7: (0.12, 0.32), 8: (0.5, 0.32), 9: (0.88, 0.32),
}

st_autorefresh(interval=1000)

# =========================================================
# ESTADO PERSISTENTE (NO SE BORRA AL RECARGAR)
# =========================================================
if "partido_activo" not in st.session_state:
    st.session_state.partido_activo = False

if "match" not in st.session_state:
    st.session_state.match = {
        "scoreA": 0,
        "scoreB": 0,
        "events": [],
        "exclusions": [],
        "started_at": None,
        "elapsed_before_pause": 0
    }

if "view" not in st.session_state:
    st.session_state.view = None

match = st.session_state.match

# =========================================================
# FUNCIONES
# =========================================================
def iso_now():
    return datetime.datetime.utcnow().isoformat()

def elapsed_seconds():
    if not match["started_at"]:
        return match["elapsed_before_pause"]
    start = datetime.datetime.fromisoformat(match["started_at"])
    return int(match["elapsed_before_pause"] + (datetime.datetime.utcnow() - start).total_seconds())

def start_match():
    if not match["started_at"]:
        match["started_at"] = iso_now()

def pause_match():
    if match["started_at"]:
        match["elapsed_before_pause"] = elapsed_seconds()
        match["started_at"] = None

def reset_match():
    st.session_state.match = {
        "scoreA": 0,
        "scoreB": 0,
        "events": [],
        "exclusions": [],
        "started_at": None,
        "elapsed_before_pause": 0
    }

def add_goal(team, zone, player=None):
    match["events"].append({
        "time": iso_now(),
        "team": team,
        "zone": int(zone),
        "player": player
    })
    match[f"score{team}"] += 1

def add_exclusion(player, team, duration):
    match["exclusions"].append({
        "player": player,
        "team": team,
        "started_at_seconds": elapsed_seconds(),
        "duration": duration
    })

def active_exclusions():
    active = []
    now_sec = elapsed_seconds()

    for ex in match["exclusions"]:
        end_sec = ex["started_at_seconds"] + ex["duration"]
        if now_sec < end_sec:
            remaining = int(end_sec - now_sec)
            ex["remaining"] = remaining
            active.append(ex)

    return active

# =========================================================
# HEADER
# =========================================================
st.title("🏐 AGUSTINOS – Marcador Oficial")

col1, col2 = st.columns(2)
with col1:
    if st.button("▶️ INICIAR PARTIDO", disabled=st.session_state.partido_activo):
        reset_match()
        st.session_state.partido_activo = True
        start_match()

with col2:
    if st.button("⏹️ FINALIZAR PARTIDO", disabled=not st.session_state.partido_activo):
        st.session_state.partido_activo = False
        pause_match()

if not st.session_state.partido_activo:
    st.info("Partido no activo. Los datos permanecen visibles.")

# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================
left, mid, right = st.columns(3)

# -------- MARCADOR --------
with left:
    st.subheader("Marcador")
    st.markdown(f"**Equipo A:** {match['scoreA']}  —  **Equipo B:** {match['scoreB']}")

    zone = st.selectbox("Zona", list(ZONE_COORDS.keys()), index=4)
    player = st.text_input("Jugador")

    st.button("Gol Equipo A", on_click=add_goal, args=("A", zone, player))
    st.button("Gol Equipo B", on_click=add_goal, args=("B", zone, player))

# -------- TIEMPO + EXCLUSIONES --------
with mid:
    st.subheader("Tiempo de partido")
    t = elapsed_seconds()
    st.markdown(f"**{t//60:02d}:{t%60:02d}**")

    st.button("⏸ Pausar", on_click=pause_match)
    st.button("▶ Reanudar", on_click=start_match)

    st.markdown("---")
    st.subheader("Exclusiones")

    with st.form("form_ex"):
        p = st.text_input("Jugador (nº)")
        team = st.selectbox("Equipo", ["A", "B"])
        dur = st.number_input("Duración (seg)", 30, 600, DEFAULT_EXCLUSION_SECONDS)
        if st.form_submit_button("Añadir exclusión"):
            add_exclusion(p, team, dur)

    exs = active_exclusions()

if exs:
    rows = []
    for ex in exs:
        mm = ex["remaining"] // 60
        ss = ex["remaining"] % 60
        rows.append({
            "Jugador": ex["player"],
            "Equipo": ex["team"],
            "Tiempo restante": f"{mm:02d}:{ss:02d}"
        })
    st.table(pd.DataFrame(rows))
else:
    st.write("No hay exclusiones activas.")


# -------- HEATMAP --------
with right:
    st.subheader("Mapa de calor")

    xsA, ysA, xsB, ysB = [], [], [], []
    for ev in match["events"]:
        x, y = ZONE_COORDS[ev["zone"]]
        (xsA if ev["team"] == "A" else xsB).append(x)
        (ysA if ev["team"] == "A" else ysB).append(y)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xsA, y=ysA, mode="markers", name="Equipo A"))
    fig.add_trace(go.Scatter(x=xsB, y=ysB, mode="markers", name="Equipo B"))
    fig.update_xaxes(visible=False, range=[0,1])
    fig.update_yaxes(visible=False, range=[0,1])
    fig.update_layout(height=400)

    st.plotly_chart(fig, use_container_width=True)

# =========================================================
# EVENTOS
# =========================================================
st.markdown("---")
st.subheader("Eventos registrados")
st.dataframe(pd.DataFrame(match["events"]))

# =========================================================
# GUARDAR PARTIDO
# =========================================================
st.markdown("---")
st.subheader("💾 Guardar partido")

rival = st.text_input("Rival")
competicion = st.text_input("Competición")

if st.button("Guardar partido en GitHub"):
    partido = {
        "fecha": iso_now(),
        "rival": rival,
        "competicion": competicion,
        "scoreA": match["scoreA"],
        "scoreB": match["scoreB"],
        "events": match["events"],
        "exclusions": match["exclusions"],
        "elapsed_seconds": elapsed_seconds()
    }

    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"data/partidos/{ts}_Agustinos_vs_{rival}.json"

    status, res = recorder.guardar_partido_github(
        "BALONMANOAGUSTINOSMARCADOR",
        "AGUSTINOSMARCADOR",
        filename,
        partido,
        st.secrets["GITHUB_TOKEN"]
    )

    if status in (200, 201):
        st.success("Partido guardado correctamente")
    else:
        st.error("Error guardando partido")

# =========================================================
# HISTÓRICO
# =========================================================
st.markdown("### Buscar en histórico por RIVAL")

buscar_rival = st.text_input("Nombre del rival a buscar", key="search_rival")

# --- Configuración del repositorio GitHub ---
GITHUB_OWNER = "BALONMANOAGUSTINOSMARCADOR"
GITHUB_REPO = "AGUSTINOSMARCADOR"


if st.button("Buscar partidos"):

    partidos = loader.cargar_partidos_github(
        GITHUB_OWNER,
        GITHUB_REPO,
        "data/partidos",
        GITHUB_TOKEN
    )

    matches = []
    for p in partidos:
        if buscar_rival.strip().lower() in p.get("rival", "").lower():
            matches.append(p)

    st.session_state.search_results = matches
    st.session_state.view = "buscar_partidos"


# ---- MOSTRAR RESULTADOS ----
if st.session_state.view == "buscar_partidos":
    results = st.session_state.search_results or []

    if results:
        st.success(f"Encontrados {len(results)} partidos.")
        for p in results:
            st.write("---")
            st.write(f"📅 Fecha: {p.get('fecha')}")
            st.write(f"🤝 Rival: {p.get('rival')}")
            st.write(f"📊 Resultado: {p.get('scoreA')} - {p.get('scoreB')}")
    else:
        st.warning("No se encontraron partidos.")

