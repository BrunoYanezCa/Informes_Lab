from src.general_results_parser import parse_general_results


def test_keeps_qualifiers_and_skips_pag_aggregate() -> None:
    rows = [
        {
            "JOB": "TM26-0001",
            "ANALISIS": "Química",
            "ANALITO": "Analito A",
            "VALOR PRE": "<0,5",
            "UNIDAD DE EXPRESION": "mg/kg",
        },
        {
            "JOB": "TM26-0001",
            "ANALISIS": "Perfil Ácidos Grasos",
            "ANALITO": "PAG",
            "VALOR PRE": 1.2,
            "UNIDAD DE EXPRESION": "% Area",
        },
    ]

    results, warnings = parse_general_results(rows)

    assert len(results) == 1
    assert results[0].result == "<0,5"
    assert "PAG" in warnings[0]


def test_execution_dates_are_read_from_excel_start_and_end_headers() -> None:
    rows = [{
        "JOB": "TM26-0001",
        "ANALISIS": "Química",
        "ANALITO": "Analito A",
        "VALOR PRE": "1.2",
        "UNIDAD DE EXPRESION": "mg/kg",
        "FECHA INICIO": "2026-11-18",
        "FECHA TÉRMINO": "2026-11-20",
    }]

    results, _ = parse_general_results(rows)

    assert results[0].start_date == "2026-11-18"
    assert results[0].end_date == "2026-11-20"