# app.py - Versión completa para AGUSTINOSMARCADOR (Streamlit)
import streamlit as st
from PIL import Image
import pandas as pd
import plotly.graph_objects as go
import datetime, json
from io import BytesIO
from streamlit_autorefresh import st_autorefresh

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
        'started_at': None,   # iso str
        'paused_at': None,    # iso str
        'elapsed_before_pause': 0.0
    }

match = st.session_state.match

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
    if match['started_at'] is None:
        return 0
    start = datetime.datetime.fromisoformat(match['started_at'])
    elapsed = (datetime.datetime.utcnow() - start).total_seconds() + match.get('elapsed_before_pause', 0.0)
    if match.get('paused_at'):
        # if paused, subtract time since paused
        paused = datetime.datetime.fromisoformat(match['paused_at'])
        elapsed = (paused - start).total_seconds() + match.get('elapsed_before_pause', 0.0)
    return max(0, int(elapsed))

def start_match():
    if match['started_at'] is None:
        match['started_at'] = datetime.datetime.utcnow().isoformat()
        match['paused_at'] = None
        match['elapsed_before_pause'] = 0.0
    elif match['paused_at'] is not None:
        # resume
        paused = datetime.datetime.fromisoformat(match['paused_at'])
        diff = (datetime.datetime.utcnow() - paused).total_seconds()
        match['elapsed_before_pause'] += diff
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

    zone_counts = compute_zone_counts()
    xs, ys, sizes, labels = [], [], [], []
    for z, cnt in zone_counts.items():
        if z in ZONE_COORDS:
            x,y = ZONE_COORDS[z]
            xs.append(x); ys.append(y)
            sizes.append(8 + cnt*6)
            labels.append(f"Z{z}: {cnt}")

    fig = go.Figure()
    if court:
        fig.add_layout_image(dict(source=court, xref="x", yref="y", x=0, y=1, sizex=1, sizey=1, sizing="stretch", layer="below"))
    if xs:
        fig.add_trace(go.Scatter(x=xs, y=ys, text=labels, textposition="top center", mode="markers+text",
                                 marker=dict(size=sizes, color='rgba(255,0,0,0.6)')))
    fig.update_xaxes(showgrid=False, visible=False, range=[0,1])
    fig.update_yaxes(showgrid=False, visible=False, range=[0,1], scaleanchor="x")
    fig.update_layout(height=440, margin=dict(l=0,r=0,t=0,b=0))
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
