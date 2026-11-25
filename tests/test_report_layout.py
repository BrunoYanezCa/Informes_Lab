from typing import Any, cast

from reportlab.lib.styles import ParagraphStyle

from src.pdf_generator import _horizontal_analysis_section, _method_summary_table
from src.report_models import LaboratoryReport, ResultRecord, SampleMetadata


def _styles() -> dict[str, ParagraphStyle]:
    return {
        name: ParagraphStyle(name=name)
        for name in (
            "TableHeading", "MethodCell", "SectionCell", "MatrixLabel", "SampleIdentity",
            "ResultCell", "PagGroup", "MetaLabel", "MetaValue", "MetaSection",
        )
    }


def test_small_analysis_uses_horizontal_template_matrix() -> None:
    records = [
        ResultRecord("TM26-1", "A", "Ensayo A", "C14:0", "<0,5", "% Area", "0,5", "1,0"),
        ResultRecord("TM26-1", "A", "Ensayo A", "C16:0", "18,4", "% Area", "0,5", "1,0"),
    ]
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1", sample_description="Muestra sintética"),
        selected_analyses=["Ensayo A"],
        results=records,
    )

    blocks = _horizontal_analysis_section(records, report, _styles(), 180 * 2.8346)

    assert blocks is not None
    method_table = blocks[0]
    matrix_table = blocks[2]
    assert method_table._cellvalues[0][0].text == "Ensayos"
    assert method_table._cellvalues[0][1].text == "Método/Título"
    assert matrix_table._cellvalues[0][0].text == "Análisis"
    assert matrix_table._cellvalues[1][0].text == "Unidades"
    assert matrix_table._cellvalues[2][0].text == "L.D."
    assert matrix_table._cellvalues[3][0].text == "L.C."
    assert matrix_table._cellvalues[4][0].text == "Identificación de Muestras"
    assert matrix_table._cellvalues[5][0].text == "Muestra sintética"


def test_duplicate_analyte_unit_uses_vertical_fallback() -> None:
    records = [
        ResultRecord("TM26-1", "A", "Ensayo A", "C14:0", "<0,5", "% Area"),
        ResultRecord("TM26-1", "A", "Ensayo A", "C14:0", "0,4", "% Area"),
    ]
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1"),
        selected_analyses=["Ensayo A"],
        results=records,
    )

    assert _horizontal_analysis_section(records, report, _styles(), 180 * 2.8346) is None


def test_pag_many_analytes_has_one_method_summary_row() -> None:
    records = [
        ResultRecord(
            "TM26-PAG",
            "PAG",
            "Perfil Ácidos Grasos",
            f"C{i}:0",
            "ND",
            "% Area",
            "0,1",
            "0,3",
            "MTH-PAG",
            "Esquema único PAG",
        )
        for i in range(1, 81)
    ]

    method_table = _method_summary_table(records, _styles(), 180 * 2.8346)
    method_rows = cast(Any, method_table)._cellvalues

    assert len(method_rows) == 2
    assert method_rows[0][0].text == "Ensayos"
    assert method_rows[1][0].text == "Perfil de Ácidos Grasos"
    assert method_rows[1][1].text == "MTH-PAG - Esquema único PAG"


def test_pag_table_uses_only_requested_unit_columns_and_keeps_categories() -> None:
    from src.pdf_generator import _pag_results_table

    records = [
        ResultRecord(
            "TM26-1", "PAG", "Perfil Ácidos Grasos", "C16:0", "12.2", "% Area", "0.1", "0.3",
            original_values={"category": "Ácidos Grasos Saturados"},
        ),
        ResultRecord(
            "TM26-1", "PAG", "Perfil Ácidos Grasos", "C16:0", "10.01", "g/100g", "0.2", "0.4",
            original_values={"category": "Ácidos Grasos Saturados"},
        ),
    ]

    table = _pag_results_table(records, _styles(), 180 * 2.8346)
    rows = cast(Any, table)._cellvalues

    assert [cell.text for cell in rows[0]] == ["Analito", "% Area", "g/100g"]
    assert rows[1][0].text == "Ácidos Grasos Saturados"
    assert [cell.text for cell in rows[2]] == ["C16:0", "12.20", "10.01"]
    table.wrap(180 * 2.8346, 250 * 2.8346)


def test_general_results_table_summarizes_pag_once() -> None:
    from src.pdf_generator import _general_results_table

    records = [
        ResultRecord("TM26-1", "PAG", "Perfil Ácidos Grasos", f"C{i}:0", "ND", "% Area")
        for i in range(1, 21)
    ]
    records.extend([
        ResultRecord("TM26-1", "PAG", "Perfil Ácidos Grasos", "C20:5 n3 (EPA)", "0.13", "% Area"),
        ResultRecord("TM26-1", "PAG", "Perfil Ácidos Grasos", "C22:6 n3 (DHA)", "0.21", "% Area"),
    ])
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1", sample_description="Oleina"),
        selected_analyses=["Perfil Ácidos Grasos"],
        results=records,
    )

    table = _general_results_table(records, report, _styles(), 180 * 2.8346)
    rows = cast(Any, table)._cellvalues

    assert len(rows) == 3
    assert rows[1][0].text == "Perfil de Ácidos Grasos"
    assert rows[1][1].text == "Ver detalle"
    assert rows[2][0].text == "EPA+DHA"
    assert rows[2][1].text == "0.34"
    assert rows[2][2].text == "% Area"


def test_execution_dates_table_uses_rectified_record_dates() -> None:
    from src.pdf_generator import _execution_dates_table

    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1"),
        selected_analyses=["Ensayo A"],
        results=[
            ResultRecord("TM26-1", "A", "Ensayo A", "X", "1", "mg/kg", start_date="2026-07-21", end_date="2026-07-22"),
        ],
    )
    styles = {"DateHeading": ParagraphStyle(name="DateHeading"), "DateCell": ParagraphStyle(name="DateCell")}

    table = _execution_dates_table(report, styles)
    rows = cast(Any, table)._cellvalues

    assert [cell.text for cell in rows[1]] == ["Ensayo A", "21/07/2026", "22/07/2026"]