from src.report_models import LaboratoryReport, ResultRecord, SampleMetadata
from src.report_validator import validate_report


def test_warns_for_missing_method_dates_and_empty_result() -> None:
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1", reception_date="2026-01-02"),
        selected_analyses=["Análisis A"],
        results=[
            ResultRecord(
                "TM26-1",
                "A",
                "Análisis A",
                "Analito X",
                result="",
                unit="mg/kg",
                source_row=12,
            )
        ],
    )

    warnings = validate_report(report)

    assert any("método o esquema" in warning for warning in warnings)
    assert any("fechas de ejecución" in warning for warning in warnings)
    assert any("falta el resultado" in warning for warning in warnings)