"""Real-world open map enrichment for LandGuard GIS.

This module supplements OpenStreetMap/Overpass with Overture Maps.  Overture's
buildings theme provides global building footprints compiled from open sources,
including Microsoft ML Buildings, Google Open Buildings, OSM, and others.  The
places theme supplies named businesses/facilities where available.

Imports are intentionally lazy so the API still starts if the optional spatial
packages have not been installed yet.  Production installs should include the
requirements added to backend/requirements.txt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


_RESIDENTIAL_CLASSES = {
    "apartments", "bungalow", "cabin", "detached", "dormitory", "dwelling_house",
    "house", "residential", "semi", "semidetached_house", "static_caravan",
    "stilt_house", "terrace", "hut",
}
_COMMERCIAL_CLASSES = {
    "commercial", "factory", "hotel", "industrial", "kiosk", "manufacture",
    "office", "retail", "service", "supermarket", "warehouse",
}
_INSTITUTIONAL_CLASSES = {
    "college", "hospital", "kindergarten", "school", "university",
}
_PUBLIC_CLASSES = {
    "civic", "fire_station", "library", "post_office", "public", "train_station",
}
_RELIGIOUS_CLASSES = {
    "cathedral", "chapel", "church", "monastery", "mosque", "religious",
    "shrine", "synagogue", "temple", "wayside_shrine",
}


@dataclass
class OvertureResult:
    features: list[dict[str, Any]]
    available: bool
    error: str | None = None


def _primary_name(names: Any) -> str | None:
    if isinstance(names, dict):
        value = names.get("primary")
        return str(value)[:180] if value else None
    return None


def _source_dataset(sources: Any) -> str | None:
    if not isinstance(sources, list):
        return None
    for item in sources:
        if not isinstance(item, dict):
            continue
        value = item.get("dataset") or item.get("provider")
        if value:
            return str(value)[:120]
    return None


def _building_use(row: dict[str, Any]) -> tuple[str, str]:
    klass = str(row.get("class") or "").lower()
    subtype = str(row.get("subtype") or "").lower()
    if klass == "government":
        return "GOVERNMENT", "Overture building class=government"
    if klass in _PUBLIC_CLASSES or subtype == "civic":
        return "PUBLIC_CIVIC", f"Overture building class/subtype={klass or subtype}"
    if klass in _INSTITUTIONAL_CLASSES or subtype in {"education", "medical"}:
        return "INSTITUTIONAL", f"Overture building class/subtype={klass or subtype}"
    if klass in _RELIGIOUS_CLASSES or subtype == "religious":
        return "RELIGIOUS", f"Overture building class/subtype={klass or subtype}"
    if klass in _COMMERCIAL_CLASSES or subtype in {"commercial", "industrial", "service"}:
        return "COMMERCIAL", f"Overture building class/subtype={klass or subtype}"
    if klass in _RESIDENTIAL_CLASSES or subtype == "residential":
        return "RESIDENTIAL", f"Overture building class/subtype={klass or subtype}"
    return "OTHER_UNKNOWN", "Overture building footprint has no explicit mapped-use class"


def _place_use(row: dict[str, Any]) -> tuple[str, str, str]:
    taxonomy = row.get("taxonomy") if isinstance(row.get("taxonomy"), dict) else {}
    primary = str((taxonomy or {}).get("primary") or row.get("basic_category") or "").lower()
    hierarchy = [str(v).lower() for v in ((taxonomy or {}).get("hierarchy") or [])]
    all_terms = set(hierarchy + ([primary] if primary else []))
    token = primary or (hierarchy[-1] if hierarchy else "place")

    if any("government" in value for value in all_terms) or token in {"city_hall", "courthouse"}:
        return "GOVERNMENT", f"Overture place category={token}", "PUBLIC_FACILITY"
    if any(value in all_terms for value in {"school", "college", "university", "kindergarten", "hospital", "clinic", "medical_center", "doctor"}):
        return "INSTITUTIONAL", f"Overture place category={token}", "PUBLIC_FACILITY"
    if any(value in all_terms for value in {"police", "fire_station", "library", "post_office", "community_center", "public_service", "transit_station"}):
        return "PUBLIC_CIVIC", f"Overture place category={token}", "PUBLIC_FACILITY"
    if any(value in all_terms for value in {"place_of_worship", "temple", "mosque", "church", "religious_organization"}):
        return "RELIGIOUS", f"Overture place category={token}", "AMENITY"
    if any(value in all_terms for value in {"shopping", "food_and_drink", "services_and_business", "lodging"}) or any(
        keyword in token for keyword in ("shop", "store", "market", "restaurant", "cafe", "hotel", "bank", "office", "pharmacy")
    ):
        return "COMMERCIAL", f"Overture place category={token}", "SHOP"
    return "OTHER_UNKNOWN", f"Overture place category={token}", "PLACE"


def _iter_rows(feature_type: str, bbox: tuple[float, float, float, float]) -> Iterable[dict[str, Any]]:
    """Stream Overture batches instead of calling ``read_all()``.

    ``read_all()`` waits for every matching remote parquet fragment before the
    caller can process even the first feature.  On slower networks that made
    the GIS endpoint look permanently stuck.  RecordBatchReader is iterable,
    so yielding one batch at a time lets the caller stop as soon as it has
    enough real features for the map.
    """
    from overturemaps import record_batch_reader  # type: ignore

    reader = record_batch_reader(feature_type, bbox=bbox)
    if reader is None:
        return
    for batch in reader:
        for row in batch.to_pylist():
            yield row


def _geometry_to_geojson(raw_geometry: Any):
    from shapely import from_wkb  # type: ignore
    from shapely.geometry import mapping  # type: ignore

    if raw_geometry is None:
        return None, None
    geom = from_wkb(bytes(raw_geometry))
    if geom.is_empty:
        return None, None
    return geom, mapping(geom)


def fetch_overture_features(
    bbox: tuple[float, float, float, float],
    *,
    polygon_points: list[tuple[float, float]] | None = None,
    include_places: bool = True,
    max_buildings: int = 1200,
    max_places: int = 250,
) -> OvertureResult:
    """Fetch real building footprints + named places from Overture for a small AOI.

    bbox order is (west, south, east, north).  polygon_points are (lat, lon).
    """
    try:
        from shapely.geometry import Point, Polygon  # type: ignore
    except Exception as exc:  # pragma: no cover - environment-specific
        return OvertureResult([], False, f"Spatial dependency unavailable: {exc}")

    clip_polygon = None
    if polygon_points:
        clip_polygon = Polygon([(lon, lat) for lat, lon in polygon_points])
        if not clip_polygon.is_valid:
            clip_polygon = clip_polygon.buffer(0)

    result: list[dict[str, Any]] = []
    building_geometries: list[tuple[Any, dict[str, Any]]] = []
    try:
        for index, row in enumerate(_iter_rows("building", bbox)):
            if index >= max_buildings * 3:
                break
            geom, geometry = _geometry_to_geojson(row.get("geometry"))
            if geom is None:
                continue
            if clip_polygon is not None and not geom.intersects(clip_polygon):
                continue
            use_class, basis = _building_use(row)
            centroid = geom.representative_point()
            dataset = _source_dataset(row.get("sources"))
            klass = row.get("class") or row.get("subtype")
            tags = {
                "overture_class": str(row.get("class") or ""),
                "overture_subtype": str(row.get("subtype") or ""),
                "source_dataset": str(dataset or ""),
            }
            if row.get("height") is not None:
                tags["height_m"] = str(row.get("height"))
            if row.get("num_floors") is not None:
                tags["num_floors"] = str(row.get("num_floors"))
            feature = {
                "feature_id": f"overture-building-{row.get('id') or index}",
                "category": "BUILDING",
                "subtype": str(klass) if klass else None,
                "name": _primary_name(row.get("names")),
                "latitude": float(centroid.y),
                "longitude": float(centroid.x),
                "geometry": geometry,
                "tags": tags,
                "use_class": use_class,
                "classification_basis": basis,
                "source_name": "Overture Maps",
            }
            result.append(feature)
            building_geometries.append((geom, feature))
            if len(building_geometries) >= max_buildings:
                break

        places: list[tuple[Any, dict[str, Any]]] = []
        if include_places:
            for index, row in enumerate(_iter_rows("place", bbox)):
                if index >= max_places * 4:
                    break
                geom, geometry = _geometry_to_geojson(row.get("geometry"))
                if geom is None:
                    continue
                point = geom if isinstance(geom, Point) else geom.representative_point()
                if clip_polygon is not None and not clip_polygon.intersects(point):
                    continue
                use_class, basis, category = _place_use(row)
                taxonomy = row.get("taxonomy") if isinstance(row.get("taxonomy"), dict) else {}
                subtype = str((taxonomy or {}).get("primary") or row.get("basic_category") or "place")
                tags = {
                    "overture_category": subtype,
                    "source_dataset": str(_source_dataset(row.get("sources")) or ""),
                }
                feature = {
                    "feature_id": f"overture-place-{row.get('id') or index}",
                    "category": category,
                    "subtype": subtype,
                    "name": _primary_name(row.get("names")),
                    "latitude": float(point.y),
                    "longitude": float(point.x),
                    "geometry": geometry,
                    "tags": tags,
                    "use_class": use_class,
                    "classification_basis": basis,
                    "source_name": "Overture Maps",
                }
                places.append((point, feature))
                if len(places) >= max_places:
                    break

            # Enrich unclassified building footprints using a place that is actually
            # located inside the footprint.  This is mapped-use enrichment, never an
            # ownership inference.
            for point, place_feature in places:
                for building_geom, building_feature in building_geometries:
                    if building_feature["use_class"] != "OTHER_UNKNOWN":
                        continue
                    if building_geom.contains(point) or building_geom.touches(point):
                        building_feature["use_class"] = place_feature["use_class"]
                        building_feature["classification_basis"] = (
                            f"Overture place inside footprint: {place_feature.get('subtype') or 'mapped place'}"
                        )
                        if not building_feature.get("name") and place_feature.get("name"):
                            building_feature["name"] = place_feature["name"]
                        break
            result.extend(feature for _point, feature in places)

        return OvertureResult(result, True, None)
    except Exception as exc:  # network/pyarrow/STAC failures must not crash GIS
        return OvertureResult([], False, str(exc))
