from __future__ import annotations

from datetime import date, datetime
from src.report_models import LaboratoryReport


def _number(value: str) -> float | None:
    text = value.strip().replace(",", ".")
    if not text:
        return None
    if text.startswith("<"):
        text = text[1:].strip()
    try:
        return float(text)
    except ValueError:
        return None


def _date(value: str) -> date | None:
    if not value:
        return None
    for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    return None


def validate_report(report: LaboratoryReport) -> list[str]:
    warnings: list[str] = []
    included = [record for record in report.results if record.include]
    if not report.metadata.sample_code:
        warnings.append("Falta el código de muestra.")
    if not included:
        warnings.append("No hay resultados incluidos en el informe.")

    selected = {analysis.casefold() for analysis in report.selected_analyses}
    for analysis in report.selected_analyses:
        if not any(record.analysis_name.casefold() == analysis.casefold() for record in included):
            warnings.append(f"El análisis '{analysis}' no tiene resultados incluidos.")

    seen: set[tuple[str, str, str, str]] = set()
    for record in included:
        if not record.analyte:
            warnings.append(f"Fila {record.source_row or '?'}: falta el analito.")
        if not record.result:
            warnings.append(f"Fila {record.source_row or '?'}: falta el resultado para '{record.analyte}'.")
        if not record.unit:
            warnings.append(f"Fila {record.source_row or '?'}: falta la unidad para '{record.analyte}'.")
        if not record.method_code and not record.method_description:
            warnings.append(f"Falta método o esquema para '{record.analysis_name}'.")
        if not record.start_date or not record.end_date:
            warnings.append(f"Faltan fechas de ejecución para '{record.analysis_name}'.")
        start = _date(record.start_date)
        end = _date(record.end_date)
        if start and end and end < start:
            warnings.append(f"La fecha de término antecede a la fecha de inicio en '{record.analysis_name}'.")

        detection_limit = _number(record.detection_limit)
        quantification_limit = _number(record.quantification_limit)
        if detection_limit is not None and quantification_limit is not None and detection_limit > quantification_limit:
            warnings.append(f"L.D. supera L.C. para '{record.analyte}' ({record.unit}).")

        key = (
            record.sample_code.casefold(),
            record.analysis_name.casefold(),
            record.analyte.casefold(),
            record.unit.casefold(),
        )
        if key in seen:
            warnings.append(
                f"Combinación repetida de muestra, análisis, analito y unidad: '{record.analyte}' ({record.unit})."
            )
        seen.add(key)
        if record.modified:
            warnings.append(f"Resultado editado manualmente: '{record.analyte}' ({record.unit}).")

    if not report.metadata.sampling_date:
        warnings.append("Falta la fecha de muestreo; no está disponible en las columnas reconocidas del libro fuente.")
    if not report.metadata.reception_date:
        warnings.append("Falta la fecha de recepción.")
    if selected and not included:
        warnings.append("La selección de análisis no contiene filas habilitadas.")
    return list(dict.fromkeys(warnings))