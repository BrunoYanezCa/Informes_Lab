from __future__ import annotations

from datetime import date, datetime


TRANSLATIONS = {
    "Informe de Laboratorio": "Laboratory Report",
    "Datos del Cliente": "Customer Information",
    "Análisis solicitado por:": "Requested by:",
    "Nombre de Contacto:": "Contact Name:",
    "Dirección:": "Address:",
    "Datos de la muestra": "Sample Information",
    "Solicitud de Análisis:": "Analysis Request:",
    "Perfil de Ácidos Grasos": "Fatty Acid Profile",
    "Perfil Ácidos Grasos": "Fatty Acid Profile",
    "Perfil de ácidos grasos": "Fatty Acid Profile",
    "Resultados Perfil de Ácidos Grasos": "Fatty Acid Profile Results",
    "Ácidos Grasos Saturados": "Saturated Fatty Acids",
    "Ácidos Grasos Monoinsaturados": "Monounsaturated Fatty Acids",
    "Ácidos Grasos Poliinsaturados": "Polyunsaturated Fatty Acids",
    "Saturados": "Saturated Fatty Acids",
    "Monoinsaturados": "Monounsaturated Fatty Acids",
    "Poliinsaturados": "Polyunsaturated Fatty Acids",
    "Totales": "Totals",
    "Humedad": "Moisture",
    "FFA (Ácido oleico)": "FFA (Oleic Acid)",
    "Índice de peróxido": "Peroxide Value",
    "Impureza Insoluble en hexano": "Hexane-Insoluble Impurities",
    "Densidad": "Density",
    "Determinación De Densidad (Peso aparente por unidad de volumen)": "Density Determination (Apparent Weight per Unit Volume)",
    "Producto:": "Product:",
    "Identificación": "Sample Identification",
    "Lote:": "Lot:",
    "Contenedor:": "Container:",
    "Nº de Guía:": "Guide No.:",
    "Muestreado Por:": "Sampled by:",
    "Fecha de Muestreo:": "Sampling Date:",
    "Fecha de Recepción:": "Reception Date:",
    "Fecha de Inicio Ensayo:": "Test Start Date:",
    "Fecha de Término Ensayo:": "Test End Date:",
    "Análisis / Metodología": "Analysis / Methodology",
    "Ensayos": "Assays",
    "Método/Título": "Method/Title",
    "Resultados Generales": "General Results",
    "ANÁLISIS": "ANALYSIS",
    "RESULTADO": "RESULT",
    "UNIDAD": "UNIT",
    "Análisis": "Analysis",
    "Analito": "Analyte",
    "Resultado": "Result",
    "Unidades": "Units",
    "Ver detalle": "See details",
    "L.D.": "D.L.",
    "L.C.": "Q.L.",
    "L.D. = Limite de Detección": "D.L. = Detection Limit",
    "L.C. = Limite de Cuantificación": "Q.L. = Quantification Limit",
    "- = Muestra no analizada": "- = Sample not analyzed",
    "ND = No Detectado": "ND = Not Detected",
    "FECHA EJECUCION ANALISIS": "ANALYSIS EXECUTION DATES",
    "Fecha Inicio": "Start Date",
    "Fecha Término (Validación)": "End Date (Validation)",
    "Notas:": "Notes:",
    "Observaciones y avisos": "Notes and notices",
    "Página": "Page",
    "Página 1 de 1": "Page 1 of 1",
    "Los resultados aplican a la muestra tal como se recibió.": "Results apply to the sample as received.",
    "Este informe es emitido, a pedido del cliente, bajo las condiciones generales de servicio de la compañía informadas en la cotización. El cliente debe tener en cuenta las definiciones de limitación de responsabilidad, indemnización y jurisdicción contenidas en el documento citado. (Copia disponible a petición).": "This report is issued at the client's request under the general terms of service provided in the quotation. The client should review the limitations of liability, indemnity, and jurisdiction contained in that document. (Copy available upon request).",
    "Los resultados solo son válidos para las muestras analizadas. Se prohíbe su reproducción total o parcial.": "Results are valid only for the samples analyzed. Total or partial reproduction is prohibited.",
    "La muestra ha sido proporcionada por el cliente y los resultados aplican a la muestra tal como fue recibida. SGS Chile Ltda. no es responsable por la información proporcionada ni por las condiciones, el estado o la preservación de la muestra. Los datos proporcionados por el cliente están claramente identificados en el presente informe.": "The sample was provided by the client and the results apply to the sample as received. SGS Chile Ltda. is not responsible for the information provided or for the sample's condition, state, or preservation. Client-provided information is clearly identified in this report.",
    "Miembro del Grupo SGS (Société Générale de Surveillance)": "Member of the SGS Group (Société Générale de Surveillance)",
}


def is_english(language: str) -> bool:
    return language.casefold() in {"en", "english", "inglés", "ingles"}


def translate(value: str, language: str) -> str:
    return TRANSLATIONS.get(value, value) if is_english(language) else value


def parse_date(value: str | date | datetime) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    return None


def format_date(value: str | date | datetime) -> str:
    parsed = parse_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else str(value or "")


def normalize_date(value: str | date | datetime) -> str:
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else str(value or "").strip()