"""Benzara XML parsing entry points."""

from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import iterparse


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _find_text(element, path: tuple[str, ...]) -> str | None:
    current = element
    for segment in path:
        next_child = None
        for child in current:
            if _local_name(child.tag) == segment:
                next_child = child
                break
        if next_child is None:
            return None
        current = next_child
    return _normalize_text(current.text)


def _find_many_text(element, path: tuple[str, ...]) -> list[str]:
    current = element
    for segment in path[:-1]:
        next_child = None
        for child in current:
            if _local_name(child.tag) == segment:
                next_child = child
                break
        if next_child is None:
            return []
        current = next_child
    target_name = path[-1]
    values: list[str] = []
    for child in current:
        if _local_name(child.tag) == target_name:
            text = _normalize_text(child.text)
            if text is not None:
                values.append(text)
    return values


def _collect_attributes(element) -> dict[str, str]:
    result: dict[str, str] = {}
    attributes_node = None
    for child in element:
        if _local_name(child.tag) == 'attributes':
            attributes_node = child
            break
    if attributes_node is None:
        return result
    for attr in attributes_node:
        if _local_name(attr.tag) != 'attribute':
            continue
        name = _find_text(attr, ('name',))
        value = _find_text(attr, ('value',))
        if name and value is not None:
            result[name] = value
    return result


def _collect_meta(element) -> dict[str, str]:
    result: dict[str, str] = {}
    meta_node = None
    for child in element:
        if _local_name(child.tag) == 'meta':
            meta_node = child
            break
    if meta_node is None:
        return result
    for field in meta_node:
        if _local_name(field.tag) != 'field':
            continue
        key = _find_text(field, ('key',))
        value = _find_text(field, ('value',))
        if key and value is not None:
            result[key] = value
    return result


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _is_product_element(element) -> bool:
    return _local_name(element.tag) == 'product'


def inspect_benzara_input(path: str | Path) -> dict[str, str | int | None]:
    candidate = Path(path)
    result: dict[str, str | int | None] = {
        "path": str(candidate),
        "exists": str(candidate.exists()),
        "root_tag": None,
        "product_like_records": 0,
    }
    if not candidate.exists():
        return result

    count = 0
    root_tag: str | None = None
    for event, element in iterparse(candidate, events=("start", "end")):
        if root_tag is None and event == 'start':
            root_tag = _local_name(element.tag)
        if event == 'end' and _is_product_element(element):
            count += 1
            element.clear()
    result["root_tag"] = root_tag
    result["product_like_records"] = count
    return result


def parse_benzara_xml(path: str | Path) -> list[dict]:
    """Parse a Benzara XML feed into a normalized list of dictionaries."""
    candidate = Path(path)
    if not candidate.exists():
        return []

    products: list[dict] = []
    for _, element in iterparse(candidate, events=("end",)):
        if not _is_product_element(element):
            continue
        attributes = _collect_attributes(element)
        meta = _collect_meta(element)
        record = {
            "source_id": _find_text(element, ("id",)),
            "type": _find_text(element, ("type",)),
            "sku": _find_text(element, ("sku",)),
            "ean": _find_text(element, ("ean",)),
            "name": _find_text(element, ("name",)),
            "description": _find_text(element, ("description",)),
            "short_description": _find_text(element, ("short_description",)),
            "regular_price": _to_float(_find_text(element, ("pricing", "regular"))),
            "tax_status": _find_text(element, ("pricing", "tax_status")),
            "tax_class": _find_text(element, ("pricing", "tax_class")),
            "manage_stock": _find_text(element, ("stock", "manage")),
            "stock_qty": _to_int(_find_text(element, ("stock", "qty"))),
            "stock_status": _find_text(element, ("stock", "status")),
            "backorders": _find_text(element, ("stock", "backorders")),
            "weight_lb": _to_float(_find_text(element, ("shipping", "weight"))),
            "length_in": _to_float(_find_text(element, ("shipping", "length"))),
            "width_in": _to_float(_find_text(element, ("shipping", "width"))),
            "height_in": _to_float(_find_text(element, ("shipping", "height"))),
            "brand": meta.get("_brand"),
            "origin": meta.get("_origin"),
            "assembly_needed": meta.get("_assembly_needed"),
            "inventory_snapshot_match": meta.get("_inventory_snapshot_match"),
            "inventory_qty_raw": meta.get("_inventory_qty_raw"),
            "categories": _find_many_text(element, ("categories", "category")),
            "category_tree": _find_many_text(element, ("categories", "tree")),
            "images": _find_many_text(element, ("images", "image")),
            "attributes": attributes,
            "material": attributes.get("Material"),
            "color": attributes.get("Color"),
            "finish": attributes.get("Finish"),
            "meta": meta,
        }
        products.append(record)
        element.clear()
    return products
