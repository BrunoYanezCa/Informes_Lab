from src.report_models import LaboratoryReport, ResultRecord, SampleMetadata
from src.report_renderer import render_report_html
from src.report_i18n import format_date, normalize_date


def test_small_analysis_preview_uses_general_results_table() -> None:
    records = [
        ResultRecord(
            "TM26-1",
            "A",
            "Ensayo de prueba",
            analyte,
            result,
            "% Area",
            "0,5",
            "1,0",
            "MET-01",
            "Método confirmado",
        )
        for analyte, result in (("C14:0", "<0,5"), ("C16:0", "18,4"))
    ]
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1", sample_description="Muestra sintética"),
        selected_analyses=["Ensayo de prueba"],
        results=records,
    )

    html = render_report_html(report)

    assert "Ensayos" in html
    assert "Método/Título" in html
    assert 'class="general-results"' in html
    assert "ANÁLISIS" in html
    assert "L.D." in html and "L.C." in html
    assert "ID MUESTRA" not in html
    assert "C14:0" in html and "C16:0" in html
    assert "&lt;0,5" in html and "18,4" in html
    assert "result-matrix" not in html

def test_pag_preview_shows_one_scheme_for_many_analytes() -> None:
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
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-PAG"),
        selected_analyses=["Perfil Ácidos Grasos"],
        results=records,
    )

    html = render_report_html(report)

    assert html.count('class="assay-method"') == 1
    assert html.count("Esquema único PAG") == 1
    assert html.count("<td>C") >= 80


def test_pag_preview_places_multiple_units_in_separate_columns() -> None:
    records = [
        ResultRecord(
            "TM26-1", "PAG", "Perfil Ácidos Grasos", "C18:1", result, unit, "0.1", "0.2",
            original_values={"category": "Monoinsaturados"},
        )
        for unit, result in (("% Area", "21.99"), ("g/100g", "17.59"))
    ]
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1"),
        selected_analyses=["Perfil Ácidos Grasos"],
        results=records,
    )

    html = render_report_html(report)

    assert "Resultados Generales" in html
    assert "Resultados Perfil de Ácidos Grasos" in html
    assert "<th>% Area</th><th>g/100g</th>" in html
    assert "<td>C18:1</td><td>21.99</td><td>17.59</td>" in html
    assert "<td>Perfil de Ácidos Grasos</td><td>Ver detalle</td><td>% Area / g/100g</td><td>0.1</td><td>0.2</td>" in html
    assert "Monoinsaturados" in html


def test_pag_preview_shows_epa_dha_sum_only_in_general_results() -> None:
    records = [
        ResultRecord("TM26-1", "PAG", "Perfil de Ácidos Grasos", analyte, result, "% Area")
        for analyte, result in (("C20:5 n3 (EPA)", "0.13"), ("C22:6 n3 (DHA)", "0.21"))
    ]
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1"),
        selected_analyses=["Perfil de Ácidos Grasos"],
        results=records,
    )

    html = render_report_html(report)
    methodology = html.split('class="assay-method"', 1)[1].split("</table>", 1)[0]

    assert "EPA+DHA</td><td>0.34</td><td>% Area" in html
    assert "EPA+DHA" not in methodology

def test_preview_separates_client_and_sample_metadata() -> None:
    report = LaboratoryReport(
        metadata=SampleMetadata(
            sample_code="TM26-1",
            requested_by="Solicitante",
            contact="Contacto",
            sampling_address="Dirección cliente",
            request_number="SOL-456",
            lot="L-1",
            container="TK-2",
            guide_number="G-3",
        ),
        results=[
            ResultRecord(
                "TM26-1", "A", "Ensayo", "X", "1", "mg/kg",
                start_date="2026-11-18", end_date="2026-11-20",
            )
        ],
        selected_analyses=["Ensayo"],
    )

    html = render_report_html(report)

    assert "Datos del Cliente" in html
    assert "Datos de la muestra" in html
    assert "Solicitud de Análisis:" in html and "SOL-456" in html
    assert "18/11/2026" in html and "20/11/2026" in html
    assert html.index("Fecha de Inicio Ensayo:") < html.index("Solicitud de Análisis:")
    assert "Dirección cliente" in html
    assert "L-1" in html and "TK-2" in html and "G-3" in html
    assert "Cantidad de muestras" not in html


def test_english_preview_translates_labels_and_formats_dates() -> None:
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1", sampling_date="2026-07-21"),
        language="en",
        selected_analyses=["Test"],
        results=[ResultRecord("TM26-1", "A", "Test", "Analyte", "1", "mg/kg")],
    )

    html = render_report_html(report)

    assert "Customer Information" in html
    assert "Sample Information" in html
    assert "Analysis / Methodology" in html
    assert "General Results" in html
    assert "Sample Identification" in html
    assert "21/07/2026" in html
    assert "Página 1 de 1" not in html


def test_date_helpers_display_day_first_and_normalize_to_iso() -> None:
    assert format_date("2026/07/21") == "21/07/2026"
    assert format_date("21/07/2026") == "21/07/2026"
    assert normalize_date("21/07/2026") == "2026-07-21"