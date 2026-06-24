"""Matching layer for Benzara and WooCommerce products."""

from __future__ import annotations

from collections import defaultdict


MATCH_BUCKETS = (
    "MATCHED_BENZARA",
    "NEW_BENZARA",
    "ORPHAN_STORE",
    "OTHER_SUPPLIER",
    "CONFLICT",
)


def _normalize_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _build_index(records: list[dict], key: str) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        value = _normalize_identifier(record.get(key))
        if value is not None:
            index[value].append(record)
    return dict(index)


def _collect_match(benzara: dict, woo: dict, strategy: str) -> dict:
    return {
        "match_strategy": strategy,
        "benzara": benzara,
        "woo": woo,
        "sku": benzara.get("sku") or woo.get("sku"),
        "ean": benzara.get("ean") or woo.get("global_unique_id"),
    }


def match_products(benzara_products: list[dict], woo_products: list[dict]) -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = {bucket: [] for bucket in MATCH_BUCKETS}

    woo_by_sku = _build_index(woo_products, "sku")
    woo_by_ean = _build_index(woo_products, "global_unique_id")
    benzara_skus = {
        value for value in (_normalize_identifier(product.get("sku")) for product in benzara_products) if value is not None
    }

    matched_woo_ids: set[int] = set()
    conflict_woo_ids: set[int] = set()

    for benzara in benzara_products:
        sku = _normalize_identifier(benzara.get("sku"))
        ean = _normalize_identifier(benzara.get("ean"))

        if sku is not None and sku in woo_by_sku:
            candidates = woo_by_sku[sku]
            if len(candidates) == 1:
                woo = candidates[0]
                if woo.get("post_id") is not None:
                    matched_woo_ids.add(woo["post_id"])
                results["MATCHED_BENZARA"].append(_collect_match(benzara, woo, "sku"))
            else:
                for woo in candidates:
                    if woo.get("post_id") is not None:
                        conflict_woo_ids.add(woo["post_id"])
                results["CONFLICT"].append(
                    {
                        "type": "duplicate_woo_sku",
                        "sku": sku,
                        "benzara": benzara,
                        "woo_candidates": candidates,
                    }
                )
            continue

        if ean is not None and ean in woo_by_ean:
            candidates = woo_by_ean[ean]
            if len(candidates) == 1:
                woo = candidates[0]
                woo_sku = _normalize_identifier(woo.get("sku"))
                if woo_sku is None or woo_sku not in benzara_skus:
                    if woo.get("post_id") is not None:
                        matched_woo_ids.add(woo["post_id"])
                    results["MATCHED_BENZARA"].append(_collect_match(benzara, woo, "ean"))
                else:
                    if woo.get("post_id") is not None:
                        conflict_woo_ids.add(woo["post_id"])
                    results["CONFLICT"].append(
                        {
                            "type": "ean_matches_existing_sku_family",
                            "ean": ean,
                            "benzara": benzara,
                            "woo_candidates": candidates,
                        }
                    )
            else:
                for woo in candidates:
                    if woo.get("post_id") is not None:
                        conflict_woo_ids.add(woo["post_id"])
                results["CONFLICT"].append(
                    {
                        "type": "duplicate_woo_ean",
                        "ean": ean,
                        "benzara": benzara,
                        "woo_candidates": candidates,
                    }
                )
            continue

        results["NEW_BENZARA"].append(benzara)

    for woo in woo_products:
        post_id = woo.get("post_id")
        if post_id in matched_woo_ids or post_id in conflict_woo_ids:
            continue
        sku = _normalize_identifier(woo.get("sku"))
        if sku is None:
            results["OTHER_SUPPLIER"].append(woo)
            continue
        if sku in benzara_skus:
            results["CONFLICT"].append(
                {
                    "type": "unmatched_but_known_sku",
                    "sku": sku,
                    "woo": woo,
                }
            )
        else:
            results["ORPHAN_STORE"].append(woo)

    return results
