from io import BytesIO

from PIL import Image

from src.preferences_service import load_preferences, replace_signature, restore_signature, save_preferences


def test_preferences_survive_reload(tmp_path) -> None:
    path = tmp_path / "config" / "user_preferences.json"
    values = {
        "catalog": {"analyses": {"PAG": {"method_description": "Método guardado"}}},
        "metadata_by_sample": {"TM26-1": {"contact": "Yanira Martinez"}},
        "metadata_defaults": {"sampling_date": "2026-07-21"},
        "execution_dates_defaults": {
            "perfil de ácidos grasos": {"start_date": "2026-07-20", "end_date": "2026-07-22"},
        },
    }

    save_preferences(path, values)

    assert load_preferences(path) == values


def test_missing_preferences_file_returns_empty_mapping(tmp_path) -> None:
    assert load_preferences(tmp_path / "missing.json") == {}


def test_signature_replacement_keeps_original_and_can_restore(tmp_path) -> None:
    signature = tmp_path / "assets" / "signature.jpeg"
    backup = tmp_path / "assets" / "signature.original.jpeg"
    signature.parent.mkdir()
    signature.write_bytes(b"old-signature")
    image_buffer = BytesIO()
    Image.new("RGBA", (4, 4), (255, 0, 0, 128)).save(image_buffer, format="PNG")

    replace_signature(image_buffer.getvalue(), signature, backup)
    first_replacement = signature.read_bytes()
    replace_signature(image_buffer.getvalue(), signature, backup)

    assert backup.read_bytes() == b"old-signature"
    assert signature.read_bytes() == first_replacement
    assert restore_signature(signature, backup) is True
    assert signature.read_bytes() == b"old-signature"


def test_restore_signature_returns_false_without_backup(tmp_path) -> None:
    assert restore_signature(tmp_path / "signature.jpeg", tmp_path / "missing.jpeg") is False