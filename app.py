# =========================================================
# AGUSTINOS MARCADOR — VERSIÓN COMPLETA Y ESTABLE
# =========================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime, json, glob
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from collections import defaultdict

from modules import recorder, loader
st.markdown("""
<style>
div[data-testid="stVerticalBlock"] > div {
    gap: 0.25rem;
}

button {
    margin-top: 0px !important;
    margin-bottom: 0px !important;
}

p {
    margin-bottom: 0.2rem !important;
    margin-top: 0.2rem !important;
}
</style>
""", unsafe_allow_html=True)


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
    "EI": (0.10, 0.10),
    "LI": (0.20, 0.32),
    "C":  (0.25, 0.50),
    "LD": (0.20, 0.68),
    "ED": (0.10, 0.90),
    "P":  (0.10, 0.50),
    "EXI": (0.35, 0.15),
    "EXC": (0.45, 0.50),
    "EXD": (0.35, 0.85),
}

ZONAS = {
    1: "EI",
    2: "LI",
    3: "C",
    4: "LD",
    5: "ED",
    6: "P",
    7: "EXI",
    8: "EXC",
    9: "EXD"
}

COURT_IMG=Image.open("court.png")

ZONA_NOMBRE_A_ID = {v: k for k, v in ZONAS.items()}

if st.session_state.get("partido_activo", False):
    st_autorefresh(interval=1000)

# =========================================================
# ESTADO PERSISTENTE (NO SE BORRA AL RECARGAR)
# =========================================================
if "partido_activo" not in st.session_state:
    st.session_state.partido_activo = False

if "match" not in st.session_state:
    st.session_state.match = {
    "teamA": "Equipo A",
    "teamB": "Equipo B",
    "scoreA": 0,
    "scoreB": 0,
    "events": [],
    "exclusions": [],
    "started_at": None,
    "elapsed_before_pause": 0,
    "part": 1
}

match = st.session_state.match

if "view" not in st.session_state:
    st.session_state.view = ""

if "partidos" not in st.session_state:
    st.session_state.partidos = []

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
        "teamA": "",
        "teamB": "",
        "scoreA": 0,
        "scoreB": 0,
        "events": [],
        "exclusions": [],
        "started_at": None,
        "elapsed_before_pause": 0,
        "part": 1
    }

def add_goal(team, zone, player=None):
    match["events"].append({
        "time": iso_now(),
        "team": team,
        "zone": ZONAS[int(zone)],
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

def set_match_time(minutes, seconds):
    total_seconds = minutes * 60 + seconds
    match["elapsed_before_pause"] = total_seconds
    match["started_at"] = None

def set_score(scoreA, scoreB):
    match["scoreA"] = scoreA
    match["scoreB"] = scoreB

def start_second_half():
    match["part"] = 2
    match["elapsed_before_pause"] = 0
    match["started_at"] = None

# =========================================================
# HEADER
# =========================================================
st.title("🏐 AGUSTINOS – Marcador Oficial")

col1, col2 = st.columns(2)
with col1:
    if st.button("▶️ INICIAR PARTIDO"):
        st.session_state.show_team_form = True

    if st.session_state.get("show_team_form", False):
        with st.form("form_teams"):
            teamA = st.text_input("Equipo A")
            teamB = st.text_input("Equipo B")

            if st.form_submit_button("Confirmar y empezar"):
                match["teamA"] = teamA or "Equipo A"
                match["teamB"] = teamB or "Equipo B"
                st.session_state.partido_activo = True
                start_match()
                st.session_state.show_team_form = False

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

    # Mostrar nombres y goles grandes
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; font-weight:bold; gap:20px;">
            <span style="font-size:28px;">{match['teamA']}</span>
            <span style="font-size:48px; color:blue;">{match['scoreA']}</span>  
            <span style="font-size:28px;">{match['teamB']}</span>
            <span style="font-size:48px; color:red;">{match['scoreB']}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Zona y jugador
    zone = st.selectbox(
        "Zona",
        list(ZONAS.keys()),
        format_func=lambda x: ZONAS[x],
        index=4
    )
    player = st.text_input("Jugador")

    # Botones de goles uno al lado del otro
    col_gol_a, col_gol_b = st.columns(2)
    with col_gol_a:
        st.button(f"Gol {match['teamA']}", on_click=add_goal, args=("A", zone, player))
    with col_gol_b:
        st.button(f"Gol {match['teamB']}", on_click=add_goal, args=("B", zone, player))

# -------- TIEMPO + EXCLUSIONES --------
exs = active_exclusions()

with mid:
    col_time, col_ex = st.columns([2, 3])

    # ⏱️ TIEMPO
    with col_time:
         st.subheader("Tiempo de partido")

         # recalcular el tiempo siempre que se renderiza
         t = elapsed_seconds()
         st.markdown(f"## {t//60:02d}:{t%60:02d}")

         # botones de control
         if st.button("⏸ Pausar"):
             pause_match()
         if st.button("▶ Reanudar"):
             start_match()

    # 🚫 EXCLUSIONES ACTIVAS
    with col_ex:
        exs = active_exclusions()

        if exs:
            st.subheader("🚫 Exclusiones")
            for ex in exs:
                mm = ex["remaining"] // 60
                ss = ex["remaining"] % 60
                st.markdown(
                    f"**{ex['player']}** | "
                    f"{match['teamA'] if ex['team']=='A' else match['teamB']} | "
                    f"⏱ {mm:02d}:{ss:02d}"
                )
        else:
            st.subheader("🚫 Exclusiones")
            st.write("—")
with right:
    
    with st.form("form_ex"):
        p = st.text_input("Jugador (nº)")
        team = st.selectbox(
            "Equipo",
            ["A", "B"],
            format_func=lambda x: match["teamA"] if x == "A" else match["teamB"]
        )
        dur = st.number_input(
            "Duración (seg)", 30, 600, DEFAULT_EXCLUSION_SECONDS
        )
        if st.form_submit_button("Añadir exclusión"):
            add_exclusion(p, team, dur)

    exs = active_exclusions()
    st.markdown("<div style='margin-top:-0.8rem'></div>", unsafe_allow_html=True)
# =========================================================
# HEATMAP (ANCHO COMPLETO, pegado arriba)
# =========================================================

# contenedor Streamlit para controlar separación
with st.container():
    st_empty = st.empty()  # "pegamento" para quitar espacio vertical
    st_empty.markdown("<div style='margin-top:-1rem'></div>", unsafe_allow_html=True)

    # 1️⃣ contar goles por zona y equipo
    goals = {
        "A": defaultdict(int),
        "B": defaultdict(int)
    }

    for ev in match["events"]:
        goals[ev["team"]][ev["zone"]] += 1

    # 2️⃣ función para construir coordenadas, tamaño y texto
    def build_team_points(team):
         xs, ys, sizes, texts = [], [], [], []

         for zone_name, n in goals[team].items():
             if zone_name not in ZONE_COORDS:
                 continue

             x, y = ZONE_COORDS[zone_name]

             if team == "B":
                 # Reflejar horizontalmente el eje X
                 x = 1 - x

                 # Ajustar las zonas laterales
                 if zone_name == "EI":  # izquierda → derecha
                     x = 1 - ZONE_COORDS["ED"][0]
                     y = ZONE_COORDS["ED"][1]
                 elif zone_name == "ED":  # derecha → izquierda
                     x = 1 - ZONE_COORDS["EI"][0]
                     y = ZONE_COORDS["EI"][1]
                 elif zone_name == "LI":  # izquierda interna → derecha interna
                     x = 1 - ZONE_COORDS["LD"][0]
                     y = ZONE_COORDS["LD"][1]
                 elif zone_name == "LD":  # derecha interna → izquierda interna
                     x = 1 - ZONE_COORDS["LI"][0]
                     y = ZONE_COORDS["LI"][1]
                 # Centro, P, EXI, EXC, EXD se mantienen igual

             xs.append(x)
             ys.append(y)
             sizes.append(18 + n*6)
             texts.append(str(n))

         return xs, ys, sizes, texts

    xsA, ysA, sizesA, textsA = build_team_points("A")
    xsB, ysB, sizesB, textsB = build_team_points("B")

    fig = go.Figure()

    fig.add_layout_image(
        dict(
            source=COURT_IMG,
            xref="x",
            yref="y",
            x=0,
            y=1,
            sizex=1,
            sizey=1,
            sizing="stretch",
            layer="below"
        )
    )

    fig.add_trace(go.Scatter(
        x=xsA,
        y=ysA,
        mode="markers+text",
        name=match["teamA"],
        marker=dict(size=sizesA, color="blue"),
        text=textsA,
        textfont=dict(color="white", size=14),
        textposition="middle center"
    ))

    fig.add_trace(go.Scatter(
        x=xsB,
        y=ysB,
        mode="markers+text",
        name=match["teamB"],
        marker=dict(size=sizesB, color="red"),
        text=textsB,
        textfont=dict(color="white", size=14),
        textposition="middle center"
    ))

    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(
        visible=False,
        range=[0, 1],
        scaleanchor="x",
        scaleratio=1
    )

    # margen mínimo para pegarlo arriba pero sin bloquear botones
    fig.update_layout(
    height=380,           # más estrecho verticalmente
    width=800,           # un poco más ancho
    autosize=False,       # desactivamos autosize para respetar width/height
    margin=dict(l=0, r=0, t=0, b=0)  # sin márgenes
)

    st.plotly_chart(fig, use_container_width=True)
    
if st.button("⚙️ MODIFICACIONES"):
    st.session_state.show_mods = not st.session_state.get("show_mods", False)



if st.session_state.get("show_mods", False):
    st.warning("⚠️ Modo modificaciones activado")

    # --- Ajuste de reloj ---
    st.subheader("⏱️ Ajustar reloj")
    colm1, colm2 = st.columns(2)
    with colm1:
        new_min = st.number_input("Minutos", 0, 60, t // 60)
    with colm2:
        new_sec = st.number_input("Segundos", 0, 59, t % 60)

    if st.button("Aplicar tiempo", key="aplicar_tiempo"):
        set_match_time(new_min, new_sec)
        st.success("Reloj actualizado")

    st.markdown("---")
    # --- Ajuste marcador ---
    st.subheader("📊 Ajustar marcador")
    colm3, colm4 = st.columns(2)
    with colm3:
        new_a = st.number_input("Equipo A", 0, 99, match["scoreA"])
    with colm4:
        new_b = st.number_input("Equipo B", 0, 99, match["scoreB"])

    if st.button("Aplicar marcador", key="aplicar_marcador"):
        set_score(new_a, new_b)
        st.success("Marcador actualizado")

    st.markdown("---")
    # --- Parte del partido ---
    st.subheader("🏁 Parte del partido")
    st.info(f"Parte actual: {match['part']}ª")

    # ⚡ Botón de segunda parte aquí
    if match["part"] == 1:
        if st.button("▶️ Iniciar 2ª parte", key="segunda_parte"):
            start_second_half()  # pone tiempo a cero y parte = 2
            st.success("Segunda parte iniciada (00:00)")
            st.experimental_rerun()  # fuerza que se actualice inmediatamente

# =========================================================
# EVENTOS
# =========================================================
st.markdown("---")
st.subheader("Eventos registrados")
if match["events"]:
    df = pd.DataFrame(match["events"])
    df["team"] = df["team"].map({
        "A": match["teamA"],
        "B": match["teamB"]
    })
    st.dataframe(df)
else:
    st.write("No hay eventos registrados.")

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
    "teamA": match["teamA"],
    "teamB": match["teamB"],
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

# --- GitHub config ---
GITHUB_OWNER = "BALONMANOAGUSTINOSMARCADOR"
GITHUB_REPO = "AGUSTINOSMARCADOR"

GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    st.warning("⚠️ No hay GITHUB_TOKEN configurado en Streamlit Secrets")

# Inicializar estado
if "partidos" not in st.session_state:
    st.session_state.partidos = []

if "search_results" not in st.session_state:
    st.session_state.search_results = []

if "view" not in st.session_state:
    st.session_state.view = ""


# ---- BOTÓN BUSCAR ----
if st.button("Buscar partidos"):

    if st.session_state.partido_activo:
        st.warning("⚠️ Para buscar partidos antes hay que FINALIZAR el partido")
    else:
        with st.spinner("🔍 Buscando partidos en el histórico..."):
            st.session_state.partidos = loader.cargar_partidos_github(
                GITHUB_OWNER,
                GITHUB_REPO,
                "data/partidos",
                GITHUB_TOKEN
            )

        st.session_state.view = "buscar_partidos"
        st.success("✅ Búsqueda completada")

# ---- FILTRADO ----
matches = []

for p in st.session_state.partidos:
    rival_p = p.get("rival", "").lower()

    if not buscar_rival.strip():
        matches.append(p)
    elif buscar_rival.strip().lower() in rival_p:
        matches.append(p)

st.session_state.search_results = matches

# ---- MOSTRAR RESULTADOS ----
if st.session_state.view == "buscar_partidos":
    results = st.session_state.search_results

    if results:
        st.success(f"Encontrados {len(results)} partidos.")
        for p in results:
            st.write("---")
            st.write(f"📅 Fecha: {p.get('fecha')}")
            st.write(f"🤝 Rival: {p.get('rival')}")
            st.write(f"📊 Resultado: {p.get('scoreA')} - {p.get('scoreB')}")
    else:
        st.warning("No se encontraron partidos.")
