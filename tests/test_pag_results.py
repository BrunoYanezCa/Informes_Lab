from src.pag_results import (
    calculate_epa_dha,
    calculate_inverse_ratio,
    format_pag_analyte_name,
    format_pag_result,
)
from src.report_models import ResultRecord


def test_pag_result_is_formatted_with_two_decimal_places() -> None:
    assert format_pag_result("1.2") == "1.20"
    assert format_pag_result("1,2") == "1.20"
    assert format_pag_result("ND") == "ND"
    assert format_pag_result("<0,1") == "<0.10"


def test_epa_dha_sum_uses_percent_area_values_and_rounds_to_two_decimals() -> None:
    records = [
        ResultRecord("TM1", "PAG", "Perfil de Ácidos Grasos", "C20:5 n3 (EPA)", "0,13", "% Area"),
        ResultRecord("TM1", "PAG", "Perfil de Ácidos Grasos", "C22:6 n3 (DHA)", "0.21", "% Area"),
        ResultRecord("TM1", "PAG", "Perfil de Ácidos Grasos", "C20:5 n3 (EPA)", "9.99", "g/100g"),
    ]

    assert calculate_epa_dha(records) == "0.34"


def test_epa_dha_treats_nd_as_zero_and_preserves_less_than_indicator() -> None:
    records = [
        ResultRecord("TM1", "PAG", "Perfil de Ácidos Grasos", "EPA", "ND", "% Area"),
        ResultRecord("TM1", "PAG", "Perfil de Ácidos Grasos", "DHA", "<0.15", "% Area"),
    ]

    assert calculate_epa_dha(records) == "<0.15"


def test_epa_dha_is_blank_if_one_component_is_missing() -> None:
    records = [
        ResultRecord("TM1", "PAG", "Perfil de Ácidos Grasos", "EPA", "0.2", "% Area"),
    ]

    assert calculate_epa_dha(records) == ""


def test_pag_analyte_name_replaces_underscores() -> None:
    assert format_pag_analyte_name("Grasa cis_monoinsaturadas") == "Grasa cis monoinsaturadas"


def test_inverse_ratio_is_numeric_inverse_of_w6_w3() -> None:
    records = [
        ResultRecord("TM1", "PAG", "Perfil de Ácidos Grasos", "W6/W3", "10", "% Area"),
    ]

    assert calculate_inverse_ratio(records) == "0.10"