"""Benzara XML parsing entry points."""

from __future__ import annotations

from pathlib import Path


def inspect_benzara_input(path: str | Path) -> dict[str, str]:
    candidate = Path(path)
    return {
        "path": str(candidate),
        "exists": str(candidate.exists()),
    }


def parse_benzara_xml(path: str | Path) -> list[dict]:
    """Placeholder parser for the Benzara XML feed."""
    _ = Path(path)
    return []

