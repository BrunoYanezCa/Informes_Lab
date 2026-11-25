from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.report_models import LaboratoryReport
from src.pag_results import (
    calculate_epa_dha,
    calculate_inverse_ratio,
    format_pag_analyte_name,
    format_pag_result,
)
from src.report_i18n import format_date, is_english, parse_date, translate


ORANGE = colors.HexColor("#FF6216")
LIGHT_GRAY = colors.HexColor("#DFDFDF")
GRID_GRAY = colors.HexColor("#9A9A9A")


class NumberedCanvas(canvas.Canvas):
    def __init__(
        self,
        *args: Any,
        signature_path: Path | None = None,
        signature_name: str = "",
        signature_title: str = "",
        issue_date: str = "",
        issue_location: str = "",
        language: str = "es",
        page_size: tuple[float, float] = A4,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._page_states: list[dict[str, Any]] = []
        self._signature_path = signature_path
        self._signature_name = signature_name
        self._signature_title = signature_title
        self._issue_date = issue_date
        self._issue_location = issue_location
        self._language = language
        self._sheet_size = page_size

    def showPage(self) -> None:
        self._page_states.append(dict(self.__dict__))
        cast(Any, self)._startPage()

    def save(self) -> None:
        total_pages = len(self._page_states)
        for page_index, state in enumerate(self._page_states):
            self.__dict__.update(state)
            self.saveState()
            self.setFont("Helvetica", 7)
            self.setFillColor(colors.black)
            self.drawRightString(
                self._sheet_size[0] - 15 * mm,
                self._sheet_size[1] - 43 * mm,
                (
                    f"Page {self.getPageNumber()} of {total_pages}"
                    if is_english(self._language)
                    else f"Página {self.getPageNumber()} de {total_pages}"
                ),
            )
            if page_index == total_pages - 1:
                self._draw_signature()
            self.restoreState()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_signature(self) -> None:
        if self._signature_path and self._signature_path.is_file():
            image_width, image_height = ImageReader(str(self._signature_path)).getSize()
            scale = min(42 * mm / image_width, 15.6 * mm / image_height)
            rendered_width = image_width * scale
            rendered_height = image_height * scale
            center_x = self._sheet_size[0] - 40 * mm
            self.drawImage(
                str(self._signature_path),
                center_x - rendered_width / 2,
                41.9 * mm + (15.6 * mm - rendered_height) / 2,
                width=rendered_width,
                height=rendered_height,
                anchor="sw",
                mask="auto",
            )
        self.setFillColor(colors.black)
        self.setFont("Helvetica-Bold", 6.5)
        self.drawCentredString(self._sheet_size[0] - 40 * mm, 39 * mm, self._signature_name)
        self.setFont("Helvetica", 6)
        self.drawCentredString(self._sheet_size[0] - 40 * mm, 35.5 * mm, self._signature_title)
        if self._issue_location and self._issue_date:
            issue_line = f"{self._issue_location}, {self._issue_date}"
        else:
            issue_line = self._issue_location or self._issue_date
        if issue_line:
            self.drawCentredString(self._sheet_size[0] - 40 * mm, 30 * mm, issue_line)


def _paragraph(value: Any, style: Any) -> Paragraph:
    text = "" if value is None else str(value)
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _date_range(records: list[Any]) -> tuple[str, str]:
    starts = [parse_date(record.start_date) for record in records if record.start_date]
    ends = [parse_date(record.end_date) for record in records if record.end_date]
    valid_starts = [value for value in starts if value is not None]
    valid_ends = [value for value in ends if value is not None]
    return (
        min(valid_starts).isoformat() if valid_starts else "",
        max(valid_ends).isoformat() if valid_ends else "",
    )


def format_issue_date(value: str | date | datetime, language: str = "es") -> str:
    parsed = parse_date(value)
    if parsed is None:
        return str(value or "").strip()
    if is_english(language):
        months = (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        )
        return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"
    months = (
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    )
    return f"{parsed.day} de {months[parsed.month - 1]} del {parsed.year}"


def _draw_template_frame(
    report: LaboratoryReport,
    settings: dict[str, Any],
    styles: Any,
    logo_path: Path,
    page_canvas: canvas.Canvas,
    document: SimpleDocTemplate,
) -> None:
    page_canvas.saveState()
    width, height = document.pagesize
    if logo_path.is_file():
        page_canvas.drawImage(
            str(logo_path),
            15 * mm,
            height - 37 * mm,
            width=47 * mm,
            height=21 * mm,
            preserveAspectRatio=True,
            anchor="sw",
            mask="auto",
        )
    page_canvas.setFont("Helvetica", 12)
    page_canvas.setFillColor(colors.black)
    report_reference = report.metadata.sample_code.strip()
    report_title = translate("Informe de Laboratorio", report.language)
    page_canvas.drawCentredString(
        width / 2,
        height - 29 * mm,
        f"{report_title}: {report_reference}",
    )
    page_canvas.setStrokeColor(ORANGE)
    page_canvas.setLineWidth(0.6)
    page_canvas.line(15 * mm, height - 45 * mm, width - 15 * mm, height - 45 * mm)

    result_statement = translate(
        settings.get("institutional_footer", {}).get("results_statement", ""),
        report.language,
    )
    if result_statement:
        page_canvas.setFont("Helvetica-Bold", 7)
        page_canvas.drawCentredString(width / 2, 24 * mm, result_statement)

    y = 21 * mm
    legal_notices = settings.get("legal_notices", {})
    for notice in (legal_notices.get("terms", ""), legal_notices.get("validity", "")):
        if not notice:
            continue
        notice = translate(notice, report.language)
        paragraph = _paragraph(notice, styles["Legal"])
        _, paragraph_height = paragraph.wrap(width - 30 * mm, 17 * mm)
        y -= paragraph_height
        paragraph.drawOn(page_canvas, 15 * mm, y)
        y -= 1.2 * mm
    page_canvas.setStrokeColor(colors.black)
    page_canvas.setLineWidth(0.45)
    page_canvas.line(15 * mm, y - 0.3 * mm, width - 15 * mm, y - 0.3 * mm)

    footer = settings.get("institutional_footer", {})
    footer_columns = [
        (footer.get("name", "SGS Chile Ltda."), 27 * mm, "#FF8040", True),
        (footer.get("address", ""), 66 * mm, "#000000", False),
        (footer.get("phone", ""), 28 * mm, "#000000", False),
        (footer.get("fax", ""), 27 * mm, "#000000", False),
        (footer.get("website", ""), 32 * mm, "#000000", False),
    ]
    footer_cells = []
    footer_widths = []
    for value, cell_width, color, bold in footer_columns:
        value = translate(str(value), report.language)
        emphasis = "<b>" if bold else ""
        closing = "</b>" if bold else ""
        footer_cells.append(
            Paragraph(
                f'<font color="{color}">{emphasis}{escape(str(value))}{closing}</font>',
                styles["Footer"],
            )
        )
        footer_widths.append(cell_width)
    footer_table = Table([footer_cells], colWidths=footer_widths, hAlign="LEFT")
    footer_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    footer_table.wrapOn(page_canvas, width - 30 * mm, 8 * mm)
    footer_table.drawOn(page_canvas, 15 * mm, 8 * mm)
    membership = _paragraph(footer.get("membership", ""), styles["Membership"])
    membership.wrap(width - 30 * mm, 6 * mm)
    membership.drawOn(page_canvas, 15 * mm, 3 * mm)
    page_canvas.restoreState()


def _metadata_table(report: LaboratoryReport, styles: Any) -> Table:
    metadata = report.metadata
    starts, ends = _date_range(report.results)
    t = lambda value: translate(value, report.language)
    rows = [
        [_paragraph(t("Datos del Cliente"), styles["MetaSection"]), "", "", ""],
        [
            _paragraph(t("Análisis solicitado por:"), styles["MetaLabel"]),
            _paragraph(metadata.requested_by, styles["MetaValue"]),
            _paragraph(t("Nombre de Contacto:"), styles["MetaLabel"]),
            _paragraph(metadata.contact, styles["MetaValue"]),
        ],
        [
            _paragraph(t("Dirección:"), styles["MetaLabel"]),
            _paragraph(metadata.sampling_address, styles["MetaValue"]),
            "",
            "",
        ],
        [_paragraph(t("Datos de la muestra"), styles["MetaSection"]), "", "", ""],
        [
            _paragraph(t("Producto:"), styles["MetaLabel"]),
            _paragraph(metadata.product, styles["MetaValue"]),
            _paragraph(t("Lote:"), styles["MetaLabel"]),
            _paragraph(metadata.lot, styles["MetaValue"]),
        ],
        [
            _paragraph(t("Contenedor:"), styles["MetaLabel"]),
            _paragraph(metadata.container, styles["MetaValue"]),
            _paragraph(t("Nº de Guía:"), styles["MetaLabel"]),
            _paragraph(metadata.guide_number or metadata.client_reference, styles["MetaValue"]),
        ],
        [
            _paragraph(t("Muestreado Por:"), styles["MetaLabel"]),
            _paragraph(metadata.sampled_by, styles["MetaValue"]),
            _paragraph(t("Fecha de Muestreo:"), styles["MetaLabel"]),
            _paragraph(format_date(metadata.sampling_date), styles["MetaValue"]),
        ],
        [
            _paragraph(t("Fecha de Recepción:"), styles["MetaLabel"]),
            _paragraph(format_date(metadata.reception_date), styles["MetaValue"]),
            _paragraph(t("Fecha de Inicio Ensayo:"), styles["MetaLabel"]),
            _paragraph(format_date(starts), styles["MetaValue"]),
        ],
        [
            _paragraph(t("Fecha de Término Ensayo:"), styles["MetaLabel"]),
            _paragraph(format_date(ends), styles["MetaValue"]),
            _paragraph(t("Solicitud de Análisis:"), styles["MetaLabel"]),
            _paragraph(metadata.request_number, styles["MetaValue"]),
        ],
    ]
    table = Table(rows, colWidths=[41 * mm, 47 * mm, 41 * mm, 43 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("SPAN", (1, 2), (3, 2)),
        ("SPAN", (0, 0), (-1, 0)),
        ("SPAN", (0, 3), (-1, 3)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.2),
        ("TOPPADDING", (0, 0), (-1, -1), 1.1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1),
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GRAY),
        ("BACKGROUND", (0, 3), (-1, 3), LIGHT_GRAY),
        ("LINEBELOW", (0, 0), (-1, 0), 0.35, GRID_GRAY),
        ("LINEBELOW", (0, 3), (-1, 3), 0.35, GRID_GRAY),
        ("LINEBELOW", (0, -1), (-1, -1), 0.35, GRID_GRAY),
    ]))
    return table


def _results_table(records: list[Any], styles: Any) -> Table:
    headings = ("Analito", "Resultado", "Unidades", "L.D.", "L.C.")
    data = [[_paragraph(label, styles["TableHeading"]) for label in headings]]
    for record in records:
        data.append([
            _paragraph(record.analyte, styles["ResultCell"]),
            _paragraph(record.result, styles["ResultCell"]),
            _paragraph(record.unit, styles["ResultCell"]),
            _paragraph(record.detection_limit, styles["ResultCell"]),
            _paragraph(record.quantification_limit, styles["ResultCell"]),
        ])
    table = Table(data, colWidths=[64 * mm, 35 * mm, 34 * mm, 23.5 * mm, 23.5 * mm], repeatRows=1, splitByRow=1)
    commands = [
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, ORANGE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, GRID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]
    for row_index in range(2, len(data), 2):
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), LIGHT_GRAY))
    table.setStyle(TableStyle(commands))
    return table


def _is_pag_record(record: Any) -> bool:
    return (
        record.analysis_code.casefold() == "pag"
        or record.analysis_name.casefold() in {"perfil ácidos grasos", "perfil de ácidos grasos"}
    )


def _global_pag_limits(records: list[Any]) -> tuple[str, str]:
    detection_limit = ""
    quantification_limit = ""
    for record in records:
        detection_limit = detection_limit or str(record.detection_limit or "").strip()
        quantification_limit = quantification_limit or str(record.quantification_limit or "").strip()
        if detection_limit and quantification_limit:
            break
    return detection_limit, quantification_limit


def _general_results_table(
    records: list[Any], report: LaboratoryReport, styles: Any, available_width: float
) -> Table:
    headings = ("ANÁLISIS", "RESULTADO", "UNIDAD", "L.D.", "L.C.")
    data = [[_paragraph(translate(label, report.language), styles["TableHeading"]) for label in headings]]
    pag_groups: dict[str, list[Any]] = {}
    for record in records:
        if _is_pag_record(record):
            pag_groups.setdefault(record.analysis_name, []).append(record)
            continue
        data.append([
            _paragraph(translate(record.analyte or record.analysis_name, report.language), styles["ResultCell"]),
            _paragraph(record.result, styles["ResultCell"]),
            _paragraph(record.unit, styles["ResultCell"]),
            _paragraph(record.detection_limit, styles["ResultCell"]),
            _paragraph(record.quantification_limit, styles["ResultCell"]),
        ])
    for analysis_name, pag_records in pag_groups.items():
        units = list(dict.fromkeys(record.unit for record in pag_records if record.unit))
        detection_limit, quantification_limit = _global_pag_limits(pag_records)
        data.append([
            _paragraph(translate("Perfil de Ácidos Grasos", report.language), styles["ResultCell"]),
            _paragraph(translate("Ver detalle", report.language), styles["ResultCell"]),
            _paragraph(" / ".join(units), styles["ResultCell"]),
            _paragraph(detection_limit, styles["ResultCell"]),
            _paragraph(quantification_limit, styles["ResultCell"]),
        ])
        data.append([
            _paragraph("EPA+DHA", styles["ResultCell"]),
            _paragraph(calculate_epa_dha(pag_records), styles["ResultCell"]),
            _paragraph("% Area", styles["ResultCell"]),
            _paragraph("", styles["ResultCell"]),
            _paragraph("", styles["ResultCell"]),
        ])
    widths = [available_width * ratio for ratio in (0.34, 0.20, 0.18, 0.14, 0.14)]
    table = Table(data, colWidths=widths, repeatRows=1, splitByRow=1)
    commands = [
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, ORANGE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, GRID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for row_index in range(2, len(data), 2):
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), LIGHT_GRAY))
    table.setStyle(TableStyle(commands))
    return table


def _pag_results_table(
    records: list[Any], styles: Any, available_width: float, language: str = "es"
) -> Table:
    units = list(dict.fromkeys(record.unit for record in records if record.unit))
    data = [[
        _paragraph(translate("Analito", language), styles["TableHeading"]),
        *[_paragraph(unit, styles["TableHeading"]) for unit in units],
    ]]
    category_rows: list[int] = []
    result_rows: list[int] = []
    grouped: dict[str, list[Any]] = {}
    analyte_order: list[str] = []
    for record in records:
        key = record.analyte.casefold()
        if key not in grouped:
            grouped[key] = []
            analyte_order.append(key)
        grouped[key].append(record)

    previous_category = ""
    for analyte_key in analyte_order:
        analyte_records = grouped[analyte_key]
        category = next((
            str(record.original_values.get("category", "")).strip()
            for record in analyte_records
            if record.original_values.get("category")
        ), "")
        if category.casefold() == "totales":
            category = "Totales"
        category = translate(category, language)
        if category and category.casefold() != previous_category.casefold():
            data.append([
                _paragraph(category, styles["PagGroup"]),
                *[_paragraph("", styles["PagGroup"]) for _ in units],
            ])
            category_rows.append(len(data) - 1)
        previous_category = category or previous_category
        by_unit = {record.unit.casefold(): record for record in analyte_records}
        data.append([
            _paragraph(format_pag_analyte_name(analyte_records[0].analyte), styles["ResultCell"]),
            *[
                _paragraph(format_pag_result(record.result if record else ""), styles["ResultCell"])
                for unit in units
                for record in (by_unit.get(unit.casefold()),)
            ],
        ])
        result_rows.append(len(data) - 1)

        if analyte_records[0].analyte.strip().casefold() == "w6/w3":
            inverse_cells = []
            for unit in units:
                unit_records = [record for record in analyte_records if record.unit.casefold() == unit.casefold()]
                inverse_cells.append(
                    _paragraph(calculate_inverse_ratio(unit_records), styles["ResultCell"])
                )
            data.append([_paragraph("W3/W6", styles["ResultCell"]), *inverse_cells])
            result_rows.append(len(data) - 1)

    label_width = min(53 * mm, available_width * 0.32)
    result_width = (available_width - label_width) / max(len(units), 1)
    table = Table(
        data,
        colWidths=[label_width, *([result_width] * len(units))],
        repeatRows=1,
        splitByRow=1,
    )
    commands = [
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, ORANGE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, GRID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]
    for row_index in category_rows:
        commands.extend([
            ("SPAN", (0, row_index), (-1, row_index)),
            ("BACKGROUND", (0, row_index), (-1, row_index), LIGHT_GRAY),
            ("LINEBELOW", (0, row_index), (-1, row_index), 0.5, GRID_GRAY),
        ])
    for stripe, row_index in enumerate(result_rows):
        if stripe % 2:
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), LIGHT_GRAY))
    table.setStyle(TableStyle(commands))
    return table


def _method_summary_table(
    records: list[Any], styles: Any, available_width: float, language: str = "es"
) -> Table:
    entries = dict.fromkeys(
        (
            "Perfil de Ácidos Grasos" if _is_pag_record(record) else record.analysis_name,
            record.method_code,
            record.method_description,
        )
        for record in records
    )
    data = [[
        _paragraph(translate("Ensayos", language), styles["TableHeading"]),
        _paragraph(translate("Método/Título", language), styles["TableHeading"]),
    ]]
    for analysis_name, method_code, method_description in entries:
        method_text = " - ".join(value for value in (method_code, method_description) if value)
        data.append([
            _paragraph(translate(analysis_name, language), styles["MethodCell"]),
            _paragraph(method_text, styles["MethodCell"]),
        ])
    table = Table(
        data,
        colWidths=[43 * mm, available_width - 43 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, ORANGE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, GRID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def _horizontal_analysis_section(
    records: list[Any],
    report: LaboratoryReport,
    styles: Any,
    available_width: float,
) -> list[Any] | None:
    result_keys = [(record.analyte.casefold(), record.unit.casefold()) for record in records]
    if not records or len(records) > 5 or len(set(result_keys)) != len(result_keys):
        return None

    label_width = 43 * mm
    result_width = (available_width - label_width) / len(records)
    column_widths = [label_width, *([result_width] * len(records))]
    section_style = styles["SectionCell"]

    method_table = _method_summary_table(records, styles, available_width)

    matrix_rows = [[
        _paragraph("Análisis", styles["MatrixLabel"]),
        *[_paragraph(record.analyte, section_style) for record in records],
    ], [
        _paragraph("Unidades", styles["MatrixLabel"]),
        *[_paragraph(record.unit, section_style) for record in records],
    ], [
        _paragraph("L.D.", styles["MatrixLabel"]),
        *[_paragraph(record.detection_limit, section_style) for record in records],
    ], [
        _paragraph("L.C.", styles["MatrixLabel"]),
        *[_paragraph(record.quantification_limit, section_style) for record in records],
    ], [
        _paragraph("Identificación de Muestras", styles["MatrixLabel"]),
        *[_paragraph("", section_style) for _ in records],
    ]]
    sample_identity = report.metadata.sample_description or report.metadata.sample_code
    matrix_rows.append([
        _paragraph(sample_identity, styles["SampleIdentity"]),
        *[_paragraph(record.result, section_style) for record in records],
    ])
    matrix_table = Table(matrix_rows, colWidths=column_widths, hAlign="LEFT")
    matrix_commands = [
        ("GRID", (0, 0), (-1, -1), 0.3, GRID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 4), (-1, 4), 0.8, ORANGE),
    ]
    matrix_table.setStyle(TableStyle(matrix_commands))
    return [method_table, Spacer(1, 2 * mm), matrix_table]


def _execution_dates_table(report: LaboratoryReport, styles: Any) -> Table:
    data = [[
        _paragraph(translate("Análisis", report.language), styles["DateHeading"]),
        _paragraph(translate("Fecha Inicio", report.language), styles["DateHeading"]),
        _paragraph(translate("Fecha Término (Validación)", report.language), styles["DateHeading"]),
    ]]
    for analysis_name in report.selected_analyses:
        records = [
            item for item in report.results
            if item.include and item.analysis_name == analysis_name
        ]
        start, end = _date_range(records)
        data.append([
            _paragraph(translate(analysis_name, report.language), styles["DateCell"]),
            _paragraph(format_date(start), styles["DateCell"]),
            _paragraph(format_date(end), styles["DateCell"]),
        ])
    table = Table(data, colWidths=[90 * mm, 45 * mm, 45 * mm], repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, GRID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def generate_pdf(report: LaboratoryReport, settings: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    page_size = letter if settings.get("page_size") == "LETTER" else A4
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="MetaLabel", fontName="Helvetica", fontSize=8, leading=9.5, textColor=colors.black))
    styles.add(ParagraphStyle(name="MetaValue", fontName="Helvetica", fontSize=8, leading=9.5, textColor=colors.black))
    styles.add(ParagraphStyle(name="MetaSection", fontName="Helvetica-Bold", fontSize=8.5, leading=10, textColor=colors.black))
    styles.add(ParagraphStyle(name="Notice", fontName="Helvetica", fontSize=7, leading=8.5, alignment=TA_JUSTIFY, textColor=colors.black, spaceBefore=2))
    styles.add(ParagraphStyle(name="NoteLabel", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=colors.black, spaceBefore=4))
    styles.add(ParagraphStyle(name="SectionHeading", fontName="Times-Roman", fontSize=10, leading=12, textColor=colors.black, spaceBefore=5, spaceAfter=2))
    styles.add(ParagraphStyle(name="AnalysisHeading", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=ORANGE, spaceBefore=4, spaceAfter=1))
    styles.add(ParagraphStyle(name="Method", fontName="Helvetica", fontSize=7, leading=9, textColor=colors.black, spaceAfter=2))
    styles.add(ParagraphStyle(name="TableHeading", fontName="Helvetica-Bold", fontSize=6.5, leading=8, textColor=ORANGE))
    styles.add(ParagraphStyle(name="MethodCell", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.black))
    styles.add(ParagraphStyle(name="MatrixLabel", fontName="Helvetica-Bold", fontSize=7, leading=8, textColor=ORANGE, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="SectionCell", fontName="Times-Roman", fontSize=7.5, leading=9, textColor=colors.black))
    styles.add(ParagraphStyle(name="SampleIdentity", fontName="Times-Roman", fontSize=7.5, leading=9, textColor=colors.black))
    styles.add(ParagraphStyle(name="ResultCell", fontName="Times-Roman", fontSize=9.5, leading=11, textColor=colors.black))
    styles.add(ParagraphStyle(name="DateHeading", fontName="Times-Roman", fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.black))
    styles.add(ParagraphStyle(name="DateCell", fontName="Times-Roman", fontSize=7.5, leading=9, textColor=colors.black))
    styles.add(ParagraphStyle(name="Legend", fontName="Times-Roman", fontSize=7, leading=9, textColor=colors.black))
    styles.add(ParagraphStyle(name="PagGroup", fontName="Helvetica-Bold", fontSize=7, leading=8.5, textColor=colors.black))
    styles.add(ParagraphStyle(name="Signature", fontName="Helvetica-Bold", fontSize=6.5, leading=8, alignment=TA_CENTER, textColor=colors.black))
    styles.add(ParagraphStyle(name="Legal", fontName="Times-Roman", fontSize=5.8, leading=7, alignment=TA_JUSTIFY, textColor=colors.black))
    styles.add(ParagraphStyle(name="Footer", fontName="Helvetica", fontSize=5.6, leading=6.5, textColor=colors.black))
    styles.add(ParagraphStyle(name="Membership", fontName="Helvetica-Bold", fontSize=5.4, leading=6, alignment=TA_CENTER, textColor=colors.black))

    document = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=45 * mm,
        bottomMargin=47 * mm,
        title=f"Informe {report.metadata.sample_code.strip()}",
    )
    project_root = Path(__file__).resolve().parents[1]
    assets = settings.get("assets", {})
    logo_path = project_root / assets.get("logo", "assets/logo.png")
    signature_path = project_root / assets.get("signature", "assets/signature.jpeg")

    def draw_page(page_canvas: canvas.Canvas, doc: SimpleDocTemplate) -> None:
        _draw_template_frame(report, settings, styles, logo_path, page_canvas, doc)

    story = [
        _metadata_table(report, styles),
        Spacer(1, 1 * mm),
        _paragraph(
            translate(settings.get("legal_notices", {}).get("sample_condition", ""), report.language),
            styles["Notice"],
        ),
    ]
    if report.metadata.observations:
        story.extend([
            Spacer(1, 8.5 * mm),
            _paragraph(translate("Notas:", report.language), styles["NoteLabel"]),
            _paragraph(report.metadata.observations, styles["Method"]),
        ])
    story.append(Spacer(1, 3 * mm))

    selected_records = [
        record for record in report.results
        if record.include and record.analysis_name in report.selected_analyses
    ]
    available_width = page_size[0] - document.leftMargin - document.rightMargin
    pag_records = [record for record in selected_records if _is_pag_record(record)]
    story.extend([
        _paragraph(translate("Análisis / Metodología", report.language), styles["SectionHeading"]),
        _method_summary_table(selected_records, styles, available_width, report.language),
        Spacer(1, 2 * mm),
        _paragraph(translate("Resultados Generales", report.language), styles["SectionHeading"]),
        _general_results_table(selected_records, report, styles, available_width),
    ])
    if pag_records:
        story.extend([
            PageBreak(),
            Spacer(1, 3 * mm),
            _paragraph(translate("Resultados Perfil de Ácidos Grasos", report.language), styles["SectionHeading"]),
            _pag_results_table(pag_records, styles, available_width, report.language),
        ])

    story.extend([
        Spacer(1, 3 * mm),
        _paragraph(translate("L.D. = Limite de Detección", report.language), styles["Legend"]),
        _paragraph(translate("L.C. = Limite de Cuantificación", report.language), styles["Legend"]),
        _paragraph(translate("ND = No Detectado", report.language), styles["Legend"]),
        Spacer(1, 5 * mm),
        _paragraph(translate("FECHA EJECUCION ANALISIS", report.language), styles["SectionHeading"]),
        _execution_dates_table(report, styles),
    ])

    canvasmaker = lambda *args, **kwargs: NumberedCanvas(
        *args,
        signature_path=signature_path,
        signature_name=report.metadata.signature_name,
        signature_title=report.metadata.signature_title,
        issue_date=format_issue_date(report.metadata.issue_date, report.language),
        issue_location=report.metadata.issue_location,
        language=report.language,
        page_size=page_size,
        **kwargs,
    )
    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page, canvasmaker=canvasmaker)
    return buffer.getvalue()