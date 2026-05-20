from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Any
import json

# Brand colors
PURPLE = colors.HexColor("#6F12FF")
PURPLE_DARK = colors.HexColor("#5201CF")
PURPLE_DARKEST = colors.HexColor("#39018E")
GRAY_LIGHT = colors.HexColor("#F2F2F2")
GRAY_MID = colors.HexColor("#EDEDED")
TEXT_DARK = colors.HexColor("#252525")
TEXT_MED = colors.HexColor("#323232")
WHITE = colors.white

W, H = A4


def star_rating_text(score: float) -> str:
    if score is None:
        return "—"
    labels = {1: "Muito abaixo", 2: "Abaixo", 3: "Atende", 4: "Acima", 5: "Muito acima"}
    rounded = round(score)
    stars = "★" * rounded + "☆" * (5 - rounded)
    return f"{stars}  {score:.2f}  ({labels.get(rounded, '')} da expectativa)"


def score_color(score: float):
    if score is None:
        return colors.grey
    if score >= 4.5:
        return colors.HexColor("#22c55e")
    if score >= 3.5:
        return colors.HexColor("#84cc16")
    if score >= 2.5:
        return colors.HexColor("#f59e0b")
    if score >= 1.5:
        return colors.HexColor("#f97316")
    return colors.HexColor("#ef4444")


def build_header(elements, styles, user_name: str, position: str, department: str, cycle_name: str):
    # Purple header bar
    header_data = [[
        Paragraph(f"<font color='white'><b>AVD 360°</b> — Grupo Gestão</font>", styles["header_title"]),
        Paragraph(f"<font color='white'>Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</font>",
                  styles["header_date"]),
    ]]
    header_table = Table(header_data, colWidths=[120 * mm, 60 * mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PURPLE),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 8 * mm))

    # Cycle name
    elements.append(Paragraph(f"Ciclo: {cycle_name}", styles["cycle_label"]))
    elements.append(Spacer(1, 3 * mm))

    # Employee info box
    info_data = [[
        Paragraph(f"<b>{user_name}</b>", styles["emp_name"]),
        Paragraph(f"{position}<br/><font color='#6F12FF'>{department}</font>", styles["emp_info"]),
    ]]
    info_table = Table(info_data, colWidths=[100 * mm, 80 * mm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRAY_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("PADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))


def build_summary_scores(elements, styles, summary: Dict):
    elements.append(Paragraph("Resumo Geral", styles["section_title"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=PURPLE, spaceAfter=4 * mm))

    cols = ["Tipo de Avaliador", "Qtd. Avaliações", "Média Geral"]
    rows = [cols]

    for label, key in [("Autoavaliação", "self"), ("Pares", "peers"), ("Superiores", "managers"), ("Geral", "overall")]:
        data = summary.get(key, {})
        count = data.get("count", 0)
        score = data.get("avg")
        score_str = f"{score:.2f}" if score else "—"
        rows.append([label, str(count), score_str])

    t = Table(rows, colWidths=[70 * mm, 40 * mm, 70 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GRAY_MID]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EDE9FF")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))


def build_competency_chart(elements, styles, comp_scores: List[Dict]):
    if not comp_scores:
        return

    elements.append(Paragraph("Desempenho por Competência", styles["section_title"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=PURPLE, spaceAfter=4 * mm))

    # Bar chart
    drawing = Drawing(180 * mm, max(80, len(comp_scores) * 14) * mm)
    chart = VerticalBarChart()
    chart.x = 10 * mm
    chart.y = 10 * mm
    chart.width = 155 * mm
    chart.height = max(60, len(comp_scores) * 12) * mm
    chart.data = [[s["avg"] for s in comp_scores if s.get("avg")]]
    chart.categoryAxis.categoryNames = [s["name"][:30] for s in comp_scores if s.get("avg")]
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 5
    chart.valueAxis.valueStep = 1
    chart.bars[0].fillColor = PURPLE
    chart.bars[0].strokeColor = None
    chart.categoryAxis.labels.angle = 30
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.labels.fontSize = 8
    drawing.add(chart)
    elements.append(drawing)
    elements.append(Spacer(1, 4 * mm))

    # Table detail
    rows = [["Competência", "Grupo", "Auto", "Pares", "Média"]]
    for s in comp_scores:
        rows.append([
            s.get("name", "")[:45],
            s.get("group", "")[:20],
            f"{s['self']:.1f}" if s.get("self") else "—",
            f"{s['peers']:.1f}" if s.get("peers") else "—",
            f"{s['avg']:.2f}" if s.get("avg") else "—",
        ])

    t = Table(rows, colWidths=[70 * mm, 40 * mm, 20 * mm, 20 * mm, 20 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GRAY_MID]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))


def build_comments_section(elements, styles, evaluations: List[Dict]):
    elements.append(Paragraph("Comentários e Observações", styles["section_title"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=PURPLE, spaceAfter=4 * mm))

    for ev in evaluations:
        evaluator_label = ev.get("evaluator_name", "Avaliador")
        rel = ev.get("relationship", "Par")
        ev_type = f"[{rel}] {evaluator_label}"

        block = []
        block.append(Paragraph(ev_type, styles["eval_name"]))

        for ans in ev.get("answers", []):
            if ans.get("comment"):
                block.append(Paragraph(
                    f"<b>{ans['competency']}:</b> {ans['comment']}",
                    styles["comment_text"]
                ))

        if ev.get("general_observations"):
            block.append(Paragraph(
                f"<b>Observações gerais:</b> {ev['general_observations']}",
                styles["obs_text"]
            ))

        if len(block) > 1:
            elements.append(KeepTogether(block))
            elements.append(Spacer(1, 3 * mm))


def generate_individual_report(
    user_name: str,
    position: str,
    department: str,
    cycle_name: str,
    summary: Dict,
    comp_scores: List[Dict],
    evaluations: List[Dict],
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=10 * mm,
        bottomMargin=15 * mm,
    )

    base_styles = getSampleStyleSheet()
    styles = {
        "header_title": ParagraphStyle("ht", fontSize=14, textColor=WHITE, fontName="Helvetica-Bold"),
        "header_date": ParagraphStyle("hd", fontSize=8, textColor=WHITE, alignment=TA_RIGHT),
        "cycle_label": ParagraphStyle("cl", fontSize=10, textColor=PURPLE_DARK, fontName="Helvetica-Bold"),
        "emp_name": ParagraphStyle("en", fontSize=14, textColor=TEXT_DARK, fontName="Helvetica-Bold"),
        "emp_info": ParagraphStyle("ei", fontSize=10, textColor=TEXT_MED),
        "section_title": ParagraphStyle("st", fontSize=13, textColor=PURPLE_DARKEST, fontName="Helvetica-Bold",
                                        spaceBefore=4 * mm),
        "eval_name": ParagraphStyle("evn", fontSize=9, textColor=PURPLE_DARK, fontName="Helvetica-Bold",
                                    backColor=colors.HexColor("#F0EBFF"), leftIndent=4,
                                    spaceAfter=2, spaceBefore=4),
        "comment_text": ParagraphStyle("ct", fontSize=8, textColor=TEXT_MED, leftIndent=8, spaceAfter=2),
        "obs_text": ParagraphStyle("ot", fontSize=8, textColor=TEXT_DARK, leftIndent=8,
                                   backColor=GRAY_LIGHT, spaceAfter=2),
    }

    elements = []
    build_header(elements, styles, user_name, position, department, cycle_name)
    build_summary_scores(elements, styles, summary)
    build_competency_chart(elements, styles, comp_scores)
    build_comments_section(elements, styles, evaluations)

    doc.build(elements)
    return buffer.getvalue()
