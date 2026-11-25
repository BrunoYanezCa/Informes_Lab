import json

from src.catalog_service import apply_catalog_limit_overrides, load_catalog, serialize_catalog_overrides
from src.report_models import ResultRecord


def test_catalog_overrides_persist_without_losing_defaults(tmp_path) -> None:
    defaults = tmp_path / "catalog.yaml"
    defaults.write_text(
        "analyses:\n  - code: PAG\n    display_name: Perfil Ácidos Grasos\n    aliases: [PAG]\n    method_code: ''\n    method_description: ''\n    analytes: []\n    allowed_units: ['% Area']\n    limits: {}\n",
        encoding="utf-8",
    )
    overrides = tmp_path / "config" / "catalog_overrides.json"

    serialized = serialize_catalog_overrides([{
        "code": "PAG",
        "display_name": "Perfil PAG",
        "aliases": ["PAG"],
        "method_code": "MET-1",
        "method_description": "Método confirmado",
        "analytes": ["C4:0"],
        "allowed_units": ["% Area", "g/100g"],
        "limits": {"C4:0|% Area": {"detection_limit": "0,1", "quantification_limit": "0,3"}},
    }])
    overrides.parent.mkdir(parents=True, exist_ok=True)
    overrides.write_text(serialized, encoding="utf-8")

    catalog = load_catalog(defaults, overrides)

    assert catalog[0]["method_code"] == "MET-1"
    assert catalog[0]["limits"]["C4:0|% Area"]["detection_limit"] == "0,1"
    assert json.loads(overrides.read_text(encoding="utf-8"))["analyses"]["PAG"]["method_code"] == "MET-1"


def test_catalog_overrides_persist_precedence(tmp_path) -> None:
    defaults = tmp_path / "catalog.yaml"
    defaults.write_text(
        "analyses:\n  - code: PAG\n    display_name: Perfil Ácidos Grasos\n    aliases: [PAG]\n    method_code: 'MET-OLD'\n    method_description: ''\n    analytes: []\n    allowed_units: ['% Area']\n    limits: {}\n",
        encoding="utf-8",
    )
    overrides = tmp_path / "config" / "catalog_overrides.json"

    serialized = serialize_catalog_overrides([{
        "code": "PAG",
        "display_name": "Perfil PAG",
        "aliases": ["PAG"],
        "method_code": "MET-1",
        "method_description": "Método confirmado",
        "analytes": ["C4:0"],
        "allowed_units": ["% Area", "g/100g"],
        "limits": {"C4:0|% Area": {"detection_limit": "0,1", "quantification_limit": "0,3"}},
    }])
    overrides.parent.mkdir(parents=True, exist_ok=True)
    overrides.write_text(serialized, encoding="utf-8")

    catalog = load_catalog(defaults, overrides)

    assert catalog[0]["method_code"] == "MET-1"
    assert catalog[0]["limits"]["C4:0|% Area"]["detection_limit"] == "0,1"
    assert json.loads(overrides.read_text(encoding="utf-8"))["analyses"]["PAG"]["method_code"] == "MET-1"

    # Simulate loading an older or empty draft by removing the overrides file
    overrides.unlink()

    # Reload catalog should now reflect the defaults (older/vacant draft scenario)
    catalog = load_catalog(defaults, overrides)

    assert catalog[0]["method_code"] == "MET-OLD"


def test_saved_catalog_limits_override_result_drafts() -> None:
    record = ResultRecord(
        "TM26-1", "PAG", "Perfil de Ácidos Grasos", "C4:0", "12.5", "% Area",
        detection_limit="9,9",
        quantification_limit="",
    )
    catalog = [{
        "code": "PAG",
        "aliases": ["PAG", "Perfil Ácidos Grasos", "Perfil de Ácidos Grasos"],
        "display_name": "Perfil de Ácidos Grasos",
        "limits": {
            "C4:0|% Area": {
                "detection_limit": "0,1",
                "quantification_limit": "0,3",
            }
        },
    }]

    updated = apply_catalog_limit_overrides([record], catalog)

    assert updated[0].detection_limit == "0,1"
    assert updated[0].quantification_limit == "0,3"
    assert record.detection_limit == "9,9"