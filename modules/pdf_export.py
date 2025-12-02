from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle, Image
from pathlib import Path
from datetime import datetime
import io

BASE = Path(__file__).parent.parent

def generar_pdf_partido(partido, filepath=None):
    """
    partido: dict con keys: fecha, events, exclusions, home, away, etc.
    Devuelve bytes del PDF o lo guarda en filepath si se indica.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Colores Agustinos: ejemplo azul oscuro y rojo (ajusta si quieres)
    color_prim = colors.HexColor("#003399")  # azul
    color_sec = colors.HexColor("#cc0000")   # rojo

    # Título
    c.setFillColor(color_prim)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(30*mm, (height - 30*mm), f"AGUSTINOS - Partido {partido.get('fecha','')}")
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.black)
    c.drawString(30*mm, (height - 40*mm), f"Resultado: {partido.get('scoreA','?')} - {partido.get('scoreB','?')}")

    # Tabla simple de resumen
    events = partido.get("events", [])[:100]
    data = [["Tiempo", "Equipo", "Jugador", "Zona", "Tipo"]]
    for e in events:
        t = e.get("time","")
        team = e.get("team","")
        player = e.get("player","")
        zone = str(e.get("zone",""))
        tipo = e.get("type","goal")
        data.append([t, team, player, zone, tipo])
    table = Table(data, colWidths=[60*mm,20*mm,40*mm,20*mm,30*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), color_prim),
        ('TEXTCOLOR',(0,0),(-1,0), colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey)
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, 20*mm, (height - 120*mm))

    c.showPage()
    c.save()
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()

    if filepath:
        with open(filepath, "wb") as f:
            f.write(pdf_bytes)
        return filepath
    return pdf_bytes
