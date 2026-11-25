from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Sequence

from src.report_models import ResultRecord


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def parse_pag_results(
    rows: Sequence[Sequence[Any]],
    selected_sample: str | None = None,
) -> tuple[list[ResultRecord], list[str]]:
    if len(rows) < 7:
        return [], ["La hoja PAG no contiene las filas esperadas de identificadores, unidades y analitos."]

    def cell(row_index: int, column_index: int) -> Any:
        if row_index >= len(rows) or column_index >= len(rows[row_index]):
            return None
        return rows[row_index][column_index]

    sample_columns: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    max_columns = max((len(row) for row in rows[:6]), default=0)
    for column_index in range(2, max_columns):
        job = _text(cell(3, column_index))
        identifier = _text(cell(0, column_index))
        unit = _text(cell(5, column_index))
        if job:
            sample_columns[job.casefold()].append((column_index, identifier, unit))

    records: list[ResultRecord] = []
    warnings: list[str] = []
    if any(not identifier for columns in sample_columns.values() for _, identifier, _ in columns):
        warnings.append("Hay columnas de PAG con JOB pero sin identificador de muestra en la fila 1.")

    for columns in sample_columns.values():
        for column_index, identifier, unit in columns:
            job = _text(cell(3, column_index))
            if selected_sample and job.casefold() != selected_sample.strip().casefold():
                continue
            if not unit:
                if any(_text(cell(row_index, column_index)) for row_index in range(6, len(rows))):
                    warnings.append(f"La muestra {job} tiene resultados PAG en una columna sin unidad.")
                continue

            category = ""
            for row_index in range(6, len(rows)):
                row_category = _text(cell(row_index, 0))
                if row_category.casefold() == "totales":
                    row_category = "Totales"
                category = row_category or category
                analyte = _text(cell(row_index, 1))
                result = _text(cell(row_index, column_index))
                if not analyte or not result:
                    continue
                records.append(
                    ResultRecord(
                        sample_code=job,
                        analysis_code="PAG",
                        analysis_name="Perfil de Ácidos Grasos",
                        analyte=analyte,
                        result=result,
                        unit=unit,
                        source_sheet="PAG",
                        source_row=row_index + 1,
                        original_values={
                            "sample_identifier": identifier,
                            "job": job,
                            "analyte": analyte,
                            "unit": unit,
                            "result": result,
                            "category": category,
                        },
                    )
                )

    job_unit_columns: dict[tuple[str, str], list[int]] = defaultdict(list)
    for job_key, columns in sample_columns.items():
        for column_index, _, unit in columns:
            if unit:
                job_unit_columns[(job_key, unit.casefold())].append(column_index)
    duplicated_columns = sum(len(column_indexes) - 1 for column_indexes in job_unit_columns.values() if len(column_indexes) > 1)
    if duplicated_columns:
        warnings.append(
            f"Se encontraron {duplicated_columns} columnas PAG repetidas con el mismo JOB y unidad; revisar antes de combinar resultados."
        )

    if selected_sample and not records:
        warnings.append(f"No se encontraron resultados PAG para la muestra seleccionada: {selected_sample}.")
    return records, list(dict.fromkeys(warnings))