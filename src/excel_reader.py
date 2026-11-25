from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook


GENERAL_SHEET = "Resultados_generales_2026"
PAG_SHEET = "PAG"
GENERAL_HEADER_ROW = 5


def _resolve_sheet(workbook: Any, requested_name: str) -> Any:
    if requested_name in workbook.sheetnames:
        return workbook[requested_name]
    matches = [name for name in workbook.sheetnames if name.casefold() == requested_name.casefold()]
    if len(matches) == 1:
        return workbook[matches[0]]
    raise KeyError(f"No se encontró la hoja requerida: {requested_name}")


def read_general_rows(
    workbook_path: str | Path,
    sheet_name: str = GENERAL_SHEET,
    header_row: int = GENERAL_HEADER_ROW,
) -> list[dict[str, Any]]:
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        sheet = _resolve_sheet(workbook, sheet_name)
        headers = [str(value).strip() if value is not None else "" for value in next(
            sheet.iter_rows(min_row=header_row, max_row=header_row, values_only=True)
        )]
        rows: list[dict[str, Any]] = []
        for row_number, values in enumerate(
            sheet.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1
        ):
            record = {
                header: values[index] if index < len(values) else None
                for index, header in enumerate(headers)
                if header
            }
            if any(value is not None and str(value).strip() for value in record.values()):
                record["_source_row"] = row_number
                rows.append(record)
        return rows
    finally:
        workbook.close()


def read_pag_matrix(workbook_path: str | Path, sheet_name: str = PAG_SHEET) -> list[tuple[Any, ...]]:
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        sheet = _resolve_sheet(workbook, sheet_name)
        return [tuple(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def read_workbook_sheet_names(workbook_path: str | Path) -> list[str]:
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()