from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
import shutil
from typing import Any

from PIL import Image


def load_preferences(path: str | Path) -> dict[str, Any]:
    preferences_path = Path(path)
    if not preferences_path.is_file():
        return {}
    with preferences_path.open("r", encoding="utf-8") as file:
        value = json.load(file)
    return value if isinstance(value, dict) else {}


def save_preferences(path: str | Path, preferences: dict[str, Any]) -> None:
    preferences_path = Path(path)
    preferences_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = preferences_path.with_suffix(f"{preferences_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(preferences, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(preferences_path)


def replace_signature(image_data: bytes, signature_path: str | Path, backup_path: str | Path) -> None:
    target = Path(signature_path)
    backup = Path(backup_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and not backup.exists():
        shutil.copy2(target, backup)
    temporary_path = target.with_name(f"{target.stem}.upload{target.suffix}")
    with Image.open(BytesIO(image_data)) as image:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        background.save(temporary_path, format="JPEG", quality=95)
    temporary_path.replace(target)


def restore_signature(signature_path: str | Path, backup_path: str | Path) -> bool:
    target = Path(signature_path)
    backup = Path(backup_path)
    if not backup.is_file():
        return False
    temporary_path = target.with_name(f"{target.stem}.restore{target.suffix}")
    shutil.copy2(backup, temporary_path)
    temporary_path.replace(target)
    return True