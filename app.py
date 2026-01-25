# app.py - Versión completa para AGUSTINOSMARCADOR (Streamlit)
import streamlit as st
from PIL import Image
import pandas as pd
import plotly.graph_objects as go
import datetime, json
from io import BytesIO
from streamlit_autorefresh import st_autorefresh

# --- GitHub token desde Streamlit Secrets ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]


st.set_page_config(page_title="AGUSTINOS MARCADOR", layout="wide", page_icon="🏐")

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
DEFAULT_EXCLUSION_SECONDS = 120   # 2 minutos
DEFAULT_MATCH_SECONDS = 30 * 60  # 30 minutos - ajustar si quieres mitades

# Coordenadas relativas para 9 zonas (x,y en 0..1). Ajustables.
ZONE_COORDS = {
    1: (0.12, 0.92), 2: (0.5, 0.92), 3: (0.88, 0.92),
    4: (0.12, 0.62), 5: (0.5, 0.62), 6: (0.88, 0.62),
    7: (0.12, 0.32), 8: (0.5, 0.32), 9: (0.88, 0.32),
}

# ---------------------------
# ESTADO (persistente en sesión)
# ---------------------------
if 'match' not in st.session_state:
    st.session_state.match = {
        'scoreA': 0,
        'scoreB': 0,
        'events': [],         # lista de dicts {time, team, zone, player}
        'exclusions': [],     # lista de dicts {player, team, started_at, ends_at}
        'started_at': datetime.datetime.now().isoformat(),
        'paused_at': None,    # iso str
        'elapsed_before_pause': 0.0
    }

match = st.session_state.match

# auto-refresh para actualizar la UI cada segundo (1000 ms)
# esto provoca que Streamlit vuelva a ejecutar el script periódicamente y así el reloj y exclusiones se actualicen visualmente
if "search_results" not in st.session_state:
    st.session_state.search_results = None
st_autorefresh(interval=1000, limit=None, key="auto_refresh")

# ---------------------------
# UTILIDADES
# ---------------------------
def iso_now():
    return datetime.datetime.utcnow().isoformat()

def add_goal(team, zone, player=None):
    try:
        zone = int(zone)
    except Exception:
        zone = 0
    ev = {'time': iso_now(), 'team': team, 'zone': zone, 'player': player}
    match['events'].append(ev)
    if team == 'A':
        match['scoreA'] += 1
    else:
        match['scoreB'] += 1

def add_exclusion(player, team, duration=DEFAULT_EXCLUSION_SECONDS):
    start = datetime.datetime.utcnow()
    ends = start + datetime.timedelta(seconds=duration)
    ex = {'player': str(player), 'team': team, 'started_at': start.isoformat(), 'duration': duration, 'ends_at': ends.isoformat()}
    match['exclusions'].append(ex)

def now_elapsed_seconds():
    match = st.session_state.match

    started_at = match.get("started_at")

    # Si no hay inicio válido
    if not started_at or not isinstance(started_at, str):
        return int(match.get("elapsed_before_pause", 0))

    try:
        start = datetime.datetime.fromisoformat(started_at)
    except Exception:
        # started_at corrupto → lo ignoramos
        return int(match.get("elapsed_before_pause", 0))

    # Si está pausado
    if match.get("paused_at"):
        try:
            paused = datetime.datetime.fromisoformat(match["paused_at"])
            return int(match.get("elapsed_before_pause", 0) + (paused - start).total_seconds())
        except Exception:
            return int(match.get("elapsed_before_pause", 0))

    # En marcha
    return int(match.get("elapsed_before_pause", 0) + (datetime.datetime.utcnow() - start).total_seconds())


def start_match():
    # iniciar desde cero
    if match['started_at'] is None:
        match['started_at'] = datetime.datetime.utcnow().isoformat()
        match['paused_at'] = None
        match['elapsed_before_pause'] = 0.0
        return

    # reanudar tras pausa
    if match['paused_at'] is not None:
        paused = datetime.datetime.fromisoformat(match['paused_at'])
        start = datetime.datetime.fromisoformat(match['started_at'])
        match['elapsed_before_pause'] += (paused - start).total_seconds()
        match['started_at'] = datetime.datetime.utcnow().isoformat()
        match['paused_at'] = None


def pause_match():
    if match['started_at'] is None:
        return
    match['paused_at'] = datetime.datetime.utcnow().isoformat()

def reset_match():
    match['scoreA'] = 0
    match['scoreB'] = 0
    match['events'] = []
    match['exclusions'] = []
    match['started_at'] = None
    match['paused_at'] = None
    match['elapsed_before_pause'] = 0.0


def cleanup_expired_exclusions():
    now = datetime.datetime.utcnow()
    active = []
    expired = []
    for ex in match['exclusions']:
        ends = datetime.datetime.fromisoformat(ex['ends_at'])
        if ends > now:
            active.append(ex)
        else:
            expired.append(ex)
    match['exclusions'] = active
    return expired

def compute_zone_counts():
    counts = {}
    for ev in match['events']:
        z = int(ev.get('zone', 0) or 0)
        counts[z] = counts.get(z, 0) + 1
    return counts

def events_df():
    if not match['events']:
        return pd.DataFrame(columns=['time','team','zone','player'])
    return pd.DataFrame(match['events'])

# ---------------------------
# INTERFAZ
# ---------------------------
st.title("🏐 AGUSTINOS - Marcador y Heatmap")
st.markdown("Usa esta app desde tu iPad / móvil / PC. Todo gratis (Streamlit).")

left, mid, right = st.columns([1,1,1])

with left:
    st.subheader("Marcador")
    st.markdown(f"**Equipo A:** {match['scoreA']}  —  **Equipo B:** {match['scoreB']}")
    zone = st.selectbox("Zona (1..9)", options=list(ZONE_COORDS.keys()), index=4)
    player = st.text_input("Jugador (opcional)", key="player_input")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Gol Equipo A"):
            add_goal('A', zone, player or None)
    with col2:
        if st.button("Gol Equipo B"):
            add_goal('B', zone, player or None)
    st.write("---")
    if st.button("Reiniciar partido"):
        reset_match()

with mid:
    st.subheader("Tiempo y exclusiones")
    elapsed = now_elapsed_seconds()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    st.markdown(f"**Tiempo transcurrido:** {minutes:02d}:{seconds:02d}")
    rc1, rc2 = st.columns(2)
    with rc1:
        if st.button("Iniciar / Reanudar"):
            start_match()
    with rc2:
        if st.button("Pausar"):
            pause_match()
    st.write("---")
    with st.form("form_add_ex"):
        pnum = st.text_input("Jugador para exclusión (nº)", key="ex_player")
        equipo_ex = st.selectbox("Equipo", options=['A','B'], key="ex_team")
        dur = st.number_input("Duración (segundos)", min_value=10, max_value=600, value=DEFAULT_EXCLUSION_SECONDS, key="ex_dur")
        if st.form_submit_button("Añadir exclusión"):
            if pnum:
                add_exclusion(pnum, equipo_ex, int(dur))
            else:
                st.warning("Indica el nº del jugador.")

    st.write("Exclusiones activas:")
    cleanup_expired_exclusions()
    if match['exclusions']:
        ex_table = []
        for ex in match['exclusions']:
            ends = datetime.datetime.fromisoformat(ex['ends_at'])
            rem = max(0, int((ends - datetime.datetime.utcnow()).total_seconds()))
            mm = rem//60; ss = rem%60
            ex_table.append({'player': ex['player'], 'team': ex['team'], 'remaining': f"{mm:02d}:{ss:02d}"})
        st.table(pd.DataFrame(ex_table))
    else:
        st.write("No hay exclusiones activas.")

with right:
    st.subheader("Mapa de calor - Zonas")
    # carga imagen pista (si existe)
    try:
        court = Image.open("static/court.png")
    except Exception:
        court = None

# ---- Mapa de calor mejorado: puntos por equipo ----
zone_counts_A = {}
zone_counts_B = {}
# separar eventos por equipo y contar por zona
for ev in match['events']:
    try:
        z = int(ev.get('zone', 0) or 0)
    except:
        z = 0
    if ev.get('team') == 'A':
        zone_counts_A[z] = zone_counts_A.get(z, 0) + 1
    else:
        zone_counts_B[z] = zone_counts_B.get(z, 0) + 1

xsA, ysA, sizesA, textsA = [], [], [], []
xsB, ysB, sizesB, textsB = [], [], [], []

for z, cnt in zone_counts_A.items():
    if z in ZONE_COORDS:
        x,y = ZONE_COORDS[z]
        xsA.append(x); ysA.append(y)
        sizesA.append(8 + cnt*6)
        textsA.append(f"A Z{z}: {cnt}")

for z, cnt in zone_counts_B.items():
    if z in ZONE_COORDS:
        x,y = ZONE_COORDS[z]
        xsB.append(x); ysB.append(y)
        sizesB.append(8 + cnt*6)
        textsB.append(f"B Z{z}: {cnt}")

fig = go.Figure()

if court is not None:
    fig.add_layout_image(dict(source=court, xref="x", yref="y", x=0, y=1, sizex=1, sizey=1, sizing="stretch", layer="below"))

# Equipo A - azul
if xsA:
    fig.add_trace(go.Scatter(
        x=xsA, y=ysA, mode='markers+text', name='Equipo A',
        text=textsA, textposition='top center',
        marker=dict(size=sizesA, color='rgba(0,102,204,0.7)', line=dict(width=1, color='rgba(0,0,0,0.4)'))
    ))
# Equipo B - rojo
if xsB:
    fig.add_trace(go.Scatter(
        x=xsB, y=ysB, mode='markers+text', name='Equipo B',
        text=textsB, textposition='top center',
        marker=dict(size=sizesB, color='rgba(220,20,60,0.7)', line=dict(width=1, color='rgba(0,0,0,0.4)'))
    ))

fig.update_xaxes(showgrid=False, visible=False, range=[0,1])
fig.update_yaxes(showgrid=False, visible=False, range=[0,1], scaleanchor="x")
fig.update_layout(height=440, margin=dict(l=0,r=0,t=0,b=0), legend=dict(orientation="h"))
st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# PANEL INFERIOR: EVENTOS, IMPORT, EXPORT
# ---------------------------
st.markdown("***")
st.subheader("Eventos registrados")
df_ev = events_df()
st.dataframe(df_ev)

colA, colB = st.columns([1,1])
with colA:
    if st.button("Exportar CSV de eventos"):
        if not df_ev.empty:
            csv = df_ev.to_csv(index=False).encode('utf-8')
            st.download_button("Descargar CSV", csv, file_name="eventos_partido.csv", mime="text/csv")
        else:
            st.info("No hay eventos para exportar.")
with colB:
    if st.button("Exportar JSON (partido)"):
        data = json.dumps(match, default=str).encode('utf-8')
        st.download_button("Descargar JSON", data, file_name="partido.json", mime="application/json")

st.markdown("**Importar LongoMatch (CSV)**")
lm = st.file_uploader("Sube CSV LongoMatch (opcional)", type=['csv'])
if lm is not None:
    try:
        lmdf = pd.read_csv(lm)
        st.write("Vista previa CSV LongoMatch (primeras filas):")
        st.dataframe(lmdf.head())
        if st.button("Importar CSV como eventos"):
            imported = 0
            # Intento mapeo flexible: columnas comunes
            for _, row in lmdf.iterrows():
                team = row.get('Team') or row.get('team') or row.get('Equipo') or 'A'
                zone = row.get('Zone') or row.get('zone') or row.get('Zona') or 5
                player = row.get('Player') or row.get('player') or row.get('Jugador') or None
                add_goal(str(team)[0], int(zone), player)
                imported += 1
            st.success(f"Importados {imported} eventos.")
    except Exception as e:
        st.error(f"Error al leer CSV: {e}")

st.markdown("***")
st.caption("App creada para AGUSTINOS. Si quieres ajustar zonas, cronómetro o añadir sonido, dime y lo adapto.")
# --- Histórico y guardado en GitHub ---
from modules import recorder, loader, stats, pdf_export
import streamlit as st
import json, os
from datetime import datetime

# Datos del repo (rellena con tu usuario y repo)
GITHUB_OWNER = "BALONMANOAGUSTINOSMARCADOR"
GITHUB_REPO = "AGUSTINOSMARCADOR"

# Token lo leeremos desde secrets (no lo pegues en el código)
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", None)
if not GITHUB_TOKEN:
    st.warning("No hay GITHUB_TOKEN en Streamlit Secrets. Para guardar partidos necesitas configurar el token. (Ver instrucciones).")

st.markdown("---")
st.subheader("Guardar / Histórico")

# info del partido
rival = st.text_input("Rival", key="input_rival")
competicion = st.text_input("Competición (opcional)", key="input_comp")
guardar_btn = st.button("💾 Finalizar y Guardar partido")

if guardar_btn:
    # construir objeto partido
    partido = {
        "fecha": datetime.utcnow().isoformat(),
        "rival": rival or "Desconocido",
        "competicion": competicion or "",
        "scoreA": match['scoreA'],
        "scoreB": match['scoreB'],
        "events": match['events'],
        "exclusions": match['exclusions'],
        "elapsed_seconds": now_elapsed_seconds()
    }
    # path: data/partidos/20251130_181200_Agustinos_vs_Rival.json
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_rival = "".join(c for c in (rival or "rival") if c.isalnum() or c in ("_", "-")).strip()
    filename = f"data/partidos/{ts}_Agustinos_vs_{safe_rival}.json"
    if not GITHUB_TOKEN:
        st.error("No hay token. No se puede guardar en GitHub.")
    else:
        status, res = recorder.guardar_partido_github(GITHUB_OWNER, GITHUB_REPO, filename, partido, GITHUB_TOKEN)
        if status in (200,201):
            st.success("Partido guardado en GitHub correctamente.")
        else:
            st.error(f"Error guardando partido en GitHub: {status} - {res}")

# Mostrar histórico por rival (opción de búsqueda)
st.markdown("### Buscar en histórico por RIVAL")
buscar_rival = st.text_input("Nombre del rival a buscar", key="search_rival")
if st.button("Buscar partidos"):
    partidos = loader.cargar_partidos_local()  # lee data/partidos.json local si existe
    # Además, intentar listar archivos en data/partidos/ si usamos guardado por archivos individuales
    # Filtrar por rival en filename o en contenido
    matches = []
    # primero contenido del partidos.json global
    for p in partidos:
        if buscar_rival.strip().lower() in p.get("rival","").lower():
            matches.append(p)
      st.session_state.search_results = matches
    # si guardamos por archivos individuales (data/partidos/*), intentamos leerlos
    import glob, os
    local_files = glob.glob("data/partidos/*.json")
    for f in local_files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                p = json.load(fh)
                if buscar_rival.strip().lower() in p.get("rival","").lower():
                    matches.append(p)
        except Exception:
            pass
    if not matches:
        st.info("No se han encontrado partidos con ese rival.")
    else:
        st.success(f"Encontrados {len(matches)} partidos.")
        for p in matches:
            st.write("---")
            st.write(f"Fecha: {p.get('fecha')}")
            st.write(f"Rival: {p.get('rival')}")
            st.write(f"Resultado: {p.get('scoreA')} - {p.get('scoreB')}")
            if st.button(f"Generar PDF: {p.get('fecha')}", key=f"pdf_{p.get('fecha')}"):
                pdf_bytes = pdf_export.generar_pdf_partido(p)
                st.download_button("Descargar PDF", data=pdf_bytes, file_name=f"partido_{p.get('fecha')}.pdf", mime="application/pdf")
