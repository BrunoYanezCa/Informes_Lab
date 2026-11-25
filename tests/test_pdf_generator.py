import re
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import pytest
from pypdf import PdfReader
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Table

from src.pdf_generator import NumberedCanvas, _metadata_table, format_issue_date, generate_pdf
from src.report_models import LaboratoryReport, ResultRecord, SampleMetadata
from src.utils import load_yaml


def test_report_title_always_uses_selected_sample_code() -> None:
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-99999", report_number="TM26-01930"),
        selected_analyses=["Análisis"],
        results=[ResultRecord("TM26-99999", "A", "Análisis", "X", "1", "mg/kg")],
    )

    pdf = generate_pdf(report, {"page_size": "A4", "legal_notices": {}})
    pages = [page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages]

    assert "TM26-99999" in " ".join(pages)
    assert "TM26-01930" not in " ".join(pages)


def test_generates_multipage_pdf_for_many_results() -> None:
    results = [
        ResultRecord("TM26-1", "PAG", "Perfil Ácidos Grasos", f"C{i}:0", "ND", "% Area")
        for i in range(1, 81)
    ]
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1"),
        selected_analyses=["Perfil Ácidos Grasos"],
        results=results,
    )

    pdf = generate_pdf(report, {"page_size": "A4", "legal_notices": {}})

    assert pdf.startswith(b"%PDF-")
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) > 1
    assert len(re.findall(rb"/Subtype\s*/Image\b", pdf)) >= 2
    assert b"\xef\xbf\xbd" not in pdf


def test_legal_copy_has_repaired_accents_and_no_replacement_characters() -> None:
    settings = load_yaml("config/settings.yaml")
    report_settings = settings["report"]
    all_copy = " ".join(report_settings["legal_notices"].values())
    all_copy += " " + " ".join(settings["report"]["institutional_footer"].values())

    assert "\ufffd" not in all_copy
    assert "compañía" in all_copy
    assert "Société Générale de Surveillance" in all_copy
    assert settings["report"]["institutional_footer"]["address"] == "Coronel, Chile"


def test_signature_date_uses_requested_spanish_format() -> None:
    assert format_issue_date("2026-11-16") == "16 de Noviembre del 2026"
    assert format_issue_date("18 de Noviembre del 2026") == "18 de Noviembre del 2026"


def test_metadata_defaults_and_removed_fields() -> None:
    metadata = SampleMetadata(request_number="SOL-456")
    report = LaboratoryReport(metadata=metadata)
    styles = {
        "MetaLabel": ParagraphStyle(name="MetaLabel"),
        "MetaValue": ParagraphStyle(name="MetaValue"),
        "MetaSection": ParagraphStyle(name="MetaSection"),
    }

    table = _metadata_table(report, styles)
    text = " ".join(
        cell.text if hasattr(cell, "text") else str(cell)
        for row in cast(Any, table)._cellvalues
        for cell in row
    )

    assert metadata.requested_by == "Aceites SBH Spa."
    assert metadata.contact == "Yanira Martinez"
    assert metadata.sampling_address == "Calle D Lote 14, Parque Industrial 1 Escuadrón - Coronel."
    assert metadata.sampled_by == "Aceites SBH Spa."
    assert "Temperatura de Recepción" not in text
    assert "Ref. Cliente" not in text
    assert "Tipo Control" not in text
    assert "Datos del Cliente" in text
    assert "Datos de la muestra" in text
    assert "Solicitud de Análisis:" in text
    assert "SOL-456" in text
    rows = cast(Any, table)._cellvalues
    assert rows[-1][0].text == "Fecha de Término Ensayo:"
    assert rows[-1][2].text == "Solicitud de Análisis:"
    assert "Lote:" in text
    assert "Contenedor:" in text
    assert "Nº de Guía:" in text
    assert "Cantidad Muestras:" not in text


def test_pdf_receives_editable_signature_values(monkeypatch) -> None:
    captured = {}

    def capture_signature(self) -> None:
        captured["name"] = self._signature_name
        captured["title"] = self._signature_title
        captured["date"] = self._issue_date

    monkeypatch.setattr(NumberedCanvas, "_draw_signature", capture_signature)
    report = LaboratoryReport(
        metadata=SampleMetadata(
            sample_code="TM26-1",
            signature_name="Nombre editable",
            signature_title="Cargo editable",
            issue_location="Puerto Varas",
            issue_date="2026-11-16",
        ),
        selected_analyses=["Análisis"],
        results=[ResultRecord("TM26-1", "A", "Análisis", "X", "1", "mg/kg")],
    )

    generate_pdf(report, {"page_size": "A4", "legal_notices": {}})

    assert captured == {
        "name": "Nombre editable",
        "title": "Cargo editable",
        "date": "16 de Noviembre del 2026",
    }


def test_signature_image_is_centered_with_name_and_title(monkeypatch) -> None:
    captured = {}
    signature = NumberedCanvas(
        BytesIO(),
        signature_path=Path("assets/signature.jpeg"),
        signature_name="Nombre",
        signature_title="Cargo",
        page_size=A4,
    )
    monkeypatch.setattr(
        signature,
        "drawImage",
        lambda path, x, y, width, height, **kwargs: captured.update(
            x=x, width=width,
        ),
    )

    signature._draw_signature()

    assert captured["x"] + captured["width"] / 2 == pytest.approx(A4[0] - 40 * mm)


def test_pag_section_starts_on_new_page_after_general_results(monkeypatch) -> None:
    captured = {}

    def capture_story(self, story, **kwargs):
        captured["story"] = story

    monkeypatch.setattr("src.pdf_generator.SimpleDocTemplate.build", capture_story)
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1"),
        selected_analyses=["Ensayo", "Perfil de Ácidos Grasos"],
        results=[
            ResultRecord("TM26-1", "A", "Ensayo", "Humedad", "1.2", "%"),
            ResultRecord("TM26-1", "PAG", "Perfil de Ácidos Grasos", "C18:1", "1.2", "% Area"),
        ],
    )

    generate_pdf(report, {"page_size": "A4", "legal_notices": {}})
    story = captured["story"]
    general_heading = next(index for index, item in enumerate(story) if getattr(item, "text", "") == "Resultados Generales")
    general_table = next(index for index in range(general_heading + 1, len(story)) if isinstance(story[index], Table))

    assert isinstance(story[general_table + 1], PageBreak)


def test_pag_title_is_on_page_two_in_generated_pdf() -> None:
    report = LaboratoryReport(
        metadata=SampleMetadata(sample_code="TM26-1", lot="L-1", container="TK-2", guide_number="G-3"),
        selected_analyses=["Ensayo", "Perfil de Ácidos Grasos"],
        results=[
            ResultRecord("TM26-1", "A", "Ensayo", "Humedad", "1.2", "%"),
            ResultRecord("TM26-1", "PAG", "Perfil de Ácidos Grasos", "C18:1", "1.2", "% Area"),
        ],
    )
    settings = load_yaml("config/settings.yaml")
    pdf = generate_pdf(report, {**settings["report"], "assets": settings["assets"]})
    pages = [page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages]

    assert "Resultados Generales" in pages[0]
    assert "Resultados Perfil de Ácidos Grasos" not in pages[0]
    assert "Resultados Perfil de Ácidos Grasos" in pages[1]
    assert "Lote:" in pages[0] and "L-1" in pages[0]
    assert "Contenedor:" in pages[0] and "TK-2" in pages[0]
    assert "Nº de Guía:" in pages[0] and "G-3" in pages[0]
    assert "Cantidad Muestras:" not in pages[0]


def test_english_report_translates_pdf_labels_and_formats_dates() -> None:
    report = LaboratoryReport(
        metadata=SampleMetadata(
            sample_code="TM26-1",
            requested_by="Client Ltd.",
            sampling_date="2026-07-21",
            reception_date="2026-07-22",
            issue_date="2026-07-23",
        ),
        language="en",
        selected_analyses=["General test", "Perfil de Ácidos Grasos"],
        results=[
            ResultRecord("TM26-1", "A", "General test", "Humedad", "1.20", "%"),
            ResultRecord("TM26-1", "PAG", "Perfil de Ácidos Grasos", "C18:1", "1.2", "% Area"),
        ],
    )
    settings = load_yaml("config/settings.yaml")
    pdf = generate_pdf(report, {**settings["report"], "assets": settings["assets"]})
    pages = [page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages]
    full_text = " ".join(pages)

    assert "Laboratory Report" in full_text
    assert "Customer Information" in full_text
    assert "Sample Information" in full_text
    assert "Analysis / Methodology" in full_text
    assert "General Results" in full_text
    assert "Fatty Acid Profile Results" in full_text
    assert "Moisture" in full_text
    assert "D.L." in full_text and "Q.L." in full_text
    assert "21/07/2026" in full_text
    assert "22/07/2026" in full_text
    assert "23 July 2026" in full_text
    assert "Resultados Generales" not in full_text