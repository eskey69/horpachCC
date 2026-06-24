"""WooCommerce WXR parsing entry points."""

from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import iterparse

CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
EXCERPT_NS = "http://wordpress.org/export/1.2/excerpt/"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str | None:
    if not tag.startswith("{"):
        return None
    return tag[1:].split("}", 1)[0]


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _item_child_text(element, name: str, namespace: str | None = None) -> str | None:
    for child in element:
        if _local_name(child.tag) != name:
            continue
        if namespace is not None and _namespace(child.tag) != namespace:
            continue
        return _normalize_text(child.text)
    return None


def _collect_taxonomies(element) -> tuple[list[str], list[str], str | None]:
    categories: list[str] = []
    tags: list[str] = []
    shipping_class: str | None = None
    for child in element:
        if _local_name(child.tag) != "category":
            continue
        domain = child.attrib.get("domain", "")
        value = _normalize_text(child.text)
        if value is None:
            continue
        if domain == "product_cat":
            categories.append(value)
        elif domain == "product_tag":
            tags.append(value)
        elif domain == 'product_shipping_class' and shipping_class is None:
            shipping_class = value
    return categories, tags, shipping_class


def _collect_meta(element) -> dict[str, str]:
    meta: dict[str, str] = {}
    for child in element:
        if _local_name(child.tag) != "postmeta":
            continue
        key = None
        value = None
        for meta_child in child:
            local = _local_name(meta_child.tag)
            if local == "meta_key":
                key = _normalize_text(meta_child.text)
            elif local == "meta_value":
                value = _normalize_text(meta_child.text) or ""
        if key:
            meta[key] = value or ""
    return meta


def inspect_woocommerce_input(path: str | Path) -> dict[str, str | int | None]:
    candidate = Path(path)
    result: dict[str, str | int | None] = {
        "path": str(candidate),
        "exists": str(candidate.exists()),
        "root_tag": None,
        "product_records": 0,
    }
    if not candidate.exists():
        return result

    root_tag: str | None = None
    count = 0
    for _, element in iterparse(candidate, events=("start", "end")):
        if root_tag is None:
            root_tag = _local_name(element.tag)
        if _local_name(element.tag) == "item" and _item_child_text(element, "post_type") == "product":
            count += 1
            element.clear()
    result["root_tag"] = root_tag
    result["product_records"] = count
    return result


def parse_woocommerce_wxr(path: str | Path) -> list[dict]:
    """Parse a WooCommerce WXR export into normalized product dictionaries."""
    candidate = Path(path)
    if not candidate.exists():
        return []

    products: list[dict] = []
    for _, element in iterparse(candidate, events=("end",)):
        if _local_name(element.tag) != "item":
            continue
        if _item_child_text(element, "post_type") != "product":
            element.clear()
            continue

        meta = _collect_meta(element)
        categories, tags, taxonomy_shipping_class = _collect_taxonomies(element)
        prefixed_meta = {k: v for k, v in meta.items() if k.startswith("_horpach_") or k.startswith("_fxc_")}
        record = {
            "post_id": _to_int(_item_child_text(element, "post_id")),
            "title": _item_child_text(element, "title"),
            "post_status": _item_child_text(element, "status"),
            "slug": _item_child_text(element, "post_name"),
            "url": _item_child_text(element, "link"),
            "content": _item_child_text(element, "encoded", CONTENT_NS),
            "excerpt": _item_child_text(element, "encoded", EXCERPT_NS),
            "categories": categories,
            "tags": tags,
            "sku": meta.get("_sku") or None,
            "regular_price": _to_float(meta.get("_regular_price")),
            "sale_price": _to_float(meta.get("_sale_price")),
            "price": _to_float(meta.get("_price")),
            "stock_qty": _to_int(meta.get("_stock")),
            "stock_status": meta.get("_stock_status") or None,
            "manage_stock": meta.get("_manage_stock") or None,
            "weight_lb": _to_float(meta.get("_weight")),
            "length_in": _to_float(meta.get("_length")),
            "width_in": _to_float(meta.get("_width")),
            "height_in": _to_float(meta.get("_height")),
            "global_unique_id": meta.get("_global_unique_id") or None,
            "thumbnail_id": meta.get("_thumbnail_id") or None,
            "product_image_gallery": meta.get("_product_image_gallery") or None,
            "shipping_class": meta.get("_shipping_class") or taxonomy_shipping_class,
            "total_sales": _to_int(meta.get("total_sales")),
            "prefixed_meta": prefixed_meta,
            "meta": meta,
        }
        products.append(record)
        element.clear()
    return products

