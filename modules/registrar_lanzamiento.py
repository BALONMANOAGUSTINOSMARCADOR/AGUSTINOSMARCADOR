from streamlit_plotly_events import plotly_events
import streamlit as st
import plotly.graph_objects as go


def registrar_lanzamiento(match):

    st.markdown("## ⚽ Registro del lanzamiento")

    col_campo, col_porteria = st.columns([2.3, 1.2], gap="large")

    with col_campo:
        st.info("Aquí irá el campo de balonmano")

    with col_porteria:

        st.info("Aquí irá la portería")

        fig = go.Figure()

        # Marco
        fig.add_shape(
            type="rect",
            x0=0, y0=0,
            x1=3, y1=3,
            line=dict(color="black", width=4)
        )

        # Verticales
        fig.add_shape(type="line", x0=1, y0=0, x1=1, y1=3)
        fig.add_shape(type="line", x0=2, y0=0, x1=2, y1=3)

        # Horizontales
        fig.add_shape(type="line", x0=0, y0=1, x1=3, y1=1)
        fig.add_shape(type="line", x0=0, y0=2, x1=3, y1=2)

        zonas = {
            1:(0.5,2.5),2:(1.5,2.5),3:(2.5,2.5),
            4:(0.5,1.5),5:(1.5,1.5),6:(2.5,1.5),
            7:(0.5,0.5),8:(1.5,0.5),9:(2.5,0.5)
        }

        # Zona seleccionada
        zona_actual = st.session_state.match.get("selected_goal_zone")        

        # Coordenadas de cada sector de la portería
        SECTORES_PORTERIA = {
            1: (0, 2),
            2: (1, 2),
            3: (2, 2),
            4: (0, 1),
            5: (1, 1),
            6: (2, 1),
            7: (0, 0),
            8: (1, 0),
            9: (2, 0),
        }

        for zona, (cx, cy) in SECTORES_PORTERIA.items():

            color = "#F2F2F2"

            if zona_actual == zona:
                color = "#2ECC71"

            fig.add_shape(
                type="rect",
                x0=cx,
                y0=cy,
                x1=cx + 1,
                y1=cy + 1,
                fillcolor=color,
                line=dict(color="black", width=2),
            )

            fig.add_annotation(
                x=cx + 0.5,
                y=cy + 0.5,
                text=f"<b>{zona}</b>",
                showarrow=False,
                font=dict(size=20, color="black"),
            )
        
        fig.update_xaxes(
            visible=False,
            range=[0,3]
        )

        fig.update_yaxes(
            visible=False,
            range=[0,3],
            scaleanchor="x",
            scaleratio=1
        )

        fig.update_layout(
            height=330,
            margin=dict(l=0,r=0,t=0,b=0)
        )

        selected = plotly_events(
            fig,
            click_event=True,
            hover_event=False,
            select_event=False,
            override_height=330,
            override_width="100%"
        )
