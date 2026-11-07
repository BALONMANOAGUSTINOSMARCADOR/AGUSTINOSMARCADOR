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
from github import Github
import os
st.write("Versión Streamlit:", st.__version__)
# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="AGUSTINOS MARCADOR",
    layout="wide",
    page_icon="🏐"
)
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
# SESSION STATE (INICIALIZACIÓN GLOBAL)
# =========================================================
if "mostrar_form_ex" not in st.session_state:
    st.session_state.mostrar_form_ex = False

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

# =========================================================
# CONFIGURACIÓN CAMPO (AGUSTINOS MARCADOR PRO)
# =========================================================

FIELD_WIDTH = COURT_IMG.size[0]
FIELD_HEIGHT = COURT_IMG.size[1]
ZONA_NOMBRE_A_ID = {v: k for k, v in ZONAS.items()}

# Bloque para modificaciones
modificaciones_activo = True

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

        # Eventos del partido
        "events": [],

        # NUEVO - Lanzamiento seleccionado sobre el campo
        "selected_shot": None,

        # NUEVO - Zona seleccionada de la portería (1-4)
        "selected_goal_zone": None,

        "exclusions": [],

        # PORTEROS ACTIVOS DE CADA EQUIPO
        "active_goalkeepers": {"A": None, "B": None},

        # HISTORIAL DE CAMBIOS DE PORTERO
        "goalkeeper_changes": [],

        "players_stats": {"A": {}, "B": {}},        
        "started_at": None,
        "elapsed_before_pause": 0,
        "part": 1
    }

match = st.session_state.match

# COMPATIBILIDAD CON PARTIDOS ANTERIORES
match.setdefault("active_goalkeepers", {"A": None, "B": None})
match.setdefault("goalkeeper_changes", [])
    
if "view" not in st.session_state:
    st.session_state.view = ""

if "partidos" not in st.session_state:
    st.session_state.partidos = []

# =========================================================
# FUNCIONES QUE MODIFICAN EL PARTIDO — USANDO st.session_state.match DIRECTAMENTE
# =========================================================

def elapsed_seconds():
    m = st.session_state.match
    if not m["started_at"]:
        return m["elapsed_before_pause"]
    start = datetime.datetime.fromisoformat(m["started_at"])
    return int(m["elapsed_before_pause"] + (datetime.datetime.utcnow() - start).total_seconds())

def iso_now():
    """Devuelve la fecha y hora actual en formato ISO (UTC)"""
    return datetime.datetime.utcnow().isoformat()

def start_match():
    m = st.session_state.match
    if not m["started_at"]:
        m["started_at"] = iso_now()

def pause_match():
    m = st.session_state.match
    if m["started_at"]:
        m["elapsed_before_pause"] = elapsed_seconds()
        m["started_at"] = None

def reset_match():
    st.session_state.match = {
        "teamA": "",
        "teamB": "",
        "scoreA": 0,
        "scoreB": 0,
        "events": [],

        # NUEVO
        "selected_shot": None,
        "selected_goal_zone": None,

        "exclusions": [],

        # PORTEROS
        "active_goalkeepers": {"A": None, "B": None},
        "goalkeeper_changes": [],

        "players_stats": {"A": {}, "B": {}},

        "started_at": None,
        "elapsed_before_pause": 0,
        "part": 1        
    }

def registrar_cambio_portero(dorsal, team):

    m = st.session_state.match

    dorsal = str(dorsal).strip()

    if not dorsal:
        st.error("Introduce el dorsal del portero.")
        return

    if team not in ("A", "B"):
        st.error("Selecciona un equipo válido.")
        return

    porteros = m.setdefault(
        "active_goalkeepers",
        {"A": None, "B": None}
    )

    anterior = porteros.get(team)

    if anterior == dorsal:
        st.warning(
            f"El portero nº {dorsal} ya está en la portería."
        )
        return

    cambio = {
        "time": iso_now(),
        "elapsed_seconds": elapsed_seconds(),
        "part": m.get("part", 1),
        "team": team,
        "team_name": m["teamA"] if team == "A" else m["teamB"],
        "previous_goalkeeper": anterior,
        "goalkeeper": dorsal
    }

    m.setdefault("goalkeeper_changes", []).append(cambio)

    porteros[team] = dorsal

    st.success(
        f"Portero nº {dorsal} registrado para el EQUIPO {team}"
    )
def add_goal(team, zone, player=None, finta=None, resultado="Gol", zona_porteria=None):
        
    m = st.session_state.match

    if player and jugador_inhabilitado(player, team):
        return

    if player:
        stats = m["players_stats"][team].get(player)
        if stats and stats.get("inhabilitado"):
            st.error(f"🚫 JUGADOR Nº {player} NO PUEDE PARTICIPAR EN EL PARTIDO")
            return


                # IDENTIFICAR EL PORTERO DEL EQUIPO DEFENSOR
        equipo_defensor = "B" if team == "A" else "A"

        portero_defensor = None

        if resultado != "Pérdida":
            portero_defensor = m.get(
                "active_goalkeepers",
                {"A": None, "B": None}
            ).get(equipo_defensor)

        m["events"].append({
            "type": "goal" if resultado == "Gol" else "shot",
            "time": iso_now(),
            "team": team,
            "zone": ZONAS[int(zone)],
            "player": player,
            "finta": finta,
            "result": resultado,
            "goal_zone": zona_porteria,
            "goal_zone_layout": 4,

            # DATOS DEL PORTERO
            "goalkeeper_team": equipo_defensor if resultado != "Pérdida" else None,
            "goalkeeper": portero_defensor
        })        
        
    
    # Solo los goles modifican el marcador
    if resultado == "Gol":
        m[f"score{team}"] += 1

def jugador_inhabilitado(player, team):
    # ⚠️ Si no hay jugador, NO se bloquea nunca
    if not player:
        return False

    stats = st.session_state.match["players_stats"][team].get(player)

    if stats and stats.get("inhabilitado"):
        st.error("🚫 JUGADOR INHABILITADO")
        return True

    return False
    
    m["events"].append({
        "time": iso_now(),
        "team": team,
        "zone": ZONAS[int(zone)],
        "player": player
    })
    m[f"score{team}"] += 1

def add_exclusion(player, team, duration):
    m = st.session_state.match

    if jugador_inhabilitado(player, team):
        return

    stats = m["players_stats"][team].setdefault(
        player,
        {"exclusiones": 0, "amarilla": 0, "roja": 0, "azul": 0, "avisos": [], "inhabilitado": False}
    )

    # 🚫 Si ya está inhabilitado, no hacer nada
    if stats.get("inhabilitado"):
        st.error(f"🚫 JUGADOR Nº {player} NO PUEDE PARTICIPAR EN EL PARTIDO")
        return

    # Registrar exclusión temporal
    m["exclusions"].append({
        "player": player,
        "team": team,
        "started_at_seconds": elapsed_seconds(),
        "duration": duration
    })

    # Contador acumulado
    stats["exclusiones"] += 1

    # 🚫 Tres exclusiones = inhabilitado
    if stats["exclusiones"] >= 3:
        stats["inhabilitado"] = True
        stats["avisos"].append("Jugador inhabilitado (3 exclusiones)")

def active_exclusions():
    m = st.session_state.match
    active = []
    now_sec = elapsed_seconds()

    for ex in m["exclusions"]:
        end_sec = ex["started_at_seconds"] + ex["duration"]
        if now_sec < end_sec:
            remaining = int(end_sec - now_sec)
            ex["remaining"] = remaining
            active.append(ex)
   
    return active

def set_match_time(minutes, seconds):
    m = st.session_state.match
    total_seconds = minutes * 60 + seconds
    m["elapsed_before_pause"] = total_seconds
    m["started_at"] = None

def set_score(scoreA, scoreB):
    m = st.session_state.match
    m["scoreA"] = scoreA
    m["scoreB"] = scoreB

def start_second_half():
    m = st.session_state.match
    old_elapsed = elapsed_seconds()  # tiempo antes de poner a cero
    m["part"] = 2
    m["elapsed_before_pause"] = 0
    m["started_at"] = None

    # 🔹 Ajustar exclusiones para mantener lo que queda
    for ex in m["exclusions"]:
        ex["started_at_seconds"] -= old_elapsed  # mantiene los segundos restantes

def add_card(player, team, color):
    m = st.session_state.match

    if jugador_inhabilitado(player, team):
        return

    stats = m["players_stats"][team].setdefault(
        player,
        {"exclusiones": 0, "amarilla": 0, "roja": 0, "azul": 0, "avisos": [], "inhabilitado": False}
    )

    color_key = color.lower()

    # ❌ NO permitir duplicados
    if stats[color_key] == 1:
        st.error(f"🚫 JUGADOR Nº {player} YA TIENE ASIGNADA UNA TARJETA {color}")
        return

    # Registrar tarjeta
    stats[color_key] = 1

    # 🚫 Roja o azul → inhabilitado
    if color_key in ("roja", "azul"):
        stats["inhabilitado"] = True
        stats["avisos"].append("Jugador inhabilitado (tarjeta " + color + ")")

    st.success(f"Tarjeta {color} registrada al jugador {player}")

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

                # 🔹 Actualizar los inputs de modificaciones para reflejar los valores actuales
                st.session_state["mod_scoreA"] = match["scoreA"]
                st.session_state["mod_scoreB"] = match["scoreB"]
                st.session_state["mod_min"] = 0
                st.session_state["mod_sec"] = 0
 
with col2:
    if st.button("⏹️ FINALIZAR PARTIDO", disabled=not st.session_state.partido_activo):
        st.session_state.partido_activo = False
        pause_match()

if not st.session_state.partido_activo:
    st.info("Partido no activo. Los datos permanecen visibles.")

if st.session_state.partido_activo and match["part"] == 1:
    if st.button("⏭️ INICIAR 2ª PARTE"):
        pause_match()
        start_second_half()
        start_match()
        st.success("⏭️ Segunda parte iniciada")
        st.rerun()

# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================
left, mid, right = st.columns(3)

# -------- MARCADOR --------
with left:
    st.subheader("Marcador")

    # Reservar el espacio del marcador para actualizarlo tras procesar los goles.
    marcador_placeholder = st.empty()

    # Jugador y Zona en la misma fila
    col_player, col_zone = st.columns([1, 1])
    with col_player:
        player = st.text_input("Jugador")
    with col_zone:
        zone = st.selectbox(
            "Zonas",
            list(ZONAS.keys()),
            format_func=lambda x: ZONAS[x],
            index=4
        )
    # 👇 NUEVO: FINTA IZQUIERDA / DERECHA
    col_finta1, col_finta2 = st.columns(2)

    with col_finta1:
        finta_iz = st.checkbox("IZ")

    with col_finta2:
        finta_der = st.checkbox("DCHA")

    # 🔒 Control de selección de finta
    finta = None

    if finta_iz and finta_der:
        st.warning("⚠️ No puedes marcar IZ y DCHA a la vez")
    elif finta_iz:
        finta = "IZ"
    elif finta_der:
        finta = "DCHA"


    # -----------------------------
    # RESULTADO DEL LANZAMIENTO
    # -----------------------------
    resultado = st.radio(
        "Resultado",
        [
            "Gol",
            "Parada",
            "Poste",
            "Fuera",
            "Pérdida"
        ],
        horizontal=True
    )

    
    # -----------------------------
    # ZONA DE FINALIZACIÓN Y GOLES
    # -----------------------------
    with st.container(key="zona_finalizacion"):

        st.markdown("### 🥅 Zona de finalización")

        # Estilo de la botonera de cuatro zonas
        st.markdown("""
        <style>
        .st-key-botonera_zonas div.stButton > button {
            height: 30px;
            min-height: 30px;
            padding: 0px;
            font-size: 12px;
            font-weight: bold;
            margin: 0px !important;
        }

        .st-key-zona_finalizacion div[data-testid="stHorizontalBlock"] {
            gap: 0.15rem !important;
        }

        .st-key-goles_equipos div[data-testid="stHorizontalBlock"] {
            gap: 0.1rem !important;
        }

        .st-key-goles_equipos div.stButton > button {
            margin-top: 0px !important;
            margin-bottom: 0px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # Comprobar que la zona seleccionada pertenece al nuevo sistema 1-4
        if st.session_state.match.get("selected_goal_zone") not in (1, 2, 3, 4):
            st.session_state.match["selected_goal_zone"] = None

        # Botonera de cuatro zonas: dos arriba y dos abajo
        with st.container(key="botonera_zonas"):

            for fila in [[1, 2], [3, 4]]:
                c1, c2 = st.columns(2, gap="small")

                for col, zona in zip([c1, c2], fila):
                    with col:
                        if st.button(
                            str(zona),
                            key=f"goal_{zona}",
                            use_container_width=True
                        ):
                            st.session_state.match["selected_goal_zone"] = zona

        zona_porteria = st.session_state.match["selected_goal_zone"]

        if zona_porteria:
            st.caption(f"🎯 Zona seleccionada: {zona_porteria}")

        # Botones de los dos equipos
        with st.container(key="goles_equipos"):

            col_gol_a, col_gol_b = st.columns([1, 1], gap="small")

            with col_gol_a:
                if st.button(
                    f"⚽ GOL {match['teamA']}",
                    key="gol_equipo_a",
                    use_container_width=True
                ):
                    if finta is None:
                        st.warning("⚠️ Debes seleccionar tipo de finta")
                    elif zona_porteria is None:
                        st.warning("⚠️ Debes seleccionar una zona de la portería")
                    else:
                        add_goal("A", zone, player, finta, resultado, zona_porteria)

            with col_gol_b:
                if st.button(
                    f"⚽ GOL {match['teamB']}",
                    key="gol_equipo_b",
                    use_container_width=True
                ):
                    if finta is None:
                        st.warning("⚠️ Debes seleccionar tipo de finta")
                    elif zona_porteria is None:
                        st.warning("⚠️ Debes seleccionar una zona de la portería")
                    else:
                        add_goal("B", zone, player, finta, resultado, zona_porteria)
    

    # Actualizar el marcador en su posición original, ya con el resultado del botón.
    marcador_placeholder.markdown(
        f"""
        <div style="display:flex; align-items:center; font-weight:bold; gap:0px;">
            <span style="font-size:28px;">{match['teamA']}</span>
            <span style="font-size:48px; color:blue;">{match['scoreA']}</span>  
            <span style="font-size:28px;">{match['teamB']}</span>
            <span style="font-size:48px; color:red;">{match['scoreB']}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # =====================================================
    # REGISTRO DEL LANZAMIENTO (AGUSTINOS MARCADOR PRO)
    # =====================================================

    contenedor = st.container()

    with contenedor:

        col_campo, col_porteria = st.columns([2.4,1.2], gap="large")  


# -------- TIEMPO + EXCLUSIONES --------

@st.fragment(
    run_every="1s" if st.session_state.get("partido_activo", False) else None
)
def render_timer_exclusions():
    st.subheader("🚫 Exclusiones")

    # ⏱️ TIEMPO DE PARTIDO
    t = elapsed_seconds()
    st.markdown(f"## {t//60:02d}:{t%60:02d}")

    col_pause, col_resume = st.columns(2)

    with col_pause:
        if st.button("⏸ Pausar", key="pausar_reloj"):
            pause_match()
            st.rerun()

    with col_resume:
        if st.button("▶ Reanudar", key="reanudar_reloj"):
            start_match()
            st.rerun()

    # Mostrar exclusiones activas
    exs = active_exclusions()

    if exs:
        for ex in exs:
            mm = ex["remaining"] // 60
            ss = ex["remaining"] % 60

            stats = match["players_stats"][ex["team"]].get(
                ex["player"], {"exclusiones": 0}
            )
            count = stats["exclusiones"]

            st.markdown(
                f"**{ex['player']}** ({count}) | "
                f"{match['teamA'] if ex['team']=='A' else match['teamB']} | "
                f"⏱ {mm:02d}:{ss:02d}"
            )
    else:
        st.write("—")


with mid:
    render_timer_exclusions()


# =========================================================
# MAPAS DE CALOR DE LAS DOS PORTERÍAS
# =========================================================

def render_goal_heatmap(team, rgb, title):

    # Contar los goles de cada uno de los cuatro sectores
    counts = {
        1: 0,
        2: 0,
        3: 0,
        4: 0
    }

    for ev in match["events"]:

        if ev.get("type") != "goal":
            continue

        if ev.get("team") != team:
            continue

        # Solo contabilizar goles registrados con el nuevo sistema
        if ev.get("goal_zone_layout") != 4:
            continue

        try:
            zona = int(ev.get("goal_zone"))
        except (TypeError, ValueError):
            continue

        if zona in counts:
            counts[zona] += 1

    max_goals = max(counts.values()) or 1

    # Construir los cuatro cuadrantes de la portería
    cells = []

    for zona in (1, 2, 3, 4):

        goles = counts[zona]

        if goles > 0:
            intensidad = goles / max_goals
            alpha = 0.18 + (0.72 * intensidad)

            fondo = f"rgba({rgb}, {alpha:.2f})"

            color_texto = (
                "#FFFFFF" if intensidad >= 0.55 else "#111111"
            )
        else:
            fondo = "#F1F1F1"
            color_texto = "#555555"

        cells.append(
            f"""
            <div style="
                min-height:68px;
                display:flex;
                flex-direction:column;
                align-items:center;
                justify-content:center;
                gap:2px;
                background:{fondo};
                color:{color_texto};
                border:1px solid rgba(0,0,0,0.15);
                border-radius:2px;
            ">
                <strong style="font-size:28px;">
                    {goles}
                </strong>
            </div>
            """
        )

    
    # Dibujar portería frontal dividida en cuatro sectores
    st.components.v1.html(
        f"""
        <div style="
            margin:0.35rem 0 1rem;
            font-family:Arial,sans-serif;
        ">

            <div style="
                text-align:center;
                font-weight:bold;
                font-size:14px;
                margin-bottom:6px;
                color:rgb({rgb});
            ">
                {title}
            </div>

            <div style="
                max-width:330px;
                margin:0 auto;
                padding:5px;
                border:4px solid #222222;
                border-bottom:none;
                border-radius:4px;
                background:#FFFFFF;
                display:grid;
                grid-template-columns:1fr 1fr;
                gap:3px;
                box-sizing:border-box;
            ">
                {''.join(cells)}
            </div>

        </div>
        """,
        height=190,
        scrolling=False
    )
    
# PORTERÍA AZUL — EQUIPO A
with mid:
    render_goal_heatmap(
        "A",
        "30, 100, 220",
        "PORTERÍA AZUL — EQUIPO A"
    )

    # PORTERÍA ROJA — EQUIPO B
    render_goal_heatmap(
        "B",
        "220, 45, 55",
        "PORTERÍA ROJA — EQUIPO B"
    )

# -------- AÑADIR EXCLUSIÓN / TARJETA --------
# Pegamento para subir la columna de la derecha
st_empty_right = st.empty()
st_empty_right.markdown("<div style='margin-top:-1rem'></div>", unsafe_allow_html=True)

with right:
    with st.form("form_ex", clear_on_submit=True):

        # Número de jugador y equipo en columnas
        col_player, col_team = st.columns([1, 1])
        with col_player:
            p = st.text_input("Jugador (nº)")
        with col_team:
            team = st.selectbox(
                "Equipo",
                ["A", "B"],
                format_func=lambda x: match["teamA"] if x == "A" else match["teamB"]
            )

        # Duración y Tarjeta en la misma fila
        col_dur, col_card = st.columns([1, 1])
        with col_dur:
            dur = st.number_input(
                "Duración (seg)",
                30, 600,
                DEFAULT_EXCLUSION_SECONDS
            )
        with col_card:
            card_color = st.selectbox(
                "Tarjeta (opcional)",
                ["NINGUNA", "AMARILLA", "ROJA", "AZUL"],
                index=0
            )

        # Botón de registro
        if st.form_submit_button("➕ Añadir exclusión / tarjeta"):

            # ⛔ Exclusión SOLO si NO es amarilla
            if card_color in ("NINGUNA", "ROJA", "AZUL"):
                if dur > 0:
                    add_exclusion(p, team, dur)

            # 🟨🟥🟦 Tarjetas
            if card_color != "NINGUNA":
                add_card(p, team, card_color)

        # -------------------------------------------------
    # CAMBIO DE PORTERO
    # -------------------------------------------------

    with st.form("form_cambio_portero", clear_on_submit=True):

        col_dorsal, col_equipo, col_boton = st.columns(
            [1, 1, 1.2]
        )

        with col_dorsal:
            dorsal_portero = st.text_input(
                "Dorsal",
                placeholder="Nº"
            )

        with col_equipo:
            equipo_portero = st.selectbox(
                "Equipo",
                ["A", "B"],
                format_func=lambda x: (
                    "EQUIPO A" if x == "A" else "EQUIPO B"
                )
            )

        with col_boton:
            st.write("")
            registrar = st.form_submit_button(
                "CAMBIO DE PORTERO",
                use_container_width=True
            )

        if registrar:
            registrar_cambio_portero(
                dorsal_portero,
                equipo_portero
            )

    # MOSTRAR PORTEROS ACTUALES

    porteros_activos = match.get(
        "active_goalkeepers",
        {"A": None, "B": None}
    )

    portero_a = porteros_activos.get("A") or "Sin registrar"
    portero_b = porteros_activos.get("B") or "Sin registrar"

    st.caption(
        f"🥅 A: {portero_a}  |  B: {portero_b}"
    )    

        
    court_placeholder = st.empty()    

# =========================================================
# HEATMAP (ANCHO COMPLETO, pegado arriba)
# =========================================================

# contenedor Streamlit para controlar separación
with st.container():
    st_empty = st.empty()  # "pegamento" para quitar espacio vertical
    st_empty.markdown("<div style='margin-top:-1rem'></div>", unsafe_allow_html=True)

    # 1️⃣ contar goles por zona y equipo (CON FINTAS)
    goals = {
        "A": defaultdict(lambda: {"total": 0, "IZ": 0, "DCHA": 0}),
        "B": defaultdict(lambda: {"total": 0, "IZ": 0, "DCHA": 0})
    }

    for ev in match["events"]:

        # Solo contar los goles
        if ev.get("type") != "goal":
            continue

        z = ev["zone"]
        t = ev["team"]

        goals[t][z]["total"] += 1

        if ev.get("finta") == "IZ":
            goals[t][z]["IZ"] += 1
        elif ev.get("finta") == "DCHA":
            goals[t][z]["DCHA"] += 1
            
    # 2️⃣ función para construir coordenadas, tamaño y texto
    def build_team_points(team):
        xs, ys, sizes, texts = [], [], [], []

        for zone_name, data in goals[team].items():
            n = data["total"]
            
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
                elif zone_name == "EXI":  # invertir EXI ↔ EXD
                    x = 1 - ZONE_COORDS["EXD"][0]
                    y = ZONE_COORDS["EXD"][1]
                elif zone_name == "EXD":  # invertir EXD ↔ EXI
                    x = 1 - ZONE_COORDS["EXI"][0]
                    y = ZONE_COORDS["EXI"][1]
                    
    # Centro, P, EXC se mantienen igual

            xs.append(x)
            ys.append(y)
            sizes.append(18 + n*6)
            texts.append(str(n))

        return xs, ys, sizes, texts

    xsA, ysA, sizesA, textsA = build_team_points("A")
    xsB, ysB, sizesB, textsB = build_team_points("B")

    fig = go.Figure()

# Punto seleccionado para el lanzamiento
selected_shot = match.get("selected_shot")

# Zona de portería seleccionada
selected_goal_zone = match.get("selected_goal_zone")

# Dibujar el campo SIEMPRE, aunque no haya lanzamiento seleccionado
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

# Puntos del equipo A
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

# Puntos del equipo B
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

# Dibujar una X verde donde se seleccione un lanzamiento
selected_shot = match.get("selected_shot")

if selected_shot is not None:
    sx, sy = selected_shot

    fig.add_trace(go.Scatter(
        x=[sx],
        y=[sy],
        mode="markers",
        marker=dict(
            size=14,
            color="lime",
            symbol="x"
        ),
        showlegend=False
    ))

# Configuración del campo: mantener el ajuste automático
fig.update_xaxes(
    visible=False,
    range=[0, 1],
    autorange=True
)

fig.update_yaxes(
    visible=False,
    range=[0, 1],
    autorange=True,
    scaleanchor="x",
    scaleratio=1
)

fig.update_layout(
    height=500,
    autosize=True,
    margin=dict(l=0, r=0, t=0, b=0)
)

# ==========================================
# DIBUJAR PUNTO DE LANZAMIENTO SELECCIONADO
# ==========================================

if selected_shot is not None:

    x, y = selected_shot

    fig.add_trace(
        go.Scatter(
            x=[x],
            y=[y],
            mode="markers",
            marker=dict(
                size=16,
                color="yellow",
                line=dict(color="black", width=2)
            ),
            showlegend=False
        )
    )
# =========================================================
# FLECHAS DE FINTAS
# =========================================================

def draw_fintas(team):
    for zone_name, data in goals[team].items():

        if zone_name not in ZONE_COORDS:
            continue

        total = data["total"]
        if total == 0:
            continue

        iz = data["IZ"]
        dcha = data["DCHA"]

        pct_iz = int((iz / total) * 100)
        pct_dcha = int((dcha / total) * 100)

        texto_sup = f"DCHA {pct_dcha}%"
        texto_inf = f"IZ {pct_iz}%"

        x, y = ZONE_COORDS[zone_name]

        # REFLEJO para equipo B (igual que ya haces)
        if team == "B":
            x = 1 - x

            if zone_name == "EI":
                x = 1 - ZONE_COORDS["ED"][0]
                y = ZONE_COORDS["ED"][1]
            elif zone_name == "ED":
                x = 1 - ZONE_COORDS["EI"][0]
                y = ZONE_COORDS["EI"][1]
            elif zone_name == "LI":
                x = 1 - ZONE_COORDS["LD"][0]
                y = ZONE_COORDS["LD"][1]
            elif zone_name == "LD":
                x = 1 - ZONE_COORDS["LI"][0]
                y = ZONE_COORDS["LI"][1]
            elif zone_name == "EXI":
                x = 1 - ZONE_COORDS["EXD"][0]
                y = ZONE_COORDS["EXD"][1]
            elif zone_name == "EXD":
                x = 1 - ZONE_COORDS["EXI"][0]
                y = ZONE_COORDS["EXI"][1]

        offset = 0.04
        curva = 0.05

        # ================================
        # EQUIPO A (flechas desde derecha)
        # ================================
        if team == "A":

            # 🔼 FINTA DCHA (flecha superior)
            fig.add_annotation(
                x=x - offset,
                y=y - curva,
                ax=x + offset,
                ay=y,
                showarrow=True,
                arrowhead=2,
                arrowwidth=1,
                arrowcolor="gray",
                text=f"<b>{pct_iz}%</b>",
                font=dict(size=11, color="black"),
            )

            # 🔽 FINTA IZ (flecha inferior)
            fig.add_annotation(
                x=x - offset,
                y=y + curva,
                ax=x + offset,
                ay=y,
                showarrow=True,
                arrowhead=2,
                arrowwidth=1,
                arrowcolor="gray",
                text=f"<b>{pct_dcha}%</b>",
                font=dict(size=11, color="black"),
            )

        # ================================
        # EQUIPO B (flechas desde izquierda)
        # ================================
        else:

            # 🔼 FINTA DCHA (flecha superior)
            fig.add_annotation(
                x=x + offset,
                y=y - curva,
                ax=x - offset,
                ay=y,
                showarrow=True,
                arrowhead=2,
                arrowwidth=1,
                arrowcolor="gray",
                text=f"<b>{pct_dcha}%</b>",
                font=dict(size=11, color="black"),
            )

            # 🔽 FINTA IZ (flecha inferior)
            fig.add_annotation(
                x=x + offset,
                y=y + curva,
                ax=x - offset,
                ay=y,
                showarrow=True,
                arrowhead=2,
                arrowwidth=1,
                arrowcolor="gray",
                text=f"<b>{pct_iz}%</b>",
                font=dict(size=11, color="black"),
            )


# ejecutar para ambos equipos
draw_fintas("A")
draw_fintas("B")

config = {
    "displayModeBar": False
}

court_placeholder.plotly_chart(
    fig,
    use_container_width=True,
    key="campo_heatmap_fijo"
)

# Modificaciones permitidas solo si el reloj NO está corriendo
modificaciones_habilitadas = match["started_at"] is None

def resumen_jugador(events, team, player):
    total = 0
    iz = 0
    dcha = 0

    for ev in events:
        if ev["team"] == team and ev.get("player") == player:
            total += 1

            if ev.get("finta") == "IZ":
                iz += 1
            elif ev.get("finta") == "DCHA":
                dcha += 1

    if total == 0:
        return 0, 0, 0

    pct_iz = int((iz / total) * 100)
    pct_dcha = int((dcha / total) * 100)

    return total, pct_iz, pct_dcha

def resumen_jugador_por_zona(events, team, player):
    resumen = {}

    for ev in events:
        if ev["team"] == team and ev.get("player") == player:
            zona = ev["zone"]

            if zona not in resumen:
                resumen[zona] = {"total": 0, "IZ": 0, "DCHA": 0}

            resumen[zona]["total"] += 1

            if ev.get("finta") == "IZ":
                resumen[zona]["IZ"] += 1
            elif ev.get("finta") == "DCHA":
                resumen[zona]["DCHA"] += 1

    return resumen

# =========================================================
# INCIDENCIAS: exclusiones acumuladas + tarjetas
# =========================================================
st.markdown("---")
st.subheader("📋 INCIDENCIAS")

for team_key, team_name in [("A", match["teamA"]), ("B", match["teamB"])]:
    st.markdown(f"**Equipo {team_name}**")
    stats_team = match["players_stats"][team_key]
    if stats_team:
        df_stats = pd.DataFrame.from_dict(stats_team, orient="index")
        df_stats.index.name = "Jugador"
        df_stats = df_stats[["exclusiones","amarilla","roja","azul","avisos"]]
        st.dataframe(df_stats)
    else:
        st.write("—")


# =========================================================
# MODIFICACIONES (SIEMPRE VISIBLES) — BLOQUE DEFINITIVO
# =========================================================

st.markdown("---")
st.subheader("🛠️ Modificaciones")
if not modificaciones_habilitadas:
    st.info("⏸️ Para aplicar modificaciones, primero pausa el partido.")

# ─────────────────────────────
# ⏱️ MODIFICAR TIEMPO
# ─────────────────────────────
with st.form("form_mod_tiempo"):
    col_time1, col_time2 = st.columns(2)

    with col_time1:
        new_min = st.number_input(
            "Minutos", 0, 60,
            value=st.session_state.get("mod_min", elapsed_seconds() // 60),
            key="mod_min"
        )

    with col_time2:
        new_sec = st.number_input(
            "Segundos", 0, 59,
            value=st.session_state.get("mod_sec", elapsed_seconds() % 60),
            key="mod_sec"
        )

    if st.form_submit_button(
        "⏱️ Aplicar tiempo",
        disabled=not modificaciones_habilitadas
    ):
        pause_match()
        old_elapsed = elapsed_seconds()  # tiempo antes de modificar
        set_match_time(new_min, new_sec)
        new_elapsed = elapsed_seconds()

        # 🔹 Ajustar exclusiones para mantener segundos restantes
        for ex in match["exclusions"]:
            ex["started_at_seconds"] += (new_elapsed - old_elapsed)

        st.success("⏱️ Tiempo actualizado")

    st.caption(
        "⚠️ PARA CAMBIAR EL TIEMPO HAY QUE FINALIZAR EL PARTIDO Y LUEGO VOLVER A INICIARLO (No se borran los datos, solamente el nombre de los equipos. Reescribirlos)"
    )

# ─────────────────────────────
# 🧮 MODIFICAR MARCADOR
# ─────────────────────────────
with st.form("form_mod_marcador"):
    col_score1, col_score2 = st.columns(2)

    with col_score1:
        new_a = st.number_input(
            "Equipo A", 0, 99,
            value=st.session_state.get("mod_scoreA", match["scoreA"]),
            key="mod_scoreA"
        )

    with col_score2:
        new_b = st.number_input(
            "Equipo B", 0, 99,
            value=st.session_state.get("mod_scoreB", match["scoreB"]),
            key="mod_scoreB"
        )

    if st.form_submit_button(
    "🧮 Aplicar marcador",
    disabled=not modificaciones_habilitadas
):
        pause_match()
        set_score(new_a, new_b)
        st.success("🧮 Marcador actualizado")
        st.rerun()
    st.caption(
    "⚠️ PARA CAMBIAR EL MARCADOR, TIENE QUE ESTAR EL TIEMPO EN PAUSA, INDICAR GOLES DE LOS DOS EQUIPOS"
)

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

if st.button("💾 Guardar en histórico"):

    if not rival or not competicion:
        st.error("Debes indicar Rival y Competición")
    else:
        pause_match()  # congelar tiempo exacto antes de guardar

        # ─────────────────────────
        # CREAR OBJETO DEL PARTIDO
        # ─────────────────────────
        partido_guardado = {
            "equipo_local": match["teamA"],
            "equipo_visitante": match["teamB"],
            "goles_local": match["scoreA"],
            "goles_visitante": match["scoreB"],
            "fecha": datetime.datetime.utcnow().isoformat(),
            "acciones": match["events"],
            "exclusiones": match["exclusions"],
            "players_stats": match["players_stats"],
            "rival": rival,
            "competicion": competicion
        }

        # ─────────────────────────
        # CONECTAR CON GITHUB
        # ─────────────────────────
        from github import Github
        import datetime
        import json

        try:
            g = Github(st.secrets["GITHUB_TOKEN"])
            repo = g.get_repo("BALONMANOAGUSTINOSMARCADOR/AGUSTINOSMARCADOR")

            # ─────────────────────────
            # NOMBRE DEL ARCHIVO
            # ─────────────────────────
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"data/partidos/partido_{timestamp}.json"
            contenido_json = json.dumps(partido_guardado, indent=4)

            # ─────────────────────────
            # SUBIR A GITHUB
            # ─────────────────────────
            # Forzar branch 'main' (cambia si antes usabas otra)
            branch_name = "main"  

            repo.create_file(
                path=filename,
                message=f"Nuevo partido guardado {timestamp}",
                content=contenido_json,
                branch=branch_name
            )

            st.success(f"✅ Partido guardado en GitHub correctamente: {filename}")

        except Exception as e:
            st.error(f"❌ Error guardando en GitHub: {e}")
            st.warning("Revisa que el token tenga permisos y que la rama exista.")

# 🔹 Buscar todos los archivos JSON en data/partidos
files = sorted(glob.glob(os.path.join("data", "partidos", "*.json")), reverse=True)

if files:
    selected_file = st.selectbox("Seleccionar partido", files)

    if st.button("🔄 Cargar partido seleccionado"):
        with open(selected_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # =====================================================
        # Detectar el tipo de JSON y adaptar a la estructura de la app
        # =====================================================
        if "data" in data:
            # JSON muy nuevo (con 'data')
            st.session_state.match = data["data"]

        elif "equipo_local" in data and "acciones" in data:
            # JSON reciente guardado con la nueva función
            st.session_state.match = {
                "teamA": data.get("equipo_local", "Equipo A"),
                "teamB": data.get("equipo_visitante", "Equipo B"),
                "scoreA": data.get("goles_local", 0),
                "scoreB": data.get("goles_visitante", 0),
                "events": data.get("acciones", []),
                "exclusions": data.get("exclusiones", []),
                "players_stats": data.get("players_stats", {"A": {}, "B": {}}),
                "started_at": None,
                "elapsed_before_pause": 0,
                "part": 1
            }

        else:
            # JSON antiguo (viejos partidos)
            st.session_state.match = {
                "teamA": "Equipo A",
                "teamB": "Equipo B",
                "scoreA": data.get("scoreA", 0),
                "scoreB": data.get("scoreB", 0),
                "events": data.get("events", []),
                "exclusions": data.get("exclusiones", []),
                "players_stats": {"A": {}, "B": {}},
                "started_at": None,
                "elapsed_before_pause": data.get("elapsed_seconds", 0),
                "part": 1
            }

        st.session_state.partido_activo = False
        st.success("✅ Partido cargado correctamente")
        st.rerun()

else:
    st.write("No hay partidos guardados todavía.")



# =========================================================
# 📊 DASHBOARD GRÁFICO DEL PARTIDO
# =========================================================

if match["events"]:

    st.markdown("---")
    st.header("📊 Análisis gráfico del partido")

    goals_sorted = sorted(match["events"], key=lambda x: x["time"])

    # =====================================================
    # 1️⃣ EVOLUCIÓN DEL MARCADOR
    # =====================================================
    st.subheader("📈 Evolución del marcador")
    st.caption("Progresión acumulada goles ambos equipos")

    times = []
    scoreA = []
    scoreB = []

    a = 0
    b = 0

    base_time = datetime.datetime.fromisoformat(goals_sorted[0]["time"])

    for ev in goals_sorted:
        t = datetime.datetime.fromisoformat(ev["time"])
        minute = int((t - base_time).total_seconds())
        times.append(minute)

        if ev["team"] == "A":
            a += 1
        else:
            b += 1

        scoreA.append(a)
        scoreB.append(b)

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=times, y=scoreA, mode="lines+markers", name=match["teamA"]))
    fig1.add_trace(go.Scatter(x=times, y=scoreB, mode="lines+markers", name=match["teamB"]))
    fig1.update_layout(height=400)
    st.plotly_chart(fig1, use_container_width=True)

    # =====================================================
    # 2️⃣ GOLES POR JUGADOR (POR EQUIPO)
    # =====================================================
    st.subheader("📊 Goles por jugador por equipo")
    st.caption("Distribución individual total, ordenado de máximo a mínimo, colores por equipo")

    from collections import defaultdict

    # 🔹 Contar goles por jugador por equipo
    player_goals = {"A": defaultdict(int), "B": defaultdict(int)}
    for ev in match["events"]:
        jugador = ev.get("player")
        if not jugador:
            continue
        player_goals[ev["team"]][str(jugador)] += 1

        # 🔹 Ordenar de mayor a menor
        # ================================
        # 🔵 GOLES POR JUGADOR (ORDENADO)
        # ================================

    def plot_goals_team(team, team_name, color):
        
        goles_jugador = {}

        for ev in match["events"]:
            if ev["team"] == team:
                jugador = ev.get("player")
                if not jugador:
                    continue

                goles_jugador[jugador] = goles_jugador.get(jugador, 0) + 1

        # ❌ eliminar jugadores sin goles (ya queda implícito)

        # ✅ ordenar de mayor a menor
        jugadores_ordenados = sorted(
            goles_jugador,
            key=goles_jugador.get,
            reverse=True
        )

        goles_ordenados = [goles_jugador[j] for j in jugadores_ordenados]

        # 🔹 Crear gráfico

        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=[str(j) for j in jugadores_ordenados],  # 👈 número jugador en eje X
            y=goles_ordenados,
            marker=dict(color=color)
        ))

        fig.update_layout(
            title=f"Goles por jugador - {team_name}",
            xaxis_title="Jugador",
            yaxis_title="Goles",
            xaxis=dict(type="category"),
            bargap=0,  # Sin separación entre barras
            height=400,
            showlegend=False
        )

        config = {
    "displayModeBar": False
}        
        st.plotly_chart(fig, use_container_width=True)

    # 🔹 Graficar equipo A
    plot_goals_team("A", match["teamA"], "steelblue")

    # 🔹 Graficar equipo B
    plot_goals_team("B", match["teamB"], "orange")

    # =====================================================
    # 3️⃣ GOLES POR ZONA
    # =====================================================
    st.subheader("📊 Distribución de goles por zona")
    st.caption("Comparativa ofensiva espacial equipos")

    zone_data = {"A": {}, "B": {}}

    for ev in match["events"]:
        z = ev["zone"]
        team = ev["team"]
        zone_data[team][z] = zone_data[team].get(z, 0) + 1

    zonas = list(ZONAS.values())

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(
        x=zonas,
        y=[zone_data["A"].get(z, 0) for z in zonas],
        name=match["teamA"]
    ))
    fig3.add_trace(go.Bar(
        x=zonas,
        y=[zone_data["B"].get(z, 0) for z in zonas],
        name=match["teamB"]
    ))

    fig3.update_layout(barmode="group", height=400)
    st.plotly_chart(fig3, use_container_width=True)

    # =====================================================
    # 4️⃣ MOMENTUM
    # =====================================================
    st.subheader("📈 Momentum del partido")
    st.caption("Diferencial dinámico impacto goles")

    diferencial = []
    diff = 0

    for ev in goals_sorted:
        if ev["team"] == "A":
            diff += 1
        else:
            diff -= 1
        diferencial.append(diff)

    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(x=times, y=diferencial, mode="lines+markers"))
    fig4.update_layout(height=400)
    st.plotly_chart(fig4, use_container_width=True)

    # =====================================================
    # 5️⃣ EXCLUSIONES EN EL TIEMPO
    # =====================================================
    if match["exclusions"]:
        st.subheader("🚫 Exclusiones durante el partido")
        st.caption("Frecuencia temporal sanciones disciplinarias")

        ex_times = [ex["started_at_seconds"] for ex in match["exclusions"]]

        fig5 = go.Figure([go.Histogram(x=ex_times)])
        fig5.update_layout(height=400)
        st.plotly_chart(fig5, use_container_width=True)

# =====================================================
# 6️⃣ GOLES JUGADOR POR ZONA
# =====================================================
st.subheader("🎯 GOLES JUGADOR POR ZONA")
st.caption("Producción individual comparada con media equipo")

# Estructura: equipo → jugador → zona → goles
estructura = {
    "A": {},
    "B": {}
}

for ev in match["events"]:
    jugador = ev.get("player")
    if not jugador:
        continue

    equipo = ev["team"]
    zona = ev["zone"]

    if jugador not in estructura[equipo]:
        estructura[equipo][jugador] = {z: 0 for z in ZONAS.values()}

    estructura[equipo][jugador][zona] += 1

for equipo in ["A", "B"]:

    jugadores = estructura[equipo]

    if not jugadores:
        continue

    st.markdown(f"### Equipo {match['teamA'] if equipo=='A' else match['teamB']}")

    # calcular media por zona del equipo
    total_por_zona = {z: 0 for z in ZONAS.values()}
    num_jugadores = len(jugadores)

    for jugador in jugadores:
        for zona in ZONAS.values():
            total_por_zona[zona] += jugadores[jugador][zona]

    media_equipo = {
        z: total_por_zona[z] / num_jugadores
        for z in ZONAS.values()
    }

    for jugador, datos in jugadores.items():

        if sum(datos.values()) == 0:
            continue

        zonas_ordenadas = sorted(datos.items(), key=lambda x: x[1], reverse=True)

        zonas_x = [z for z, v in zonas_ordenadas]
        valores_y = [v for z, v in zonas_ordenadas]
        media_y = [media_equipo[z] for z in zonas_x]

        fig_jugador = go.Figure()

        # Barras jugador
        fig_jugador.add_trace(go.Bar(
            x=zonas_x,
            y=valores_y,
            name=f"Goles jugador {jugador}"
        ))

        # Línea media equipo
        fig_jugador.add_trace(go.Scatter(
            x=zonas_x,
            y=media_y,
            mode="lines+markers",
            name="Media equipo"
        ))

        fig_jugador.update_layout(
            height=350,
            title=f"Jugador {jugador}",
            xaxis_title="Zona de lanzamiento",
            yaxis_title="Número de goles"
        )

        st.plotly_chart(
            fig_jugador,
            use_container_width=True,
            key=f"grafico_{equipo}_{jugador}"
        )

        # ================================
        # 🔵 BOLAS RESUMEN EN LÍNEA
        # ================================

        total, pct_iz, pct_dcha = resumen_jugador(match["events"], equipo, jugador)
        resumen_zonas = resumen_jugador_por_zona(match["events"], equipo, jugador)

        import plotly.graph_objects as go

        fig_resumen = go.Figure()

        x_pos = 0
        separacion = 0.12  # espacio entre bolas

        # ----------------
        # 🔵 BOLA TOTAL
        # ----------------
        fig_resumen.add_trace(go.Scatter(
            x=[x_pos],
            y=[0.5],
            mode="markers+text",
            marker=dict(
                size=60,
                color="blue" if team == "A" else "red"
            ),
            text=[f"{total}<br>{pct_dcha}% / {pct_iz}%"],
            textfont=dict(color="white", size=11),
            textposition="middle center",
            showlegend=False
        ))

        # título
        fig_resumen.add_annotation(
            x=x_pos,
            y=0.9,
            text="<b>TOTAL</b>",
            showarrow=False,
            font=dict(size=11, color="black")
        )

        x_pos += separacion

        # ----------------
        # 🔵 BOLAS POR ZONA
        # ----------------
        orden_zonas = ["EI", "LI", "C", "LD", "ED", "EXI", "EXD"]

        for zona in orden_zonas:
            if zona not in resumen_zonas:
                continue
            data = resumen_zonas[zona]

            total_z = data["total"]
            if total_z == 0:
                continue

            pct_iz_z = int((data["IZ"] / total_z) * 100) if total_z > 0 else 0
            pct_dcha_z = int((data["DCHA"] / total_z) * 100) if total_z > 0 else 0

            fig_resumen.add_trace(go.Scatter(
                x=[x_pos],
                y=[0.5],
                mode="markers+text",
                marker=dict(
                    size=50,
                    color="blue" if team == "A" else "red"
                ),
                text=[f"{total_z}<br>{pct_dcha_z}% / {pct_iz_z}%"],
                textfont=dict(color="white", size=10),
                textposition="middle center",
                showlegend=False
            ))

            # título zona (EI, C, ED, etc.)
            fig_resumen.add_annotation(
                x=x_pos,
                y=0.9,
                text=f"<b>{zona}</b>",
                showarrow=False,
                font=dict(size=10, color="black")
            )

            x_pos += separacion

        # ----------------
        # LAYOUT
        # ----------------
        fig_resumen.update_xaxes(visible=False, range=[-0.05, 1])
        fig_resumen.update_yaxes(visible=False, range=[0, 1])

        fig_resumen.update_layout(
            height=140,
            margin=dict(l=0, r=0, t=0, b=0)
        )

        st.plotly_chart(
            fig_resumen,
            use_container_width=True,
            key=f"resumen_{equipo}_{jugador}"
        )
