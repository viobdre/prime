"""Locations for app files and the local model store (no Qt, no torch imports)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def models_dir() -> Path:
    return app_dir() / "models"


def checkpoints_dir() -> Path:
    return models_dir() / "hub" / "checkpoints"  # where torch.hub keeps weights


def manifest_path() -> Path:
    return models_dir() / "manifest.json"


def configure_env() -> None:
    """Point torch/demucs at the app-local model folder (offline-friendly)."""
    try:
        models_dir().mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    os.environ["TORCH_HOME"] = str(models_dir())


def read_manifest() -> dict:
    try:
        return json.loads(manifest_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def mark_installed(name: str) -> None:
    data = read_manifest()
    data[name] = {"verified": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        manifest_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def is_installed(name: str) -> bool:
    return name in read_manifest()
