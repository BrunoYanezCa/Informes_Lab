from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable

from src.report_models import ResultRecord


NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
DECIMAL_PLACES = Decimal("0.01")


def _numeric_result(value: str) -> tuple[Decimal, str] | None:
    text = value.strip()
    if text.casefold() == "nd":
        return Decimal("0"), ""
    match = NUMBER_PATTERN.search(text)
    if match is None:
        return None
    try:
        number = Decimal(match.group().replace(",", "."))
    except InvalidOperation:
        return None
    prefix = text[:match.start()].strip()
    return number, prefix if prefix in {"<", "<=", ">", ">="} else ""


def _format_number(value: Decimal) -> str:
    return f"{value.quantize(DECIMAL_PLACES, rounding=ROUND_HALF_UP):.2f}"


def format_pag_result(value: str) -> str:
    if value.strip().casefold() == "nd":
        return value
    parsed = _numeric_result(value)
    if parsed is None:
        return value
    number, prefix = parsed
    return f"{prefix}{_format_number(number)}"


def format_pag_analyte_name(value: str) -> str:
    return str(value).replace("_", " ").strip()


def calculate_epa_dha(records: Iterable[ResultRecord]) -> str:
    epa: tuple[Decimal, str] | None = None
    dha: tuple[Decimal, str] | None = None
    for record in records:
        if record.unit.strip().casefold() != "% area":
            continue
        analyte = record.analyte.casefold()
        target = "epa" if "epa" in analyte or "c20:5" in analyte else (
            "dha" if "dha" in analyte or "c22:6" in analyte else ""
        )
        if target == "epa" and epa is None:
            epa = _numeric_result(record.result)
        elif target == "dha" and dha is None:
            dha = _numeric_result(record.result)
    if epa is None or dha is None:
        return ""
    total = epa[0] + dha[0]
    prefixes = [prefix for _, prefix in (epa, dha) if prefix]
    prefix = prefixes[0] if prefixes and len(set(prefixes)) == 1 else ""
    return f"{prefix}{_format_number(total)}"


def calculate_inverse_ratio(records: Iterable[ResultRecord], ratio_name: str = "W6/W3") -> str:
    for record in records:
        if record.analyte.strip().casefold() != ratio_name.casefold():
            continue
        parsed = _numeric_result(record.result)
        if parsed is None:
            return ""
        number, prefix = parsed
        if number == 0:
            return ""
        inverse = Decimal("1") / number
        if prefix:
            inverse_prefix = "" if prefix in {"<", "<=", ">", ">="} else ""
            return f"{inverse_prefix}{_format_number(inverse)}"
        return _format_number(inverse)
    return ""