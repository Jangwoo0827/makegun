"""Persistent JSON storage that works on desktop (files) and in the browser (localStorage).

In the web build (pygbag / emscripten) the filesystem is wiped on page reload, so saves go to
the browser's localStorage instead, keyed by the file name.
"""
from __future__ import annotations

import json
import os
from typing import Any

import settings

_KEY_PREFIX = "gun_designer/"


def _local_storage() -> Any:
    import platform  # pygbag exposes the browser `window` here
    return platform.window.localStorage  # type: ignore[attr-defined]


def _key(path: str) -> str:
    return _KEY_PREFIX + os.path.basename(path)


def read_json(path: str) -> Any | None:
    """Parsed JSON, or None if missing/corrupt."""
    try:
        if settings.WEB:
            raw = _local_storage().getItem(_key(path))
            return None if raw is None else json.loads(str(raw))
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # missing file, bad JSON, storage unavailable
        return None


def write_json(path: str, data: Any) -> bool:
    try:
        text = json.dumps(data, indent=1)
        if settings.WEB:
            _local_storage().setItem(_key(path), text)
            return True
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)  # atomic: never leaves a half-written file
        return True
    except Exception:
        return False


def delete(path: str) -> None:
    try:
        if settings.WEB:
            _local_storage().removeItem(_key(path))
        elif os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
