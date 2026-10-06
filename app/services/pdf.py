from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, CondPageBreak
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from xml.sax.saxutils import escape as xml_escape
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


def _esc(text) -> str:
    return xml_escape(str(text or "")).replace("\n", "<br/>")


def _wrap_label(text: str, font: str, size: float, width: float, max_lines: int = 3) -> List[str]:
    lines = simpleSplit(text or "", font, size, width) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and stringWidth(last + "…", font, size) > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


def _competency_chart_drawing(comp_scores: List[Dict]) -> Drawing:
    """Horizontal bar chart drawn by hand so the competency labels are never clipped."""
    total_w = 180 * mm
    label_w = 68 * mm
    bar_x = label_w + 4 * mm
    bar_w = total_w - bar_x - 12 * mm
    font, font_size, line_h = "Helvetica", 7.5, 9
    axis_h = 8 * mm
    pad = 2 * mm

    rows = []
    for s in comp_scores:
        lines = _wrap_label(s.get("name", ""), font, font_size, label_w)
        row_h = max(7 * mm, len(lines) * line_h + 6)
        rows.append((s, lines, row_h))

    total_h = sum(r[2] for r in rows) + axis_h + pad
    d = Drawing(total_w, total_h)
    top = total_h - pad
    bottom = axis_h

    # Gridlines and axis labels (0 to 5)
    for v in range(6):
        x = bar_x + bar_w * v / 5
        d.add(Line(x, bottom, x, top, strokeColor=colors.HexColor("#DDDDDD"), strokeWidth=0.5))
        d.add(String(x, bottom - 10, str(v), fontName=font, fontSize=8,
                     fillColor=TEXT_MED, textAnchor="middle"))
    d.add(Line(bar_x, bottom, bar_x, top, strokeColor=colors.HexColor("#999999"), strokeWidth=0.7))

    y = top
    for s, lines, row_h in rows:
        center = y - row_h / 2
        # Label right-aligned against the axis, vertically centred on the bar
        first_baseline = center + (len(lines) - 1) * line_h / 2 - font_size / 3
        for i, line in enumerate(lines):
            d.add(String(label_w, first_baseline - i * line_h, line, fontName=font,
                         fontSize=font_size, fillColor=TEXT_DARK, textAnchor="end"))
        avg = s.get("avg")
        if avg is not None:
            bh = min(row_h - 4, 5 * mm)
            bw = bar_w * min(avg, 5) / 5
            d.add(Rect(bar_x, center - bh / 2, bw, bh, fillColor=PURPLE, strokeColor=None))
            d.add(String(bar_x + bw + 3, center - 3, f"{avg:.2f}", fontName="Helvetica-Bold",
                         fontSize=8, fillColor=TEXT_DARK))
        else:
            d.add(String(bar_x + 3, center - 3, "sem nota", fontName=font, fontSize=7,
                         fillColor=colors.grey))
        y -= row_h
    return d


def build_competency_chart(elements, styles, comp_scores: List[Dict]):
    if not comp_scores:
        return

    elements.append(Paragraph("Desempenho por Competência", styles["section_title"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=PURPLE, spaceAfter=4 * mm))
    elements.append(Paragraph("Média de pontuação por competência (escala de 1 a 5)", styles["chart_caption"]))

    # Split long lists so each drawing fits on a single page
    chunk = 18
    for i in range(0, len(comp_scores), chunk):
        elements.append(_competency_chart_drawing(comp_scores[i:i + chunk]))
        elements.append(Spacer(1, 3 * mm))
    elements.append(Spacer(1, 2 * mm))

    # Table detail
    rows = [["Competência", "Grupo", "Auto", "Pares", "Média"]]
    for s in comp_scores:
        rows.append([
            Paragraph(_esc(s.get("name", "")), styles["cell"]),
            Paragraph(_esc(s.get("group", "")), styles["cell"]),
            f"{s['self']:.1f}" if s.get("self") else "—",
            f"{s['peers']:.1f}" if s.get("peers") else "—",
            f"{s['avg']:.2f}" if s.get("avg") else "—",
        ])

    t = Table(rows, colWidths=[75 * mm, 45 * mm, 20 * mm, 20 * mm, 20 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GRAY_MID]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6 * mm))


def build_evaluations_section(elements, styles, evaluations: List[Dict]):
    if not evaluations:
        return

    # Avoid leaving the section title stranded at the bottom of a page
    elements.append(CondPageBreak(70 * mm))
    elements.append(Paragraph("Avaliações Individuais", styles["section_title"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=PURPLE, spaceAfter=4 * mm))

    muted_dash = "<font color='#999999'>—</font>"
    for ev in evaluations:
        avg = ev.get("avg")
        avg_txt = f"  ·  média {avg:.2f}" if avg is not None else ""
        header = Paragraph(
            f"[{_esc(ev.get('relationship', 'Par'))}] {_esc(ev.get('evaluator_name', 'Avaliador'))}{avg_txt}",
            styles["eval_name"],
        )

        answers = ev.get("answers", [])
        rows = [["Competência", "Nota", "Observação"]]
        for ans in answers:
            score = ans.get("score")
            rows.append([
                Paragraph(_esc(ans.get("competency", "")), styles["cell"]),
                Paragraph(f"<font color='#{score_color(score).hexval()[2:]}'>{score:g}</font>"
                          if score is not None else "—", styles["score_cell"]),
                Paragraph(_esc(ans.get("comment")) or muted_dash, styles["cell"]),
            ])

        style = [
            ("BACKGROUND", (0, 0), (-1, 0), PURPLE_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GRAY_MID]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]
        t = Table(rows, colWidths=[62 * mm, 16 * mm, 102 * mm], repeatRows=1)
        t.setStyle(TableStyle(style))

        obs_body = _esc(ev.get("general_observations")) or "<font color='#999999'>Sem observação final.</font>"
        obs = Table([[Paragraph(f"<b>Observação final:</b><br/>{obs_body}", styles["obs_text"])]],
                    colWidths=[180 * mm])
        obs.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0EBFF")),
            ("LINEBEFORE", (0, 0), (0, -1), 2, PURPLE),
            ("PADDING", (0, 0), (-1, -1), 8),
        ]))

        # Keep the evaluator name glued to the start of its table
        header.keepWithNext = True
        elements.append(header)
        elements.append(Spacer(1, 2 * mm))
        elements.append(t)
        elements.append(Spacer(1, 4 * mm))
        elements.append(obs)
        elements.append(Spacer(1, 8 * mm))


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
        "eval_name": ParagraphStyle("evn", fontSize=10, textColor=PURPLE_DARKEST, fontName="Helvetica-Bold",
                                    spaceBefore=2),
        "cell": ParagraphStyle("cell", fontSize=8, leading=10, textColor=TEXT_DARK),
        "chart_caption": ParagraphStyle("cc", fontSize=8, textColor=TEXT_MED, spaceAfter=2 * mm),
        "score_cell": ParagraphStyle("sc", fontSize=9, leading=11, fontName="Helvetica-Bold",
                                     alignment=TA_CENTER),
        "obs_text": ParagraphStyle("ot", fontSize=8.5, leading=11, textColor=TEXT_DARK),
    }

    elements = []
    build_header(elements, styles, user_name, position, department, cycle_name)
    build_summary_scores(elements, styles, summary)
    build_competency_chart(elements, styles, comp_scores)
    build_evaluations_section(elements, styles, evaluations)

    doc.build(elements)
    return buffer.getvalue()


def generate_report_from_data(data: Dict) -> bytes:
    """Builds the PDF from the dict returned by aggregate_report_data."""
    u = data["user"]
    cycle = data["cycle"]
    return generate_individual_report(
        user_name=u.name,
        position=u.position or "—",
        department=u.department or "—",
        cycle_name=cycle.name if cycle else "—",
        summary=data["summary"],
        comp_scores=data["comp_scores"],
        evaluations=data["evaluations"],
    )
