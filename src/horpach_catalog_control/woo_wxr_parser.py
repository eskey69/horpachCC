"""WooCommerce WXR parsing entry points."""

from __future__ import annotations

from pathlib import Path


def inspect_woocommerce_input(path: str | Path) -> dict[str, str]:
    candidate = Path(path)
    return {
        "path": str(candidate),
        "exists": str(candidate.exists()),
    }


def parse_woocommerce_wxr(path: str | Path) -> list[dict]:
    """Placeholder parser for the WooCommerce WXR export."""
    _ = Path(path)
    return []

