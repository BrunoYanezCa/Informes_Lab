from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Iterable

from src.report_models import ResultRecord, SampleMetadata


EDITABLE_RESULT_FIELDS = (
    "analysis_code",
    "analysis_name",
    "analyte",
    "result",
    "unit",
    "detection_limit",
    "quantification_limit",
    "method_code",
    "method_description",
    "start_date",
    "end_date",
    "include",
    "modified",
)


def _result_draft_key(record: ResultRecord) -> str:
    source = record.original_values
    key = (
        record.sample_code.casefold(),
        record.source_sheet,
        record.source_row,
        str(source.get("ANALISIS") or record.analysis_code).casefold(),
        str(source.get("ANALITO") or source.get("analyte") or record.analyte).casefold(),
        str(source.get("UNIDAD DE EXPRESION") or source.get("unit") or record.unit).casefold(),
    )
    return "|".join("" if value is None else str(value) for value in key)


def serialize_result_drafts(records: Iterable[ResultRecord]) -> dict[str, Any]:
    saved_records: dict[str, dict[str, Any]] = {}
    manual_records: list[dict[str, Any]] = []
    for record in records:
        values = {field: getattr(record, field) for field in EDITABLE_RESULT_FIELDS}
        values["sample_code"] = record.sample_code
        if record.source_row is None or record.source_sheet == "Manual":
            manual_records.append(values)
        else:
            saved_records[_result_draft_key(record)] = values
    return {"records": saved_records, "manual": manual_records}


def restore_result_drafts(
    records: Iterable[ResultRecord], saved: dict[str, Any] | None
) -> list[ResultRecord]:
    original_records = list(records)
    if not saved:
        return original_records
    saved_records = saved.get("records", {})
    restored: list[ResultRecord] = []
    for original in original_records:
        values = saved_records.get(_result_draft_key(original))
        if values is None:
            continue
        record = deepcopy(original)
        for field in EDITABLE_RESULT_FIELDS:
            if field in values:
                setattr(record, field, values[field])
        restored.append(record)
    for values in saved.get("manual", []):
        restored.append(ResultRecord(
            sample_code=str(values.get("sample_code", "")),
            analysis_code=str(values.get("analysis_code", "")),
            analysis_name=str(values.get("analysis_name", "")),
            analyte=str(values.get("analyte", "")),
            result=str(values.get("result", "")),
            unit=str(values.get("unit", "")),
            detection_limit=str(values.get("detection_limit", "")),
            quantification_limit=str(values.get("quantification_limit", "")),
            method_code=str(values.get("method_code", "")),
            method_description=str(values.get("method_description", "")),
            start_date=str(values.get("start_date", "")),
            end_date=str(values.get("end_date", "")),
            source_sheet="Manual",
            include=bool(values.get("include", True)),
            modified=bool(values.get("modified", True)),
        ))
    return restored


def list_sample_codes(records: Iterable[ResultRecord]) -> list[str]:
    return sorted({record.sample_code for record in records if record.sample_code}, key=str.casefold)


def analyses_for_sample(records: Iterable[ResultRecord], sample_code: str) -> list[str]:
    return sorted(
        {
            record.analysis_name
            for record in records
            if record.sample_code.casefold() == sample_code.casefold() and record.analysis_name
        },
        key=str.casefold,
    )


def results_for_sample(
    records: Iterable[ResultRecord], sample_code: str, selected_analyses: Iterable[str] | None = None
) -> list[ResultRecord]:
    selected = {name.casefold() for name in selected_analyses} if selected_analyses is not None else None
    return [
        record
        for record in records
        if record.sample_code.casefold() == sample_code.casefold()
        and (selected is None or record.analysis_name.casefold() in selected)
    ]


def results_for_selected_analyses(
    records: Iterable[ResultRecord], selected_analyses: Iterable[str]
) -> list[ResultRecord]:
    selected = {name.casefold() for name in selected_analyses}
    return [
        record for record in records
        if {record.analysis_code.casefold(), record.analysis_name.casefold()} & selected
    ]


def metadata_for_sample(records: Iterable[ResultRecord], sample_code: str) -> SampleMetadata:
    for record in records:
        if record.sample_code.casefold() != sample_code.casefold():
            continue
        source = record.original_values

        def display_value(value: object) -> str:
            if isinstance(value, (date, datetime)):
                return value.strftime("%Y-%m-%d")
            return str(value or "")

        return SampleMetadata(
            sample_code=sample_code,
            request_number=str(source.get("N SOLICITUD DE ANALISIS") or ""),
            sample_description=str(source.get("LOTE O CONTENEDOR /ID BATCH MEZCLA") or ""),
            client=str(source.get("PROVEEDOR CLIENTE O ESTANQUE SBH") or source.get("CLIENTE") or ""),
            product=str(source.get("NOMBRE ARTICULO") or ""),
            lot=str(source.get("LOTE") or ""),
            container=str(source.get("CONTENEDOR") or ""),
            guide_number=str(source.get("N° DE GUIA") or ""),
            reception_date=display_value(source.get("FECHA INGRESO")),
            client_reference=str(source.get("N° DE GUIA") or ""),
            observations=str(source.get("OBSERVACIONES") or ""),
        )
    return SampleMetadata(sample_code=sample_code)


def execution_dates_for_results(records: Iterable[ResultRecord]) -> dict[str, dict[str, str]]:
    dates: dict[str, dict[str, str]] = defaultdict(dict)
    for record in records:
        analysis = record.analysis_name
        if record.start_date:
            dates[analysis]["start_date"] = min(
                dates[analysis].get("start_date", record.start_date), record.start_date
            )
        if record.end_date:
            dates[analysis]["end_date"] = max(
                dates[analysis].get("end_date", record.end_date), record.end_date
            )
    return dict(dates)