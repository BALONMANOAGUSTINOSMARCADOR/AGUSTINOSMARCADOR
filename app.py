# app.py — AGUSTINOS MARCADOR (VERSIÓN ESTABLE)

import streamlit as st
from PIL import Image
import pandas as pd
import plotly.graph_objects as go
import datetime, json
from streamlit_autorefresh import st_autorefresh

# =========================
# CONFIG INICIAL
# =========================
st.set_page_config(
    page_title="AGUSTINOS MARCADOR",
    layout="wide",
    page_icon="🏐"
)

# =========================
# ESTADO GLOBAL
# =========================
if "partido_activo" not in st.session_state:
    st.session_state.partido_activo = False

if "match" not in st.session_state:
    st.session_state.match = {
        "scoreA": 0,
        "scoreB": 0,
        "events": [],
        "exclusions": [],
        "started_at": None,
        "paused_at": None,
        "elapsed_before_pause": 0.0
    }

match = st.session_state.match
PARTIDO_ACTIVO = st.session_state.partido_activo

# refresco cada segundo
st_autorefresh(interval=1000)

# =========================
# CONFIGURACIÓN
# =========================
DEFAULT_EXCLUSION_SECONDS = 120

ZONE_COORDS = {
    1: (0.12, 0.92), 2: (0.5, 0.92), 3: (0.88, 0.92),
    4: (0.12, 0.62), 5: (0.5, 0.62), 6: (0.88, 0.62),
    7: (0.12, 0.32), 8: (0.5, 0.32), 9: (0.88, 0.32),
}

# =========================
# FUNCIONES
# =========================
def iso_now():
    return datetime.datetime.utcnow().isoformat()

def add_goal(team, zone, player=None):
    match["events"].append({
        "time": iso_now(),
        "team": team,
        "zone": int(zone),
        "player": player
    })
    if team == "A":
        match["scoreA"] += 1
    else:
        match["scoreB"] += 1

def now_elapsed_seconds():
    if not match["started_at"]:
        return int(match["elapsed_before_pause"])
    start = datetime.datetime.fromisoformat(match["started_at"])
    return int(match["elapsed_before_pause"] + (datetime.datetime.utcnow() - start).total_seconds())

def start_match():
    match["started_at"] = iso_now()
    match["paused_at"] = None

def pause_match():
    if match["started_at"]:
        elapsed = now_elapsed_seconds()
        match["elapsed_before_pause"] = elapsed
        match["started_at"] = None

def reset_match():
    match.update({
        "scoreA": 0,
        "scoreB": 0,
        "events": [],
        "exclusions": [],
        "started_at": None,
        "paused_at": None,
        "elapsed_before_pause": 0.0
    })

# =========================
# HEADER
# =========================
st.title("🏐 AGUSTINOS – Marcador y Heatmap")

col_start, col_end = st.columns(2)

with col_start:
    if st.button("▶️ INICIAR PARTIDO", disabled=PARTIDO_ACTIVO):
        reset_match()
        st.session_state.partido_activo = True
        start_match()

with col_end:
    if st.button("⏹️ FINALIZAR PARTIDO", disabled=not PARTIDO_ACTIVO):
        st.session_state.partido_activo = False
        pause_match()

if not PARTIDO_ACTIVO:
    st.info("No hay partido activo. Pulsa ▶️ INICIAR PARTIDO para comenzar.")

# =========================
# INTERFAZ PRINCIPAL
# =========================
left, mid, right = st.columns(3)

# -------- MARCADOR --------
with left:
    st.subheader("Marcador")
    st.markdown(f"**Equipo A:** {match['scoreA']}  —  **Equipo B:** {match['scoreB']}")

    zone = st.selectbox("Zona (1–9)", list(ZONE_COORDS.keys()), index=4)
    player = st.text_input("Jugador")

    if st.button("Gol Equipo A", disabled=not PARTIDO_ACTIVO):
        add_goal("A", zone, player)

    if st.button("Gol Equipo B", disabled=not PARTIDO_ACTIVO):
        add_goal("B", zone, player)

    if st.button("Reiniciar partido"):
        reset_match()

# -------- TIEMPO --------
with mid:
    st.subheader("Tiempo")
    elapsed = now_elapsed_seconds()
    st.markdown(f"**{elapsed//60:02d}:{elapsed%60:02d}**")

    col1, col2 = st.columns(2)
    with col1:
        st.button("▶ Reanudar", on_click=start_match, disabled=not PARTIDO_ACTIVO)
    with col2:
        st.button("⏸ Pausar", on_click=pause_match, disabled=not PARTIDO_ACTIVO)

# -------- HEATMAP --------
with right:
    st.subheader("Mapa de calor")

    xsA, ysA, sizesA = [], [], []
    xsB, ysB, sizesB = [], [], []

    for ev in match["events"]:
        z = ev["zone"]
        x, y = ZONE_COORDS[z]
        if ev["team"] == "A":
            xsA.append(x); ysA.append(y); sizesA.append(10)
        else:
            xsB.append(x); ysB.append(y); sizesB.append(10)

    fig = go.Figure()
    if xsA:
        fig.add_trace(go.Scatter(x=xsA, y=ysA, mode="markers", marker=dict(size=sizesA), name="Equipo A"))
    if xsB:
        fig.add_trace(go.Scatter(x=xsB, y=ysB, mode="markers", marker=dict(size=sizesB), name="Equipo B"))

    fig.update_xaxes(visible=False, range=[0,1])
    fig.update_yaxes(visible=False, range=[0,1])
    fig.update_layout(height=400)

    st.plotly_chart(fig, use_container_width=True)

# =========================
# EVENTOS
# =========================
st.markdown("---")
st.subheader("Eventos")
st.dataframe(pd.DataFrame(match["events"]))
