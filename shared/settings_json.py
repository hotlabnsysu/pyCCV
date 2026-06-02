"""Shared JSON settings helpers."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


def load_json_settings(path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load a JSON settings file and return a dict."""
    if not path.exists():
        return copy.deepcopy(default) if default is not None else {}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_json_settings(
    path: Path,
    data: Dict[str, Any],
    *,
    indent: int = 4,
    ensure_ascii: bool = False,
) -> None:
    """Save dict settings as JSON (UTF-8) using atomic write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, suffix=".tmp", prefix=path.stem,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

