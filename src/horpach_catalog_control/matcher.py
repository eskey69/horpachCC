"""Matching layer for Benzara and WooCommerce products."""

from __future__ import annotations


def match_products(benzara_products: list[dict], woo_products: list[dict]) -> dict[str, list[dict]]:
    return {
        "MATCHED_BENZARA": [],
        "NEW_BENZARA": list(benzara_products),
        "ORPHAN_STORE": [],
        "OTHER_SUPPLIER": [],
        "CONFLICT": [],
    }

