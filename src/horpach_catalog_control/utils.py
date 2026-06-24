"""Shared helper functions."""

from __future__ import annotations

from pathlib import Path


def ensure_directory(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def summarize_file(path: str | Path) -> str:
    candidate = Path(path)
    if not candidate.exists():
        return f"missing: {candidate}"
    return f"exists: {candidate} ({candidate.stat().st_size} bytes)"

