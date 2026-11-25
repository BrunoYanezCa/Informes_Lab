from __future__ import annotations

from collections import defaultdict
from html import escape

from src.pag_results import (
    calculate_epa_dha,
    calculate_inverse_ratio,
    format_pag_analyte_name,
    format_pag_result,
)
from src.report_models import LaboratoryReport
from src.report_i18n import format_date, parse_date, translate


def render_report_html(report: LaboratoryReport, rows_per_page: int = 32) -> str:
    t = lambda value: translate(value, report.language)
    included = [record for record in report.results if record.include]
    grouped: dict[str, list] = defaultdict(list)
    for record in included:
        grouped[record.analysis_name].append(record)

    flat_results = [record for name in report.selected_analyses for record in grouped.get(name, [])]
    start_dates = [parse_date(record.start_date) for record in flat_results if record.start_date]
    end_dates = [parse_date(record.end_date) for record in flat_results if record.end_date]
    start_dates = [value for value in start_dates if value is not None]
    end_dates = [value for value in end_dates if value is not None]
    execution_start = min(start_dates) if start_dates else ""
    execution_end = max(end_dates) if end_dates else ""
    pag_records = [
        record for record in flat_results
        if record.analysis_code.casefold() == "pag"
        or record.analysis_name.casefold() in {"perfil ácidos grasos", "perfil de ácidos grasos"}
    ]
    regular_records = [record for record in flat_results if record not in pag_records]
    method_rows = "".join(
        "<tr>"
        f"<td>{escape(t('Perfil de Ácidos Grasos') if code.casefold() == 'pag' else name)}</td>"
        f"<td>{escape(' - '.join(value for value in (code, description) if value))}</td>"
        "</tr>"
        for name, code, description in dict.fromkeys(
            (record.analysis_name, record.method_code, record.method_description)
            for record in flat_results
        )
    )
    general_rows = "".join(
        "<tr>"
        f"<td>{escape(t(record.analyte or record.analysis_name))}</td><td>{escape(record.result)}</td>"
        f"<td>{escape(record.unit)}</td><td>{escape(record.detection_limit)}</td>"
        f"<td>{escape(record.quantification_limit)}</td>"
        "</tr>"
        for record in regular_records
    )
    pag_groups: dict[str, list] = defaultdict(list)
    for record in pag_records:
        pag_groups[record.analysis_name].append(record)
    for analysis_name, records in pag_groups.items():
        units = list(dict.fromkeys(record.unit for record in records if record.unit))
        detection_limit = next((str(record.detection_limit).strip() for record in records if str(record.detection_limit).strip()), "")
        quantification_limit = next((str(record.quantification_limit).strip() for record in records if str(record.quantification_limit).strip()), "")
        general_rows += (
            "<tr>"
            f"<td>{escape(t('Perfil de Ácidos Grasos'))}</td><td>{escape(t('Ver detalle'))}</td>"
            f"<td>{escape(' / '.join(units))}</td>"
            f"<td>{escape(detection_limit)}</td><td>{escape(quantification_limit)}</td>"
            "</tr>"
        )
        general_rows += (
            "<tr><td>EPA+DHA</td>"
            f"<td>{escape(calculate_epa_dha(records))}</td><td>% Area</td><td></td><td></td></tr>"
        )

    pag_table = ""
    if pag_records:
        units = list(dict.fromkeys(record.unit for record in pag_records if record.unit))
        analytes: dict[str, list] = {}
        for record in pag_records:
            analytes.setdefault(record.analyte.casefold(), []).append(record)
        pag_rows: list[str] = []
        previous_category = ""
        for analyte_records in analytes.values():
            category = next((
                str(record.original_values.get("category", "")).strip()
                for record in analyte_records
                if record.original_values.get("category")
            ), "")
            if category.casefold() == "totales":
                category = "Totales"
            category = t(category)
            if category and category.casefold() != previous_category.casefold():
                pag_rows.append(
                    f'<tr class="pag-group"><th colspan="{len(units) + 1}">{escape(category)}</th></tr>'
                )
            previous_category = category or previous_category
            values = {record.unit.casefold(): record for record in analyte_records}
            pag_rows.append(
                "<tr>"
                f"<td>{escape(format_pag_analyte_name(analyte_records[0].analyte))}</td>"
                + "".join(
                    f"<td>{escape(format_pag_result(record.result if record else ''))}</td>"
                    for unit in units
                    for record in (values.get(unit.casefold()),)
                )
                + "</tr>"
            )
            if analyte_records[0].analyte.strip().casefold() == "w6/w3":
                pag_rows.append(
                    "<tr>"
                    "<td>W3/W6</td>"
                    + "".join(
                        f"<td>{escape(calculate_inverse_ratio([
                            record for record in analyte_records
                            if record.unit.casefold() == unit.casefold()
                        ]))}</td>"
                        for unit in units
                    )
                    + "</tr>"
                )
        pag_headings = "<th>Analito</th>" + "".join(
            f"<th>{escape(unit)}</th>"
            for unit in units
        )
        pag_table = (
            f'<h3>{escape(t("Resultados Perfil de Ácidos Grasos"))}</h3>'
            f'<table class="pag-results"><thead><tr>{pag_headings}</tr></thead>'
            f"<tbody>{''.join(pag_rows)}</tbody></table>"
        )

    metadata = report.metadata
    page = (
        '<section class="report-page">'
        '<header><div class="brand">SGS</div>'
        f"<div><h1>{escape(t('Informe de Laboratorio'))}</h1><p>{escape(metadata.sample_code)}</p></div></header>"
        f'<h3>{escape(t("Datos del Cliente"))}</h3><table class="metadata"><tbody>'
        f"<tr><th>{escape(t('Análisis solicitado por:'))}</th><td>{escape(metadata.requested_by)}</td><th>{escape(t('Nombre de Contacto:'))}</th><td>{escape(metadata.contact)}</td></tr>"
        f'<tr><th>{escape(t("Dirección:"))}</th><td colspan="3">{escape(metadata.sampling_address)}</td></tr>'
        f'</tbody></table><h3>{escape(t("Datos de la muestra"))}</h3><table class="metadata"><tbody>'
        f"<tr><th>{escape(t('Producto:'))}</th><td>{escape(metadata.product)}</td><th>{escape(t('Identificación'))}</th><td>{escape(metadata.sample_description)}</td></tr>"
        f"<tr><th>{escape(t('Lote:'))}</th><td>{escape(metadata.lot)}</td><th>{escape(t('Contenedor:'))}</th><td>{escape(metadata.container)}</td></tr>"
        f"<tr><th>{escape(t('Nº de Guía:'))}</th><td>{escape(metadata.guide_number or metadata.client_reference)}</td><th>{escape(t('Muestreado Por:'))}</th><td>{escape(metadata.sampled_by)}</td></tr>"
        f"<tr><th>{escape(t('Fecha de Muestreo:'))}</th><td>{escape(format_date(metadata.sampling_date))}</td><th>{escape(t('Fecha de Recepción:'))}</th><td>{escape(format_date(metadata.reception_date))}</td></tr>"
        f"<tr><th>{escape(t('Fecha de Inicio Ensayo:'))}</th><td>{escape(format_date(execution_start))}</td><th>{escape(t('Fecha de Término Ensayo:'))}</th><td>{escape(format_date(execution_end))}</td></tr>"
        f'<tr><th>{escape(t("Solicitud de Análisis:"))}</th><td colspan="3">{escape(metadata.request_number)}</td></tr>'
        "</tbody></table>"
        f'<h3>{escape(t("Análisis / Metodología"))}</h3>'
        f'<table class="assay-method"><thead><tr><th>{escape(t("Ensayos"))}</th><th>{escape(t("Método/Título"))}</th></tr></thead>'
        f"<tbody>{method_rows}</tbody></table>"
        f'<h3>{escape(t("Resultados Generales"))}</h3>'
        f'<table class="general-results"><thead><tr><th>{escape(t("ANÁLISIS"))}</th><th>{escape(t("RESULTADO"))}</th>'
        f'<th>{escape(t("UNIDAD"))}</th><th>{escape(t("L.D."))}</th><th>{escape(t("L.C."))}</th></tr></thead>'
        f"<tbody>{general_rows}</tbody></table>"
        + pag_table
        + f'<footer>{escape(t("Página 1 de 1"))}</footer></section>'
    )

    notices = "".join(
        f"<p>{escape(str(text))}</p>"
        for text in report.warnings
    )
    return (
        "<style>"
        "body{font-family:Arial,sans-serif;color:#202124;font-size:12px}"
        ".report-page{border:1px solid #bbb;padding:18px;margin:12px 0;min-height:760px;position:relative}"
        "header{display:flex;align-items:center;gap:18px;border-bottom:4px solid #f5c400;padding-bottom:10px}"
        ".brand{font-size:30px;font-weight:bold;color:#222}h1{font-size:21px;margin:0}h3{font-size:15px;margin:18px 0 6px}"
        "table{width:100%;border-collapse:collapse;margin-bottom:12px}th,td{border:1px solid #aaa;padding:5px;text-align:left}"
        "th{background:#f5f5f5}.metadata th{width:15%}.metadata td{width:35%}"
        ".assay-method th,.general-results th,.pag-results th{color:#ff6216;font-size:10px}.assay-method td,.general-results td,.pag-results td{font-size:11px}"
        ".pag-results{table-layout:fixed}.pag-results th:not(:first-child),.pag-results td:not(:first-child){text-align:center}.pag-group th{background:#e5e5e5;color:#202124;text-align:left}"
        ".general-results tbody tr:nth-child(even),.pag-results tbody tr:nth-child(odd){background:#eee}"
        "footer{position:absolute;bottom:10px;right:18px;color:#555}"
        "</style><main>"
        + page
        + f'<section><h2>{escape(t("Observaciones y avisos"))}</h2>{notices}</section></main>'
    )