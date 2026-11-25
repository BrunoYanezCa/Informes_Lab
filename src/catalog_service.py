from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def load_catalog(
    defaults_path: str | Path,
    overrides_path: str | Path | None = None,
    overrides_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    with Path(defaults_path).open("r", encoding="utf-8") as file:
        defaults = yaml.safe_load(file) or {}
    analyses = {
        str(item["code"]): dict(item)
        for item in defaults.get("analyses", [])
        if item.get("code")
    }
    overrides = overrides_data or {}
    if overrides_path is not None:
        override_path = Path(overrides_path)
        if override_path.exists():
            with override_path.open("r", encoding="utf-8") as file:
                overrides = json.load(file)
    for code, values in overrides.get("analyses", {}).items():
        analyses.setdefault(code, {"code": code}).update(values)
    return list(analyses.values())


def serialize_catalog_overrides(analyses: list[dict[str, Any]]) -> str:
    payload = {
        "analyses": {
            str(item["code"]): item
            for item in analyses
            if item.get("code")
        }
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _normalized_limit_key(analyte: Any, unit: Any) -> str:
    analyte_text = " ".join(str(analyte or "").strip().casefold().split())
    unit_text = " ".join(str(unit or "").strip().casefold().split())
    return f"{analyte_text}|{unit_text}"


def apply_catalog_limit_overrides(records: list[Any], catalog: list[dict[str, Any]]) -> list[Any]:
    """Aplica límites LD/LC no vacíos del catálogo como fuente autoritativa.

    Los borradores de resultados pueden contener valores históricos o vacíos.
    Para evitar que esos valores oculten una configuración guardada, cada límite
    no vacío del catálogo reemplaza el valor del registro al construir el informe.
    """
    updated = deepcopy(records)
    for record in updated:
        analysis_labels = {str(record.analysis_code).casefold(), str(record.analysis_name).casefold()}
        item = None
        for candidate in catalog:
            labels = {
                str(candidate.get(key, "")).casefold()
                for key in ("code", "display_name")
                if candidate.get(key)
            }
            labels.update(
                str(alias).casefold()
                for alias in candidate.get("aliases", [])
                if alias
            )
            if analysis_labels & labels:
                item = candidate
                break
        if item is None:
            continue

        record_key = _normalized_limit_key(record.analyte, record.unit)
        for key, values in item.get("limits", {}).items():
            key_analyte, separator, key_unit = str(key).partition("|")
            if separator:
                catalog_key = _normalized_limit_key(key_analyte, key_unit)
            else:
                catalog_key = _normalized_limit_key(key_analyte, "")
            if catalog_key != record_key:
                continue

            detection_limit = str(values.get("detection_limit", "") or "").strip()
            quantification_limit = str(values.get("quantification_limit", "") or "").strip()
            if detection_limit:
                record.detection_limit = detection_limit
            if quantification_limit:
                record.quantification_limit = quantification_limit
            break
    return updated