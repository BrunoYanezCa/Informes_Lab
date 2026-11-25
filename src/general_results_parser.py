from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any, Iterable, Mapping

from src.report_models import ResultRecord


PAG_MARKER = "PAG"


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def parse_general_results(
    rows: Iterable[Mapping[str, Any]], aliases: Mapping[str, str] | None = None
) -> tuple[list[ResultRecord], list[str]]:
    fields = {
        "sample_code": "JOB",
        "analysis_name": "ANALISIS",
        "analyte": "ANALITO",
        "result": "VALOR PRE",
        "unit": "UNIDAD DE EXPRESION",
        "start_date": "FECHA INICIO",
        "end_date": "FECHA TÉRMINO",
        "client": "CLIENTE",
        "product": "NOMBRE ARTICULO",
        "reception_date": "FECHA INGRESO",
        "client_reference": "N° DE GUIA",
        "observations": "OBSERVACIONES",
    }
    if aliases:
        fields.update(aliases)

    records: list[ResultRecord] = []
    warnings: list[str] = []
    seen: Counter[tuple[str, str, str, str]] = Counter()
    skipped_pag = 0

    for row in rows:
        sample_code = _text(row.get(fields["sample_code"]))
        analysis_name = _text(row.get(fields["analysis_name"]))
        analyte = _text(row.get(fields["analyte"]))
        if not sample_code or not (analysis_name or analyte):
            continue
        if analyte.casefold() == PAG_MARKER.casefold():
            skipped_pag += 1
            continue

        result_value = row.get(fields["result"])
        record = ResultRecord(
            sample_code=sample_code,
            analysis_code=analysis_name,
            analysis_name=analysis_name,
            analyte=analyte,
            result=_text(result_value),
            unit=_text(row.get(fields["unit"])),
            start_date=_text(row.get(fields["start_date"])),
            end_date=_text(row.get(fields["end_date"])),
            source_sheet="Resultados_generales_2026",
            source_row=row.get("_source_row"),
            original_values=dict(row),
        )
        records.append(record)
        key = (sample_code.casefold(), analysis_name.casefold(), analyte.casefold(), record.unit.casefold())
        seen[key] += 1

    duplicate_count = sum(count - 1 for count in seen.values() if count > 1)
    if duplicate_count:
        warnings.append(
            f"Se detectaron {duplicate_count} filas repetidas por muestra, análisis, analito y unidad en resultados generales."
        )
    if skipped_pag:
        warnings.append(
            f"Se omitieron {skipped_pag} filas agregadas con ANALITO='PAG'; el perfil debe leerse desde la hoja PAG."
        )
    return records, warnings