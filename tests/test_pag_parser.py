from src.pag_parser import parse_pag_results


def test_unpivots_two_units_without_combining_values() -> None:
    rows = [
        ("", "ID Muestra", "ID-ANON-1", "ID-ANON-1"),
        ("", "Laboratorio", "Lab", "Lab"),
        ("", "Formulario", "10", "10"),
        ("", "Job", "TM26-0001", "TM26-0001"),
        ("", "Producto", "Producto", "Producto"),
        ("Tipo", "Ácido Graso", "% Area ", "g/100g"),
        ("Sat", "C4:0", "ND", "<0,5"),
    ]

    results, warnings = parse_pag_results(rows, "TM26-0001")

    assert [(item.analyte, item.unit, item.result) for item in results] == [
        ("C4:0", "% Area", "ND"),
        ("C4:0", "g/100g", "<0,5"),
    ]
    assert warnings == []


def test_warns_when_job_and_unit_repeat_in_pag_columns() -> None:
    rows = [
        ("", "ID Muestra", "ID-1", "ID-2"),
        ("", "Laboratorio", "Lab", "Lab"),
        ("", "Formulario", "10", "10"),
        ("", "Job", "TM26-0001", "TM26-0001"),
        ("", "Producto", "P", "P"),
        ("Tipo", "Ácido Graso", "% Area", "% Area"),
        ("Sat", "C4:0", "ND", "0.4"),
    ]

    _, warnings = parse_pag_results(rows, "TM26-0001")

    assert any("columnas PAG repetidas" in warning for warning in warnings)


def test_unpivots_forty_analytes_across_two_units() -> None:
    rows = [
        ("", "ID Muestra", "ID-ANON-1", "ID-ANON-1"),
        ("", "Laboratorio", "Lab", "Lab"),
        ("", "Formulario", "10", "10"),
        ("", "Job", "TM26-0001", "TM26-0001"),
        ("", "Producto", "Producto", "Producto"),
        ("Tipo", "Ácido Graso", "% Area", "g/100g"),
    ]
    rows.extend(("", f"C{i}:0", f"{i}.1", f"{i}.2") for i in range(1, 41))

    results, _ = parse_pag_results(rows, "TM26-0001")

    assert len(results) == 80
    assert len({(item.analyte, item.unit) for item in results}) == 80


def test_preserves_pag_category_for_result_sections() -> None:
    rows = [
        ("", "ID Muestra", "ID-1"),
        ("", "Laboratorio", "Lab"),
        ("", "Formulario", "10"),
        ("", "Job", "TM26-0001"),
        ("", "Producto", "Producto"),
        ("Tipo", "Ácido Graso", "% Area"),
        ("Saturados", "C14:0", "0.27"),
        (None, "C16:0", "12.25"),
        ("Monoinsaturados", "C18:1 n9", "21.99"),
    ]

    results, _ = parse_pag_results(rows, "TM26-0001")

    assert [item.original_values["category"] for item in results] == [
        "Saturados", "Saturados", "Monoinsaturados",
    ]


def test_normalizes_totals_category_capitalization() -> None:
    rows = [
        ("", "ID Muestra", "ID-1"),
        ("", "Laboratorio", "Lab"),
        ("", "Formulario", "10"),
        ("", "Job", "TM26-0001"),
        ("", "Producto", "Producto"),
        ("Tipo", "Ácido Graso", "% Area"),
        ("totales", "Total ácidos grasos", "96.7"),
    ]

    results, _ = parse_pag_results(rows, "TM26-0001")

    assert results[0].original_values["category"] == "Totales"
    assert results[0].analysis_name == "Perfil de Ácidos Grasos"


def test_warns_for_unknown_sample() -> None:
    rows = [
        ("", "ID Muestra", "ID-ANON-1"),
        ("", "Laboratorio", "Lab"),
        ("", "Formulario", "10"),
        ("", "Job", "TM26-0001"),
        ("", "Producto", "Producto"),
        ("Tipo", "Ácido Graso", "% Area"),
        ("Sat", "C4:0", "ND"),
    ]

    results, warnings = parse_pag_results(rows, "TM26-NO-EXISTE")

    assert results == []
    assert any("No se encontraron resultados PAG" in warning for warning in warnings)