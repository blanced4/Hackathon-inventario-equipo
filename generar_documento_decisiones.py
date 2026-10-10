import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(36, 22, "RETO HACKATECNM · SERVICIO DE INVENTARIO INTELIGENTE · ARQUITECTURA DE DATOS")
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(612 - 36, 22, page_str)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 32, 612 - 36, 32)
        self.restoreState()

def build_pdf(filename="Documento_de_Decisiones_HackaTecNM.pdf"):
    # Target: Exactly 1 Page (Letter: 612 x 792 pt). Margins: 34 pt horizontal, 28 pt vertical
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=26,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    header_title = ParagraphStyle(
        'HeaderTitle',
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=15,
        textColor=colors.HexColor('#0F172A')
    )
    
    header_subtitle = ParagraphStyle(
        'HeaderSubtitle',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0284C7')
    )

    meta_text = ParagraphStyle(
        'MetaText',
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#475569')
    )

    sec_title = ParagraphStyle(
        'SecTitle',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=1
    )

    body = ParagraphStyle(
        'Body',
        fontName='Helvetica',
        fontSize=7.3,
        leading=9.5,
        textColor=colors.HexColor('#1E293B')
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.3,
        textColor=colors.HexColor('#1E293B'),
        leftIndent=8
    )

    story = []

    # 1. Header Box
    header_data = [
        [
            Paragraph("<b>DOCUMENTO DE DECISIONES DE ARQUITECTURA</b>", header_title),
            Paragraph("<b>EQUIPO SPINDLE-OS</b><br/>Reto Almacén Inteligente HackaTecNM", ParagraphStyle('RAlign', parent=meta_text, alignment=2))
        ],
        [
            Paragraph("SERVICIO DE MICROINVENTARIO REACTIVO BASADO EN KAFKA & POSTGRESQL", header_subtitle),
            Paragraph("Evaluación Técnica: Sección 5.5 (15 pts)", ParagraphStyle('RAlign2', parent=meta_text, alignment=2))
        ]
    ]
    t_header = Table(header_data, colWidths=[360, 180])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor('#0F172A'), spaceBefore=1, spaceAfter=4))

    # Helper function to render a clean decision block
    def make_section(num, title, badge, content_p, bullets):
        head = [
            [
                Paragraph(f"<b>{num}. {title}</b>", sec_title),
                Paragraph(f"<b>{badge}</b>", ParagraphStyle('Badge', fontName='Helvetica-Bold', fontSize=6.5, textColor=colors.HexColor('#0369A1'), alignment=2))
            ]
        ]
        t_sec = Table(head, colWidths=[430, 110])
        t_sec.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        
        box_data = [[t_sec], [Paragraph(content_p, body)]]
        for b in bullets:
            box_data.append([Paragraph(f"• <b>{b[0]}:</b> {b[1]}", bullet_style)])
            
        t_box = Table(box_data, colWidths=[540])
        t_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor('#CBD5E1')),
            ('LINEBELOW', (0,0), (-1,0), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        return t_box

    # Q1: Relación de compras con el catálogo
    q1_text = (
        "Las remisiones y órdenes de compra de proveedores presentan nomenclaturas heterogéneas, albaranes imprecisos y códigos "
        "con caracteres especiales (comas, diagonales o espacios). La correspondencia con el catálogo se gestiona mediante un "
        "pipeline determinista multietapa complementado con buffer de desacoplamiento:"
    )
    q1_bullets = [
        ("Normalización Canónica", "Limpieza de strings (stripping, colapso de whitespace, uppercase) preservando signos estructurales válidos según §5 del contrato (ej. 'TOR, CAB, BAJA', '7014 CTA/P4'). Búsqueda primaria indexada por SKU exacto y secundaria por catálogo de partes."),
        ("Resolución de Ambigüedades y SKUs Duplicados", "Si el número de parte coincide con múltiples registros o no tiene match directo en el catálogo, la compra no se descarta ni corrompe el Kardex: se ingresa a la tabla <b>unmatched_receipts</b> con estatus 'pending'."),
        ("Asociación Asistida e IA", "Los arribos no resueltos se someten a inferencia semántica con Gemini AI (o heurística de similitud Levenshtein). La resolución oficial ejecuta un POST /purchasing/unmatched-receipts/{id}/resolve ingresando stock a la bahía U-100 y desbloqueando faltantes en el mismo ciclo.")
    ]
    story.append(make_section("1", "¿CÓMO RELACIONAN COMPRAS CON EL CATÁLOGO?", "NORMALIZACIÓN + QUARANTINE BUFFER", q1_text, q1_bullets))
    story.append(Spacer(1, 4))

    # Q2: Manejo de kits
    q2_text = (
        "En el reacondicionamiento de husillos de alta precisión, la demanda ocurre tanto a nivel de ensambles cerrados como por "
        "reemplazo de componentes individuales desgastados durante la inspección. La arquitectura adopta una estrategia híbrida "
        "fundamentada en <b>group_name</b>:"
    )
    q2_bullets = [
        ("Granularidad Elemental en Kardex", "El inventario físico y los movimientos contables (inventory_movements) se llevan estrictamente a nivel de <b>componente individual (part_id)</b>. Esto previene stock fantasma y permite reutilizar piezas sueltas de husillos desensamblados."),
        ("Agrupación Lógica vía group_name", "Los kits se modelan en las líneas de ensamble (bom_lines) compartiendo su <b>group_name</b> (ej. 'RODAMIENTOS', 'SELLOS'). Durante la inspección rápida, se identifican las necesidades unitarias requeridas ('buy', 'scrap')."),
        ("Reabasto y Balance de Ensambles", "Las sugerencias de reabastecimiento consolidan faltantes por <b>group_name</b> para emitir compras conjuntas a proveedores especializados, pero el ingreso y reservas operan sobre cada ítem elemental, garantizando no-negatividad.")
    ]
    story.append(make_section("2", "¿CÓMO MANEJAN KITS Y COMPONENTES?", "DESPIECE GRANULAR + BOM GROUP_NAME", q2_text, q2_bullets))
    story.append(Spacer(1, 4))

    # Q3: Prevención de reservas dobles
    q3_text = (
        "La inspección de órdenes y la reasignación de materiales pueden ocurrir en paralelo desde múltiples terminales o mediante "
        "re-inspecciones sucesivas. Para garantizar la invariante de disponibilidad no-negativa y eliminar condiciones de carrera:"
    )
    q3_bullets = [
        ("Aislamiento ACID con Bloqueo Pesimista", "Toda reserva o asignación se ejecuta bajo transacciones PostgreSQL con <b>SELECT ... FOR UPDATE</b> sobre los registros de stock y reservas de la pieza afectada, serializando accesos concurrentes a nivel de fila."),
        ("Semántica de Reemplazo Atómico (Regla 2)", "Una re-inspección para una misma orden y bom_line_id <b>no acumula reservas</b>; ejecuta un UPSERT atómico que cancela/sustituye la reserva activa previa, liberando sobrantes de inmediato al inventario disponible."),
        ("Cálculo Atómico de Disponibilidad", "La disponibilidad disponible = max(0, on_hand - sum(reservas_activas)) se evalúa dentro del mismo lock de base de datos. Ninguna reserva procede si excede el saldo en estanterías; el déficit se canaliza automáticamente a la tabla shortages.")
    ]
    story.append(make_section("3", "¿CÓMO EVITAN RESERVAS DOBLES?", "ACID + SELECT FOR UPDATE + REEMPLAZO ATÓMICO", q3_text, q3_bullets))
    story.append(Spacer(1, 4))

    # Q4: Garantía de idempotencia
    q4_text = (
        "La red Kafka entrega mensajes con garantía <i>at-least-once</i>. Desconexiones del consumidor, replays de tópicos o reintentos "
        "de red pueden retransmitir eventos ya procesados. Para asegurar consistencia inmutable:"
    )
    q4_bullets = [
        ("Tabla Transaccional processed_events", "Cada mensaje consumido extrae su <b>event_id</b> (o compuesto único de negocio) y lo inserta en una tabla de control protegida por clave primaria: <code>PRIMARY KEY (event_id)</code>."),
        ("Efecto Transaccional Atómico", "La persistencia del event_id y la mutación de estado (movimiento en Kardex, reserva o faltante) ocurren en la <b>misma transacción de base de datos</b>. Si el evento ya existe, la inserción genera colisión y se descarta (no-op)."),
        ("Reconstrucción Determinista (Compare Pass)", "Al reiniciar el servicio con base vacía y releer los tópicos desde offset 0 (Regla 22), el procesamiento ordenado replica el libro mayor exacto, superando la prueba oficial <code>snapshot & compare</code> con 0 divergencias.")
    ]
    story.append(make_section("4", "¿CÓMO GARANTIZAN IDEMPOTENCIA?", "AT-LEAST-ONCE + PROCESSED_EVENTS EN MISMA TX", q4_text, q4_bullets))

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado exitosamente: {filename}")

if __name__ == "__main__":
    build_pdf()
