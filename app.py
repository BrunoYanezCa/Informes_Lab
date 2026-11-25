from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import hashlib
from io import BytesIO
import json
from typing import Any

import pandas as pd
import streamlit as st

from src.catalog_service import (
    apply_catalog_limit_overrides,
    load_catalog,
    serialize_catalog_overrides,
)
from src.excel_reader import read_general_rows, read_pag_matrix
from src.general_results_parser import parse_general_results
from src.pag_parser import parse_pag_results
from src.preferences_service import (
    load_preferences,
    replace_signature,
    restore_signature,
    save_preferences,
)
from src.pdf_generator import generate_pdf
from src.report_models import LaboratoryReport, ResultRecord, SampleMetadata
from src.report_renderer import render_report_html
from src.report_i18n import format_date, normalize_date
from src.report_validator import validate_report
from src.sample_service import (
    analyses_for_sample,
    list_sample_codes,
    metadata_for_sample,
    results_for_sample,
    results_for_selected_analyses,
    restore_result_drafts,
    serialize_result_drafts,
)
from src.utils import PROJECT_ROOT, load_yaml


st.set_page_config(page_title="Informes de Laboratorio", page_icon="📄", layout="wide")
SETTINGS = load_yaml(PROJECT_ROOT / "config" / "settings.yaml")
ALIASES = load_yaml(PROJECT_ROOT / "config" / "column_aliases.yaml").get("general", {})
DEFAULT_CATALOG = PROJECT_ROOT / "config" / "analysis_catalog.yaml"
PREFERENCES_PATH = PROJECT_ROOT / "config" / "user_preferences.json"


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, (datetime,)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def _catalog_for_analysis(analysis_name: str, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    for item in catalog:
        labels = [str(item.get(key, "")) for key in ("code", "display_name")]
        labels.extend(str(alias) for alias in item.get("aliases", []))
        if analysis_name.casefold() in {label.casefold() for label in labels if label}:
            return item
    return {"code": analysis_name, "display_name": analysis_name, "aliases": [], "limits": {}}


def _apply_catalog(records: list[ResultRecord], catalog: list[dict[str, Any]]) -> list[ResultRecord]:
    updated = deepcopy(records)
    for record in updated:
        source_analysis = record.analysis_code or record.analysis_name
        item = _catalog_for_analysis(source_analysis, catalog)
        record.analysis_code = source_analysis
        record.analysis_name = (
            "Perfil de Ácidos Grasos"
            if source_analysis.casefold() == "pag"
            else str(item.get("display_name") or record.analysis_name)
        )
        record.method_code = record.method_code or str(item.get("method_code", "") or "")
        record.method_description = record.method_description or str(item.get("method_description", "") or "")
        limit_key = f"{record.analyte}|{record.unit}"
        limits = item.get("limits", {}).get(limit_key, {})
        record.detection_limit = record.detection_limit or str(limits.get("detection_limit", "") or "")
        record.quantification_limit = record.quantification_limit or str(limits.get("quantification_limit", "") or "")
    return updated


def _persist_catalog(catalog: list[dict[str, Any]]) -> None:
    preferences = st.session_state["preferences"]
    preferences["catalog"] = json.loads(serialize_catalog_overrides(catalog))
    save_preferences(PREFERENCES_PATH, preferences)


def _load_source(source: Any) -> tuple[list[ResultRecord], list[str]]:
    general_sheet = SETTINGS["workbook"]["general_sheet"]
    pag_sheet = SETTINGS["workbook"]["pag_sheet"]
    general_rows = read_general_rows(source, general_sheet, SETTINGS["workbook"]["general_header_row"])
    records, warnings = parse_general_results(general_rows, ALIASES)
    pag_matrix = read_pag_matrix(source, pag_sheet)
    pag_records, pag_warnings = parse_pag_results(pag_matrix)
    general_pag_jobs = {
        _text(row.get(ALIASES["sample_code"]))
        for row in general_rows
        if _text(row.get(ALIASES["analyte"])).casefold() == "pag"
    }
    overlap = general_pag_jobs & {record.sample_code for record in pag_records}
    if overlap:
        warnings.append(
            f"{len(overlap)} códigos tienen el agregado PAG en resultados generales y perfil en la hoja PAG; se usa el perfil de PAG y se omite el agregado."
        )
    records.extend(pag_records)
    warnings.extend(pag_warnings)
    return records, list(dict.fromkeys(warnings))


def _editor_frame(records: list[ResultRecord]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Incluir": record.include,
            "Análisis": record.analysis_name,
            "Analito": record.analyte,
            "Resultado": record.result,
            "Unidad": record.unit,
            "L.D.": record.detection_limit,
            "L.C.": record.quantification_limit,
            "Código método": record.method_code,
            "Método / esquema": record.method_description,
            "Fecha inicio": record.start_date,
            "Fecha término": record.end_date,
            "Origen": record.source_sheet,
            "_original": record,
        }
        for record in records
    ])


def _editor_records(frame: pd.DataFrame) -> list[ResultRecord]:
    records: list[ResultRecord] = []
    for _, row in frame.iterrows():
        original = row.get("_original")
        if not isinstance(original, ResultRecord):
            original = ResultRecord(sample_code="", analysis_code="", analysis_name="", analyte="")
        record = deepcopy(original)
        record.include = bool(row.get("Incluir", True)) if not pd.isna(row.get("Incluir", True)) else False
        fields = {
            "analysis_name": "Análisis",
            "analyte": "Analito",
            "result": "Resultado",
            "unit": "Unidad",
            "detection_limit": "L.D.",
            "quantification_limit": "L.C.",
            "method_code": "Código método",
            "method_description": "Método / esquema",
            "start_date": "Fecha inicio",
            "end_date": "Fecha término",
            "source_sheet": "Origen",
        }
        analysis_changed = False
        for attribute, column in fields.items():
            value = _text(row.get(column, ""))
            if value != getattr(original, attribute):
                setattr(record, attribute, value)
                record.modified = True
                if attribute == "analysis_name":
                    analysis_changed = True
        if analysis_changed:
            record.analysis_code = record.analysis_name
        if not original.sample_code:
            record.sample_code = st.session_state.get("active_sample", "")
            record.source_sheet = "Manual"
            record.modified = True
        records.append(record)
    return records


def _execution_dates_frame(
    records: list[ResultRecord], saved_dates: dict[str, Any]
) -> pd.DataFrame:
    analyses: dict[str, dict[str, str]] = {}
    for record in records:
        analysis_key = record.analysis_name.casefold()
        values = analyses.setdefault(analysis_key, {
            "Análisis": record.analysis_name,
            "Fecha inicio": "",
            "Fecha término": "",
        })
        start_date = normalize_date(record.start_date) if record.start_date else ""
        end_date = normalize_date(record.end_date) if record.end_date else ""
        if start_date:
            values["Fecha inicio"] = min(values["Fecha inicio"], start_date) if values["Fecha inicio"] else start_date
        if end_date:
            values["Fecha término"] = max(values["Fecha término"], end_date)
    rows = []
    for analysis_key, values in analyses.items():
        defaults = saved_dates.get(analysis_key, {})
        rows.append({
            "Análisis": values["Análisis"],
            "Fecha inicio": format_date(defaults.get("start_date", values["Fecha inicio"])),
            "Fecha término": format_date(defaults.get("end_date", values["Fecha término"])),
        })
    return pd.DataFrame(rows, columns=["Análisis", "Fecha inicio", "Fecha término"])


def _render_catalog(catalog: list[dict[str, Any]]) -> None:
    st.subheader("Configuración persistente de análisis")
    st.caption("Los cambios se guardan en este servidor local. Puedes descargar el catálogo JSON para trasladarlo a otra instalación. No se completan límites ni métodos por inferencia.")
    with st.expander("Importar catálogo JSON"):
        uploaded_catalog = st.file_uploader("Archivo de configuración", type=["json"], key="catalog_json_upload")
        if st.button("Cargar configuración JSON", disabled=uploaded_catalog is None):
            if uploaded_catalog is None:
                st.error("Selecciona un JSON para cargar la configuración.")
            else:
                try:
                    overrides = json.loads(uploaded_catalog.getvalue().decode("utf-8"))
                    imported = load_catalog(DEFAULT_CATALOG, overrides_data=overrides)
                    imported_codes = {item["code"] for item in imported}
                    imported.extend(item for item in catalog if item.get("code") not in imported_codes)
                    st.session_state["catalog"] = imported
                    _persist_catalog(imported)
                    st.success("Catálogo cargado en esta sesión.")
                    st.rerun()
                except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as error:
                    st.error(f"No se pudo leer el JSON: {error}")
    names = [str(item.get("display_name") or item.get("code")) for item in catalog]
    selected_name = st.selectbox("Análisis", names, key="catalog_selected")
    selected = next(item for item in catalog if str(item.get("display_name") or item.get("code")) == selected_name)
    analytes = "\n".join(str(item) for item in selected.get("analytes", []))
    units = ", ".join(str(item) for item in selected.get("allowed_units", []))
    limits = selected.get("limits", {})
    limit_rows = []
    analytes_for_limits = list(selected.get("analytes", []))
    units_for_limits = list(selected.get("allowed_units", []))
    if str(selected.get("code", "")).casefold() == "pag":
        active_sample = st.session_state.get("active_sample", "")
        sample_records = [
            record for record in st.session_state.get("all_records", [])
            if record.sample_code.casefold() == active_sample.casefold()
            and (record.analysis_code.casefold() == "pag" or record.source_sheet == "PAG")
        ]
        analytes_for_limits = list(dict.fromkeys(
            record.analyte for record in sample_records if record.analyte
        )) or analytes_for_limits
        units_for_limits = list(dict.fromkeys(
            record.unit for record in sample_records if record.unit
        )) or units_for_limits
        limit_keys = [f"{analyte}|{unit}" for analyte in analytes_for_limits for unit in units_for_limits]
    else:
        limit_keys = list(limits)
    for key in limit_keys:
        values = limits.get(key, {})
        analyte, separator, unit = str(key).partition("|")
        limit_rows.append({
            "Analito": analyte,
            "Unidad": unit if separator else "",
            "L.D.": values.get("detection_limit", ""),
            "L.C.": values.get("quantification_limit", ""),
        })
    if not limit_rows:
        limit_rows = [{"Analito": "", "Unidad": "", "L.D.": "", "L.C.": ""}]

    with st.form("catalog_form"):
        display_name = st.text_input("Nombre en el informe", value=str(selected.get("display_name", "")))
        method_code = st.text_input("Código de método", value=str(selected.get("method_code", "")))
        method_description = st.text_input("Método / esquema", value=str(selected.get("method_description", "")))
        unit_text = st.text_input("Unidades permitidas", value=units, help="Separar por coma; se conservan las unidades observadas en el Excel.")
        analyte_text = st.text_area("Analitos esperados, en orden", value=analytes, height=140)
        limits_frame = st.data_editor(
            pd.DataFrame(limit_rows),
            num_rows="dynamic",
            width="stretch",
            key=f"limits_{selected['code']}_{st.session_state.get('active_sample', 'default')}",
            column_config={
                "Analito": st.column_config.TextColumn(required=False),
                "Unidad": st.column_config.TextColumn(required=False),
                "L.D.": st.column_config.TextColumn(required=False),
                "L.C.": st.column_config.TextColumn(required=False),
            },
        )
        save = st.form_submit_button("Guardar como predeterminado")
    if save:
        updated = deepcopy(catalog)
        item = next(entry for entry in updated if entry["code"] == selected["code"])
        item["display_name"] = display_name.strip() or str(item["code"])
        item["method_code"] = method_code.strip()
        item["method_description"] = method_description.strip()
        item["allowed_units"] = [value.strip() for value in unit_text.split(",") if value.strip()]
        item["analytes"] = [value.strip() for value in analyte_text.splitlines() if value.strip()]
        item["limits"] = {
            f"{_text(row['Analito'])}|{_text(row['Unidad'])}": {
                "detection_limit": _text(row["L.D."]),
                "quantification_limit": _text(row["L.C."]),
            }
            for _, row in limits_frame.iterrows()
            if _text(row["Analito"]) and _text(row["Unidad"])
        }
        catalog = updated
        st.session_state["catalog"] = updated
        _persist_catalog(updated)
        st.success("Configuración guardada y aplicada como predeterminada.")
    st.download_button(
        "Descargar catálogo JSON",
        data=serialize_catalog_overrides(catalog),
        file_name="catalogo_analisis.json",
        mime="application/json",
        width="stretch",
    )


def main() -> None:
    st.title("Informes de Laboratorio")
    if "preferences" not in st.session_state:
        st.session_state["preferences"] = load_preferences(PREFERENCES_PATH)
    st.session_state.setdefault(
        "report_language_english",
        bool(st.session_state["preferences"].get("report_language_english", False)),
    )
    report_in_english = st.checkbox(
        "Generar informe en inglés",
        key="report_language_english",
    )
    if report_in_english != st.session_state["preferences"].get("report_language_english", False):
        st.session_state["preferences"]["report_language_english"] = report_in_english
        save_preferences(PREFERENCES_PATH, st.session_state["preferences"])
    if "catalog" not in st.session_state:
        st.session_state["catalog"] = load_catalog(
            DEFAULT_CATALOG,
            overrides_data=st.session_state["preferences"].get("catalog", {}),
        )
    catalog = st.session_state["catalog"]

    with st.sidebar:
        st.header("Origen de resultados")
        uploaded = st.file_uploader("Libro Excel", type=["xlsx", "xlsm"])
        if st.button("Cargar resultados", type="primary", width="stretch"):
            if uploaded is None:
                st.error("Sube un libro Excel para cargar los resultados.")
            else:
                try:
                    workbook_bytes = uploaded.getvalue()
                    source_key = f"{uploaded.name}:{hashlib.sha256(workbook_bytes).hexdigest()}"
                    with st.spinner("Leyendo las hojas de resultados..."):
                        records, warnings = _load_source(BytesIO(workbook_bytes))
                    saved_result_drafts = st.session_state["preferences"].get("result_drafts", {}).get(source_key, {})
                    records_by_sample = {
                        code.casefold(): restore_result_drafts(
                            [record for record in records if record.sample_code.casefold() == code.casefold()],
                            saved_result_drafts.get(code),
                        )
                        for code in list_sample_codes(records)
                    }
                    records = [
                        record
                        for code in list_sample_codes(records)
                        for record in records_by_sample[code.casefold()]
                    ]
                    st.session_state["all_records"] = records
                    st.session_state["source_warnings"] = warnings
                    st.session_state["source_name"] = uploaded.name
                    st.session_state["source_key"] = source_key
                    st.session_state["drafts"] = {}
                    catalog = st.session_state["catalog"]
                    known = {
                        str(label).casefold()
                        for item in catalog
                        for label in [item.get("code", ""), item.get("display_name", ""), *item.get("aliases", [])]
                        if label
                    }
                    analysis_names = sorted(
                        {record.analysis_name for record in records if record.analysis_name},
                        key=str.casefold,
                    )
                    for analysis_name in analysis_names:
                        if analysis_name.casefold() in known:
                            continue
                        analysis_records = [record for record in records if record.analysis_name == analysis_name]
                        catalog.append({
                            "code": analysis_name,
                            "aliases": [],
                            "display_name": analysis_name,
                            "preferred_source": "PAG" if all(record.source_sheet == "PAG" for record in analysis_records) else "Resultados_generales_2026",
                            "analytes": list(dict.fromkeys(record.analyte for record in analysis_records if record.analyte)),
                            "allowed_units": list(dict.fromkeys(record.unit for record in analysis_records if record.unit)),
                            "method_code": "",
                            "method_description": "",
                            "limits": {},
                            "rules": {},
                        })
                        known.add(analysis_name.casefold())
                    st.session_state["catalog"] = catalog
                    if not records:
                        st.warning("El libro se leyó, pero no se encontraron resultados reconocibles.")
                    else:
                        st.success(f"Cargados {len(records):,} resultados desde {st.session_state['source_name']}.")
                except Exception as error:
                    st.error(f"No se pudieron leer los resultados: {error}")

        all_records = st.session_state.get("all_records", [])
        if all_records:
            codes = list_sample_codes(all_records)
            st.divider()
            st.header("Selección")
            st.caption(f"{len(codes):,} muestras detectadas")
            sample = st.selectbox("Muestra / JOB", codes, key="sample_selector")
            st.session_state["active_sample"] = sample
            detected = analyses_for_sample(all_records, sample)
            select_all = st.checkbox("Seleccionar todos", value=True, key=f"all_{sample}")
            selected_analyses = detected if select_all else st.multiselect(
                "Análisis incluidos", detected, default=detected, key=f"analyses_{sample}"
            )
            st.session_state["selected_analyses"] = selected_analyses
            st.caption(f"{len(selected_analyses)} de {len(detected)} análisis seleccionados")
            warnings = st.session_state.get("source_warnings", [])
            if warnings:
                with st.expander(f"Advertencias de lectura ({len(warnings)})"):
                    for warning in warnings:
                        st.warning(warning)

    if not st.session_state.get("all_records"):
        st.info("Carga el libro de resultados desde la barra lateral para comenzar.")
        return

    all_records = st.session_state["all_records"]
    sample = st.session_state["active_sample"]
    selected_source_analyses = st.session_state.get("selected_analyses", [])
    selected_analyses = [
        str(_catalog_for_analysis(name, catalog).get("display_name") or name)
        for name in selected_source_analyses
    ]
    base_results = _apply_catalog(results_for_sample(all_records, sample), catalog)
    drafts = st.session_state.setdefault("drafts", {})
    if sample not in drafts:
        drafts[sample] = _editor_frame(base_results)
    frame = drafts[sample]
    metadata_drafts = st.session_state.setdefault("metadata_drafts", {})
    if sample not in metadata_drafts:
        metadata = metadata_for_sample(all_records, sample).__dict__.copy()
        excel_metadata = metadata.copy()
        preferences = st.session_state["preferences"]
        saved_metadata = preferences.get("metadata_by_sample", {}).get(sample, {})
        metadata.update({key: value for key, value in saved_metadata.items() if key in metadata})
        global_metadata = preferences.get("metadata_defaults", {})
        metadata.update({key: value for key, value in global_metadata.items() if key in metadata})
        priority_fields = ("client", "reception_date", "lot", "guide_number", "product")
        for field_name in priority_fields:
            metadata[field_name] = excel_metadata.get(field_name, "")
        metadata["sample_code"] = sample
        metadata_drafts[sample] = metadata
    metadata = metadata_drafts[sample]
    signature_defaults = SETTINGS["report"].get("signature", {})
    metadata.setdefault("signature_name", signature_defaults.get("default_name", ""))
    metadata.setdefault("signature_title", signature_defaults.get("default_title", ""))
    metadata.setdefault("issue_location", signature_defaults.get("default_location", ""))
    if not metadata.get("issue_date"):
        metadata["issue_date"] = date.today().isoformat()

    general_tab, results_tab, preview_tab, generate_tab, catalog_tab = st.tabs(
        ["Datos generales", "Resultados", "Vista previa", "Generar", "Configuración"]
    )
    with general_tab:
        st.subheader("Datos del informe")
        with st.form(f"metadata_form_{sample}"):
            left, right = st.columns(2)
            with left:
                requested_by = st.text_input("Análisis solicitado por", value=metadata.get("requested_by", ""))
                contact = st.text_input("Nombre de Contacto", value=metadata.get("contact", ""))
                product = st.text_input("Producto", value=metadata.get("product", ""))
                lot = st.text_input("Lote", value=metadata.get("lot", ""))
                container = st.text_input("Contenedor", value=metadata.get("container", ""))
                guide_number = st.text_input("Nº de Guía", value=metadata.get("guide_number", metadata.get("client_reference", "")))
                request_number = st.text_input("Solicitud de Análisis", value=metadata.get("request_number", ""))
                sampling_address = st.text_input("Dirección", value=metadata.get("sampling_address", ""))
                signature_name = st.text_input("Nombre de quien firma", value=metadata.get("signature_name", ""))
                signature_title = st.text_input("Cargo de quien firma", value=metadata.get("signature_title", ""))
            with right:
                sampling_date = st.text_input("Fecha de muestreo (DD/MM/AAAA)", value=format_date(metadata.get("sampling_date", "")))
                reception_date = st.text_input("Fecha de recepción (DD/MM/AAAA)", value=format_date(metadata.get("reception_date", "")))
                sampled_by = st.text_input("Muestreado Por", value=metadata.get("sampled_by", ""))
                issue_location = st.text_input("Lugar de emisión", value=metadata.get("issue_location", ""))
                issue_date = st.text_input(
                    "Fecha de emisión (texto libre)",
                    value=metadata.get("issue_date") or date.today().strftime("%Y-%m-%d"),
                    help="Puedes escribir una fecha o texto libre, por ejemplo: 18 de Noviembre del 2026.",
                )
            observations = st.text_area("Observaciones", value=metadata.get("observations", ""))
            submitted = st.form_submit_button("Aplicar datos generales")
        if submitted:
            metadata.update({
                "requested_by": requested_by,
                "contact": contact,
                "product": product,
                "lot": lot,
                "container": container,
                "guide_number": guide_number,
                "request_number": request_number,
                "sampling_address": sampling_address,
                "sampling_date": normalize_date(sampling_date),
                "reception_date": normalize_date(reception_date),
                "sampled_by": sampled_by,
                "signature_name": signature_name,
                "signature_title": signature_title,
                "issue_location": issue_location,
                "issue_date": str(issue_date).strip(),
                "observations": observations,
            })
            preferences = st.session_state["preferences"]
            metadata_by_sample = preferences.setdefault("metadata_by_sample", {})
            metadata_by_sample[sample] = metadata.copy()
            global_metadata = metadata.copy()
            global_metadata.pop("sample_code", None)
            for field_name in ("client", "reception_date", "lot", "guide_number", "product", "request_number"):
                global_metadata.pop(field_name, None)
            preferences["metadata_defaults"] = global_metadata
            for other_sample, other_draft in metadata_drafts.items():
                other_draft.update(global_metadata)
                other_draft["sample_code"] = other_sample
            save_preferences(PREFERENCES_PATH, preferences)
            st.success("Datos generales actualizados y guardados como predeterminados para todas las muestras.")

        st.subheader("Firma del informe")
        uploaded_signature = st.file_uploader(
            "Reemplazar firma (PNG o JPEG)",
            type=["png", "jpg", "jpeg"],
            key="signature_upload",
        )
        signature_path = PROJECT_ROOT / SETTINGS.get("assets", {}).get("signature", "assets/signature.jpeg")
        signature_backup = signature_path.with_name(f"{signature_path.stem}.original{signature_path.suffix}")
        signature_col, restore_col = st.columns(2)
        with signature_col:
            if st.button("Aplicar firma nueva", disabled=uploaded_signature is None):
                if uploaded_signature is not None:
                    replace_signature(uploaded_signature.getvalue(), signature_path, signature_backup)
                    st.success("Firma reemplazada. La firma original quedó reservada para restaurarla.")
                    st.rerun()
        with restore_col:
            if st.button("Restaurar firma original", disabled=not signature_backup.is_file()):
                if restore_signature(signature_path, signature_backup):
                    st.success("Firma original restaurada.")
                    st.rerun()

        st.subheader("Fechas de ejecución por análisis")
        preferences = st.session_state["preferences"]
        execution_date_defaults = preferences.setdefault("execution_dates_by_sample", {}).setdefault(sample, {})
        initial_dates = _execution_dates_frame(
            _apply_catalog(results_for_sample(all_records, sample), catalog),
            execution_date_defaults,
        )
        edited_dates = st.data_editor(
            initial_dates,
            num_rows="fixed",
            width="stretch",
            key=f"execution_dates_{sample}",
            column_config={
                "Análisis": st.column_config.TextColumn(disabled=True),
                "Fecha inicio": st.column_config.TextColumn(help="Formato DD/MM/AAAA. Fecha detectada; puedes rectificarla."),
                "Fecha término": st.column_config.TextColumn(help="Formato DD/MM/AAAA. Fecha detectada; puedes rectificarla."),
            },
        )
        selected_dates: dict[str, dict[str, str]] = {}
        for _, row in edited_dates.iterrows():
            analysis_name = _text(row.get("Análisis", ""))
            if analysis_name:
                selected_dates[analysis_name.casefold()] = {
                    "start_date": normalize_date(_text(row.get("Fecha inicio", ""))),
                    "end_date": normalize_date(_text(row.get("Fecha término", ""))),
                }
        execution_date_defaults.update(selected_dates)
        save_preferences(PREFERENCES_PATH, preferences)

    with results_tab:
        st.subheader("Resultados editables")
        edited_frame = st.data_editor(
            frame.drop(columns=["_original"], errors="ignore"),
            num_rows="dynamic",
            width="stretch",
            key=f"results_editor_{sample}",
            column_config={
                "Incluir": st.column_config.CheckboxColumn("Incluir", default=True),
                "Resultado": st.column_config.TextColumn("Resultado", help="Se conserva como texto, incluidos <LD, ND y separadores decimales."),
                "Origen": st.column_config.TextColumn("Origen", disabled=True),
            },
        )
        original_records = list(frame.get("_original", []))
        if len(edited_frame) <= len(original_records):
            edited_frame["_original"] = original_records[: len(edited_frame)]
        else:
            edited_frame["_original"] = original_records + [None] * (len(edited_frame) - len(original_records))
        drafts[sample] = edited_frame
        current_results = _editor_records(edited_frame)
        preferences = st.session_state["preferences"]
        source_key = st.session_state.get("source_key", "")
        result_drafts = preferences.setdefault("result_drafts", {})
        result_drafts.setdefault(source_key, {})[sample] = serialize_result_drafts(current_results)
        save_preferences(PREFERENCES_PATH, preferences)
        modified_count = sum(record.modified for record in current_results)
        if modified_count:
            st.warning(f"Hay {modified_count} filas modificadas o agregadas; quedarán identificadas en la validación.")
        st.caption("Puedes editar celdas, agregar filas o eliminarlas. El Excel fuente no se modifica.")

    current_results = _editor_records(drafts[sample])
    for record in current_results:
        date_values = st.session_state["preferences"].get("execution_dates_by_sample", {}).get(
            sample, {},
        ).get(record.analysis_name.casefold())
        if date_values is not None:
            record.start_date = date_values.get("start_date", record.start_date)
            record.end_date = date_values.get("end_date", record.end_date)
    report_results = apply_catalog_limit_overrides(
        results_for_selected_analyses(current_results, selected_source_analyses),
        catalog,
    )
    current_metadata = SampleMetadata(**metadata)
    report = LaboratoryReport(
        metadata=current_metadata,
        language="en" if report_in_english else "es",
        selected_analyses=list(selected_analyses),
        results=report_results,
        warnings=list(st.session_state.get("source_warnings", [])),
    )
    report.warnings.extend(validate_report(report))

    with preview_tab:
        st.subheader("Vista previa del informe")
        st.markdown(render_report_html(report, SETTINGS["report"]["rows_per_page"]), unsafe_allow_html=True)

    with generate_tab:
        st.subheader("Validación final")
        included_results = [item for item in report.results if item.include]
        st.write(f"Muestra: **{sample}**")
        st.write(f"Análisis: **{len(selected_analyses)}** · Resultados incluidos: **{len(included_results)}**")
        unique_warnings = list(dict.fromkeys(report.warnings))
        if unique_warnings:
            for warning in unique_warnings:
                st.warning(warning)
        else:
            st.success("No se detectaron advertencias.")
        if st.button("Generar PDF", type="primary", disabled=not included_results):
            pdf_settings = {**SETTINGS["report"], "assets": SETTINGS.get("assets", {})}
            st.session_state["pdf_bytes"] = generate_pdf(report, pdf_settings)
            st.session_state["pdf_name"] = f"Informe_{sample}_{datetime.now():%Y%m%d}.pdf"
        if st.session_state.get("pdf_bytes"):
            st.download_button(
                "Descargar PDF",
                data=st.session_state["pdf_bytes"],
                file_name=st.session_state["pdf_name"],
                mime="application/pdf",
                width="stretch",
            )

    with catalog_tab:
        _render_catalog(catalog)


if __name__ == "__main__":
    main()