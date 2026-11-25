from src.report_models import ResultRecord
from src.sample_service import (
    analyses_for_sample,
    metadata_for_sample,
    restore_result_drafts,
    results_for_sample,
    results_for_selected_analyses,
    serialize_result_drafts,
)


def test_selects_one_analysis_from_multiple() -> None:
    records = [
        ResultRecord("TM26-1", "A", "Análisis A", "X", "1", "mg/kg"),
        ResultRecord("TM26-1", "B", "Análisis B", "Y", "2", "mg/kg"),
        ResultRecord("TM26-1", "C", "Análisis C", "Z", "3", "mg/kg"),
    ]

    assert analyses_for_sample(records, "TM26-1") == ["Análisis A", "Análisis B", "Análisis C"]
    assert [item.analysis_name for item in results_for_sample(records, "TM26-1", ["Análisis B"])] == [
        "Análisis B"
    ]


def test_selects_pag_by_display_name_when_code_is_pag() -> None:
    record = ResultRecord("TM26-1", "PAG", "Perfil Ácidos Grasos", "C18:1", "21.99", "% Area")

    assert results_for_selected_analyses([record], ["Perfil Ácidos Grasos"]) == [record]


def test_result_drafts_restore_edits_and_deleted_rows() -> None:
    source_records = [
        ResultRecord(
            "TM26-1", "PAG", "Perfil de Ácidos Grasos", "C18:1", "20.0", "% Area",
            source_sheet="PAG", source_row=7,
            original_values={"analyte": "C18:1", "unit": "% Area"},
        ),
        ResultRecord(
            "TM26-1", "PAG", "Perfil de Ácidos Grasos", "C20:5", "0.1", "% Area",
            source_sheet="PAG", source_row=8,
            original_values={"analyte": "C20:5", "unit": "% Area"},
        ),
    ]
    edited = ResultRecord(
        "TM26-1", "PAG", "Perfil de Ácidos Grasos", "C18:1", "21.5", "% Area",
        method_description="Método actualizado", source_sheet="PAG", source_row=7,
        original_values={"analyte": "C18:1", "unit": "% Area"}, modified=True,
    )

    restored = restore_result_drafts(source_records, serialize_result_drafts([edited]))

    assert len(restored) == 1
    assert restored[0].result == "21.5"
    assert restored[0].method_description == "Método actualizado"


def test_result_drafts_restore_manual_rows() -> None:
    manual = ResultRecord(
        "TM26-1", "Manual", "Ensayo manual", "X", "1.25", "mg/kg",
        source_sheet="Manual", modified=True,
    )

    restored = restore_result_drafts([], serialize_result_drafts([manual]))

    assert len(restored) == 1
    assert restored[0].analyte == "X"
    assert restored[0].result == "1.25"


def test_metadata_priority_fields_come_from_excel_columns() -> None:
    record = ResultRecord(
        "TM26-1", "A", "Análisis A", "X", "1", "mg/kg",
        original_values={
            "PROVEEDOR CLIENTE O ESTANQUE SBH": "Cliente Excel",
            "FECHA INGRESO": "2026-11-20",
            "LOTE": "LOTE-7",
            "N° DE GUIA": "GUIA-123",
            "NOMBRE ARTICULO": "Aceite",
            "N SOLICITUD DE ANALISIS": "SOL-456",
        },
    )

    metadata = metadata_for_sample([record], "TM26-1")

    assert metadata.client == "Cliente Excel"
    assert metadata.reception_date == "2026-11-20"
    assert metadata.lot == "LOTE-7"
    assert metadata.guide_number == "GUIA-123"
    assert metadata.product == "Aceite"
    assert metadata.request_number == "SOL-456"