from openpyxl import Workbook

from src.excel_reader import read_general_rows, read_pag_matrix
from src.general_results_parser import parse_general_results


def test_reads_general_headers_and_pag_matrix(tmp_path) -> None:
    path = tmp_path / "input.xlsx"
    workbook = Workbook()
    general = workbook.create_sheet("Resultados_generales_2026")
    for row in range(1, 5):
        general.append([])
    general.append(["JOB", "ANALISIS", "ANALITO", "VALOR PRE", "UNIDAD DE EXPRESION"])
    general.append(["TM26-0001", "Ensayo", "Analito X", "<0,5", "mg/kg"])
    pag = workbook.create_sheet("PAG")
    for row in [
        ("", "ID Muestra", "ID-1"),
        ("", "Laboratorio", "Lab"),
        ("", "Formulario", "1"),
        ("", "Job", "TM26-0001"),
        ("", "Producto", "P"),
        ("Tipo", "Ácido Graso", "% Area"),
        ("Sat", "C4:0", "ND"),
    ]:
        pag.append(row)
    workbook.save(path)

    general_rows = read_general_rows(path)
    pag_rows = read_pag_matrix(path)

    assert general_rows[0]["JOB"] == "TM26-0001"
    assert general_rows[0]["VALOR PRE"] == "<0,5"
    assert pag_rows[6][2] == "ND"


def test_execution_dates_in_columns_k_and_l_reach_result_records(tmp_path) -> None:
    path = tmp_path / "dates.xlsx"
    workbook = Workbook()
    general = workbook.active
    general.title = "Resultados_generales_2026"
    for _ in range(4):
        general.append([])
    general.append([
        "JOB", "ANALISIS", "ANALITO", "VALOR PRE", "UNIDAD DE EXPRESION",
        "OTRA A", "OTRA B", "OTRA C", "OTRA D", "OTRA E",
        "FECHA INICIO", "FECHA TÉRMINO",
    ])
    general.append([
        "TM26-0002", "Ensayo", "Analito X", "1.2", "mg/kg",
        "", "", "", "", "", "2026-11-18", "2026-11-20",
    ])
    workbook.save(path)

    rows = read_general_rows(path)
    results, _ = parse_general_results(rows)

    assert results[0].start_date == "2026-11-18"
    assert results[0].end_date == "2026-11-20"