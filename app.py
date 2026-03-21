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

ZONA_NOMBRE_A_ID = {v: k for k, v in ZONAS.items()}

# Bloque para modificaciones
modificaciones_activo = True

# 🔁 Refresco automático del reloj mientras el partido esté activo
if st.session_state.get("partido_activo", False):
    st_autorefresh(interval=1000, key="auto_refresh_reloj")

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
        "players_stats": {  # Nuevo: historial de jugadores
            "A": {},  # estructura: {numero_jugador: {"exclusiones": 0, "amarilla":0, "roja":0, "azul":0, "avisos":[]}}
            "B": {}
        },
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
        "exclusions": [],
        "started_at": None,
        "elapsed_before_pause": 0,
        "part": 1
    }

def add_goal(team, zone, player=None, finta=None):
    m = st.session_state.match

    if player and jugador_inhabilitado(player, team):
        return

    if player:
        stats = m["players_stats"][team].get(player)
        if stats and stats.get("inhabilitado"):
            st.error(f"🚫 JUGADOR Nº {player} NO PUEDE PARTICIPAR EN EL PARTIDO")
            return

    m["events"].append({
        "time": iso_now(),
        "team": team,
        "zone": ZONAS[int(zone)],
        "player": player,
        "finta": finta  # 👈 NUEVO CAMPO
    })

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

    # Mostrar nombres y goles grandes
    st.markdown(
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

    
    # Botones de goles uno al lado del otro
    col_gol_a, col_gol_b = st.columns(2, gap="small")

    with col_gol_a:
        if st.button(f"Gol {match['teamA']}"):
            if finta is None:
                st.warning("⚠️ Debes seleccionar tipo de finta")
            else:
                add_goal("A", zone, player, finta)

    with col_gol_b:
        if st.button(f"Gol {match['teamB']}"):
            if finta is None:
                st.warning("⚠️ Debes seleccionar tipo de finta")
            else:
                add_goal("B", zone, player, finta)

# -------- TIEMPO + EXCLUSIONES --------
with mid:
    st.subheader("🚫 Exclusiones")

    # ⏱️ TIEMPO DE PARTIDO
    t = elapsed_seconds()
    reloj_display = st.empty()
    reloj_display.markdown(f"## {t//60:02d}:{t%60:02d}")

    col_pause, col_resume = st.columns(2)
    with col_pause:
        if st.button("⏸ Pausar"):
            pause_match()
            st.rerun()
    with col_resume:
        if st.button("▶ Reanudar"):
            start_match()
            st.rerun()

    # Mostrar exclusiones activas
    exs = active_exclusions()
    if exs:
        for ex in exs:
            mm = ex["remaining"] // 60
            ss = ex["remaining"] % 60
            stats = match["players_stats"][ex["team"]].get(ex["player"], {"exclusiones": 0})
            count = stats["exclusiones"]
            st.markdown(
                f"**{ex['player']}** ({count}) | "
                f"{match['teamA'] if ex['team']=='A' else match['teamB']} | "
                f"⏱ {mm:02d}:{ss:02d}"
            )
    else:
        st.write("—")

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
                text=f"{pct_dcha}%",
                font=dict(size=10),
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
                text=f"{pct_iz}%",
                font=dict(size=10),
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
                text=f"{pct_dcha}%",
                font=dict(size=10),
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
                text=f"{pct_iz}%",
                font=dict(size=10),
            )


# ejecutar para ambos equipos
draw_fintas("A")
draw_fintas("B")

    st.plotly_chart(fig, use_container_width=True)

# Modificaciones permitidas solo si el reloj NO está corriendo
modificaciones_habilitadas = match["started_at"] is None

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

    # 🔹 Función para dibujar gráfico de un equipo
    def plot_goals_team(team_key, team_name, color):
        data = player_goals[team_key]

        # 🔹 Filtrar solo jugadores con goles
        data_filtered = {j: g for j, g in data.items() if g > 0}

        if not data_filtered:
            st.write(f"— No hay goles registrados para {team_name}")
            return

        # 🔹 Ordenar de mayor a menor
        jugadores_sorted = sorted(data_filtered.items(), key=lambda x: x[1], reverse=True)
        jugadores = [j for j, g in jugadores_sorted]
        goles = [g for j, g in jugadores_sorted]

        # 🔹 Crear gráfico
        fig = go.Figure(go.Bar(
            x=jugadores,
            y=goles,
            marker_color=color,
            width=0.8
        ))

        fig.update_layout(
            title=f"Goles por jugador - {team_name}",
            xaxis_title="Jugador",
            yaxis_title="Goles",
            xaxis=dict(tickangle=-90),  # Números en vertical
            bargap=0,  # Sin separación entre barras
            height=400,
            showlegend=False
        )

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

        st.plotly_chart(fig_jugador, use_container_width=True)
