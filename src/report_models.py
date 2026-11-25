from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SampleMetadata:
    sample_code: str = ""
    request_number: str = ""
    sample_description: str = ""
    requested_by: str = "Aceites SBH Spa."
    client: str = ""
    contact: str = "Yanira Martinez"
    product: str = ""
    lot: str = ""
    container: str = ""
    guide_number: str = ""
    sampling_address: str = "Calle D Lote 14, Parque Industrial 1 Escuadrón - Coronel."
    sampling_date: str = ""
    reception_date: str = ""
    client_reference: str = ""
    reception_temperature: str = ""
    control_type: str = ""
    sampled_by: str = "Aceites SBH Spa."
    sample_count: str = "1"
    report_number: str = ""
    signature_name: str = "María José Garcés"
    signature_title: str = "Jefe de Laboratorio Químico"
    issue_location: str = ""
    issue_date: str = ""
    observations: str = ""


@dataclass
class ResultRecord:
    sample_code: str
    analysis_code: str
    analysis_name: str
    analyte: str
    result: str = ""
    unit: str = ""
    detection_limit: str = ""
    quantification_limit: str = ""
    method_code: str = ""
    method_description: str = ""
    start_date: str = ""
    end_date: str = ""
    source_sheet: str = ""
    source_row: int | None = None
    include: bool = True
    original_values: dict[str, Any] = field(default_factory=dict)
    modified: bool = False


@dataclass
class LaboratoryReport:
    metadata: SampleMetadata
    language: str = "es"
    selected_analyses: list[str] = field(default_factory=list)
    results: list[ResultRecord] = field(default_factory=list)
    execution_dates: dict[str, dict[str, str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)