from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from statistics import mean
from urllib.parse import urlencode

import httpx
from shapely.geometry import LineString, Point, Polygon

from app.schemas.route_analysis import (
    OfficialRoadReference,
    RouteAnalysisRequest,
    RouteAnalysisResponse,
    RouteCandidate,
    RouteLocation,
    RouteObstacleSummary,
    TerrainSummary,
)


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
OPEN_TOPO_URL = "https://api.opentopodata.org/v1/srtm30m"
# kumi.systems was replaced by private.coffee.  Prefer the current public mirror,
# then another global mirror, and use the main instance as final fallback.
OVERPASS_ENDPOINTS = (
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
USER_AGENT = "LandGuard-SIH2026/route-feasibility"


@dataclass
class RawRoute:
    coordinates: list[list[float]]  # [lon, lat]
    distance_km: float
    duration_min: float | None
    source_label: str
    candidate_key: str
    candidate_kind: str


class RouteAnalysisError(RuntimeError):
    pass


def _haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    r = 6371.0088
    p1, p2 = radians(a_lat), radians(b_lat)
    dphi = radians(b_lat - a_lat)
    dlambda = radians(b_lon - a_lon)
    h = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * r * asin(sqrt(h))


def _polyline_distance_km(coords: list[list[float]]) -> float:
    return sum(
        _haversine_km(a[1], a[0], b[1], b[0])
        for a, b in zip(coords, coords[1:])
    )


def _norm_place(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


_SETTLEMENT_RANK = {
    "city": 90,
    "town": 85,
    "municipality": 82,
    "village": 75,
    "suburb": 65,
    "quarter": 60,
    "neighbourhood": 58,
    "hamlet": 55,
    "locality": 45,
}
_ADMIN_TYPES = {"administrative", "state", "state_district", "district", "county", "region"}


def _query_name(value: str) -> str:
    """Return the user-supplied place name without broad geographic qualifiers."""
    return _norm_place(str(value or "").split(",", 1)[0])


def _row_name_candidates(row: dict) -> set[str]:
    address = row.get("address") or {}
    namedetails = row.get("namedetails") or {}
    values = [
        row.get("name"),
        namedetails.get("name"),
        address.get("city"),
        address.get("town"),
        address.get("municipality"),
        address.get("village"),
        address.get("suburb"),
        address.get("hamlet"),
        address.get("locality"),
    ]
    return {_norm_place(value) for value in values if _norm_place(value)}


def _geocode_score(row: dict, *, query: str, state: str | None, district: str | None, attempt_index: int = 0) -> tuple[float, ...]:
    """Rank Nominatim rows toward the named settlement rather than an admin-area centroid.

    This matters for inputs such as ``Rayagada`` where Nominatim may return both
    Rayagada town and Rayagada district.  Route endpoints should resolve to the
    requested town/village/landmark, not silently to the centre of the district.
    """
    query_n = _query_name(query)
    state_n = _norm_place(state)
    district_n = _norm_place(district)
    display = _norm_place(row.get("display_name"))
    address = row.get("address") or {}
    address_text = _norm_place(" ".join(str(v) for v in address.values()))
    haystack = f"{display} {address_text}"
    names = _row_name_candidates(row)

    row_type = _norm_place(row.get("type"))
    address_type = _norm_place(row.get("addresstype"))
    row_class = _norm_place(row.get("class"))
    effective_type = address_type or row_type

    # Scope is the strongest signal for district/state officers.  A candidate
    # outside the officer's district must not beat an in-scope same-name place.
    district_match = 1 if district_n and district_n in haystack else 0
    state_match = 1 if state_n and state_n in haystack else 0
    scope_score = district_match * 220 + state_match * 100

    exact_name = 1 if query_n and query_n in names else 0
    display_starts = 1 if query_n and (display == query_n or display.startswith(query_n + ",")) else 0

    settlement_rank = max(
        _SETTLEMENT_RANK.get(row_type, 0),
        _SETTLEMENT_RANK.get(address_type, 0),
    )
    if row_class == "place" and settlement_rank:
        settlement_rank += 12

    # Explicitly demote administrative boundaries when the user asked for a
    # simple place name.  This fixes cases such as Rayagada town vs Rayagada
    # district and avoids routing to a district centroid.
    admin_penalty = 0
    if effective_type in _ADMIN_TYPES or (row_class == "boundary" and row_type == "administrative"):
        admin_penalty = -95

    # Context-rich attempts are preferred, but only as a small tiebreaker.
    attempt_bonus = max(0, 12 - attempt_index * 3)
    importance = float(row.get("importance") or 0.0)

    return (
        float(scope_score),
        float(exact_name * 160 + display_starts * 45),
        float(settlement_rank + admin_penalty),
        float(attempt_bonus),
        importance,
    )


def _geocode_attempts(query: str, *, state: str | None = None, district: str | None = None) -> list[str]:
    query = query.strip()
    attempts: list[str] = []
    if district and state:
        # Keep the explicit ``district`` token even when query == district.
        # "Rayagada, Rayagada district, Odisha" is less ambiguous than merely
        # "Rayagada, Odisha", which can resolve to an administrative boundary.
        attempts.append(f"{query}, {district} district, {state}, India")
        attempts.append(f"{query}, {district}, {state}, India")
    elif state:
        attempts.append(f"{query}, {state}, India")
    attempts.append(query)
    return list(dict.fromkeys(attempts))


def _choose_geocode_row(rows: list[tuple[dict, int]], *, query: str, state: str | None, district: str | None) -> dict | None:
    if not rows:
        return None

    state_n = _norm_place(state)
    district_n = _norm_place(district)

    # De-duplicate the same OSM object returned by multiple search attempts.
    unique: dict[tuple, tuple[dict, int]] = {}
    for row, attempt_index in rows:
        key = (
            row.get("osm_type"), row.get("osm_id"),
            str(row.get("lat")), str(row.get("lon")),
        )
        previous = unique.get(key)
        if previous is None or attempt_index < previous[1]:
            unique[key] = (row, attempt_index)

    candidates = list(unique.values())

    def in_scope(item: tuple[dict, int]) -> bool:
        row, _ = item
        display = _norm_place(row.get("display_name"))
        address = row.get("address") or {}
        address_text = _norm_place(" ".join(str(v) for v in address.values()))
        haystack = f"{display} {address_text}"
        if state_n and state_n not in haystack:
            return False
        if district_n and district_n not in haystack:
            return False
        return True

    scoped = [item for item in candidates if in_scope(item)]
    if state_n or district_n:
        # Never silently fall back to an out-of-scope same-name place.  A wrong
        # endpoint is more dangerous than asking the officer for a fuller name.
        if not scoped:
            return None
        candidates = scoped

    row, attempt_index = max(
        candidates,
        key=lambda item: _geocode_score(
            item[0], query=query, state=state, district=district, attempt_index=item[1]
        ),
    )
    return row


def _geocode(query: str, *, state: str | None = None, district: str | None = None) -> RouteLocation:
    query = query.strip()
    attempts = _geocode_attempts(query, state=state, district=district)
    collected: list[tuple[dict, int]] = []
    last_error: Exception | None = None

    for attempt_index, search_text in enumerate(attempts):
        params = {
            "q": search_text,
            "format": "jsonv2",
            "limit": 12,
            "countrycodes": "in",
            "addressdetails": 1,
            "namedetails": 1,
        }
        try:
            with httpx.Client(timeout=7.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(NOMINATIM_URL, params=params)
                response.raise_for_status()
                rows = list(response.json() or [])
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            continue
        collected.extend((row, attempt_index) for row in rows)

    row = _choose_geocode_row(collected, query=query, state=state, district=district)
    if row is not None:
        return RouteLocation(
            label=str(row.get("display_name") or query),
            latitude=float(row["lat"]),
            longitude=float(row["lon"]),
        )

    if last_error is not None and not collected:
        raise RouteAnalysisError(f"Place search is unavailable: {last_error}") from last_error
    scope = ", ".join(part for part in (district, state) if part)
    suffix = f" inside {scope}" if scope else " in India"
    raise RouteAnalysisError(f"Could not locate '{query}'{suffix}. Use a village/town, landmark or a more complete address.")


def _canonical_pair(origin: RouteLocation, destination: RouteLocation) -> tuple[RouteLocation, RouteLocation, bool]:
    """Return a stable endpoint order so A→B and B→A generate the same physical candidates."""
    a = (round(origin.latitude, 6), round(origin.longitude, 6))
    b = (round(destination.latitude, 6), round(destination.longitude, 6))
    if a <= b:
        return origin, destination, False
    return destination, origin, True


def _reverse_if_needed(route: RawRoute, reverse: bool) -> RawRoute:
    if not reverse:
        return route
    return RawRoute(
        coordinates=list(reversed(route.coordinates)),
        distance_km=route.distance_km,
        duration_min=route.duration_min,
        source_label=route.source_label,
        candidate_key=route.candidate_key,
        candidate_kind=route.candidate_kind,
    )


def _osrm_request(
    points: list[tuple[float, float]],
    alternatives: bool = False,
    *,
    source_label: str = "OSRM mapped road-network route",
    candidate_key_prefix: str = "NETWORK",
) -> list[RawRoute]:
    coords = ";".join(f"{lon:.7f},{lat:.7f}" for lat, lon in points)
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": "3" if alternatives else "false",
    }
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(f"{OSRM_URL}/{coords}", params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RouteAnalysisError(f"Road-network routing provider is unavailable: {exc}") from exc
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RouteAnalysisError("No drivable network route was returned between those points.")
    result: list[RawRoute] = []
    for index, row in enumerate(payload["routes"][:3], start=1):
        geometry = row.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        result.append(RawRoute(
            coordinates=[[float(lon), float(lat)] for lon, lat in coordinates],
            distance_km=float(row.get("distance") or 0) / 1000.0,
            duration_min=float(row.get("duration") or 0) / 60.0,
            source_label=source_label,
            candidate_key=f"{candidate_key_prefix}_{index}",
            candidate_kind="EXISTING_NETWORK",
        ))
    return result


def _offset_midpoint(origin: RouteLocation, destination: RouteLocation, sign: int) -> tuple[float, float]:
    mean_lat = (origin.latitude + destination.latitude) / 2
    metres_per_lat = 111_320.0
    metres_per_lon = 111_320.0 * max(cos(radians(mean_lat)), 0.2)
    dx = (destination.longitude - origin.longitude) * metres_per_lon
    dy = (destination.latitude - origin.latitude) * metres_per_lat
    length = max(sqrt(dx * dx + dy * dy), 1.0)
    offset = min(max(length * 0.10, 600.0), 3500.0) * sign
    px, py = -dy / length, dx / length
    mid_x = dx / 2 + px * offset
    mid_y = dy / 2 + py * offset
    return origin.latitude + mid_y / metres_per_lat, origin.longitude + mid_x / metres_per_lon


def _dedupe_routes(routes: list[RawRoute]) -> list[RawRoute]:
    kept: list[RawRoute] = []
    for route in routes:
        if any(abs(route.distance_km - other.distance_km) < 0.08 and abs((route.duration_min or 0) - (other.duration_min or 0)) < 0.8 for other in kept):
            continue
        kept.append(route)
        if len(kept) >= 3:
            break
    return kept


def _build_network_candidates(origin: RouteLocation, destination: RouteLocation) -> list[RawRoute]:
    canonical_origin, canonical_destination, reverse = _canonical_pair(origin, destination)
    routes = _osrm_request(
        [(canonical_origin.latitude, canonical_origin.longitude), (canonical_destination.latitude, canonical_destination.longitude)],
        alternatives=True,
        source_label="Existing mapped drivable-road candidate",
        candidate_key_prefix="NETWORK",
    )
    routes = _dedupe_routes(routes)
    if len(routes) < 3:
        for sign in (1, -1):
            if len(routes) >= 3:
                break
            via = _offset_midpoint(canonical_origin, canonical_destination, sign)
            try:
                rows = _osrm_request(
                    [
                        (canonical_origin.latitude, canonical_origin.longitude),
                        via,
                        (canonical_destination.latitude, canonical_destination.longitude),
                    ],
                    source_label="Existing mapped road candidate via alternate network corridor",
                    candidate_key_prefix=f"NETWORK_VIA_{'L' if sign > 0 else 'R'}",
                )
            except RouteAnalysisError:
                continue
            routes = _dedupe_routes(routes + rows)
    return [_reverse_if_needed(route, reverse) for route in routes[:3]]


def _bezier_route(
    origin: RouteLocation,
    destination: RouteLocation,
    offset_fraction: float,
    *,
    construction_type: str,
    candidate_key: str,
) -> RawRoute:
    mean_lat = (origin.latitude + destination.latitude) / 2
    metres_per_lat = 111_320.0
    metres_per_lon = 111_320.0 * max(cos(radians(mean_lat)), 0.2)
    dx = (destination.longitude - origin.longitude) * metres_per_lon
    dy = (destination.latitude - origin.latitude) * metres_per_lat
    straight_m = max(sqrt(dx * dx + dy * dy), 1.0)
    px, py = -dy / straight_m, dx / straight_m
    # Offset is capped so district-scale candidates stay plausible rather than making huge arcs.
    cap_m = 9000.0 if construction_type in {"ROAD", "CANAL"} else 6500.0
    offset_m = max(-cap_m, min(cap_m, straight_m * offset_fraction))
    cx = dx / 2 + px * offset_m
    cy = dy / 2 + py * offset_m
    coordinates: list[list[float]] = []
    samples = 49
    for i in range(samples):
        t = i / (samples - 1)
        omt = 1 - t
        x = 2 * omt * t * cx + t * t * dx
        y = 2 * omt * t * cy + t * t * dy
        lat = origin.latitude + y / metres_per_lat
        lon = origin.longitude + x / metres_per_lon
        coordinates.append([lon, lat])
    label = {
        "ROAD": "Conceptual greenfield road/highway alignment",
        "RAILWAY": "Conceptual greenfield railway alignment",
        "CANAL": "Conceptual canal alignment",
        "PIPELINE": "Conceptual pipeline alignment",
    }.get(construction_type, "Conceptual greenfield infrastructure alignment")
    return RawRoute(
        coordinates=coordinates,
        distance_km=_polyline_distance_km(coordinates),
        duration_min=None,
        source_label=label,
        candidate_key=candidate_key,
        candidate_kind="GREENFIELD_CONCEPT",
    )


def _build_greenfield_candidates(origin: RouteLocation, destination: RouteLocation, construction_type: str) -> list[RawRoute]:
    canonical_origin, canonical_destination, reverse = _canonical_pair(origin, destination)
    offsets_by_type = {
        "ROAD": (-0.18, -0.09, 0.0, 0.09, 0.18),
        "RAILWAY": (-0.12, -0.06, 0.0, 0.06, 0.12),
        "CANAL": (-0.20, -0.10, 0.0, 0.10, 0.20),
        "PIPELINE": (-0.14, -0.07, 0.0, 0.07, 0.14),
        "OTHER": (-0.16, -0.08, 0.0, 0.08, 0.16),
    }
    offsets = offsets_by_type.get(construction_type, offsets_by_type["OTHER"])
    routes = [
        _bezier_route(
            canonical_origin,
            canonical_destination,
            offset,
            construction_type=construction_type,
            candidate_key=f"GREENFIELD_{index}",
        )
        for index, offset in enumerate(offsets, start=1)
    ]
    return [_reverse_if_needed(route, reverse) for route in routes]


def _sample_route(route: RawRoute, count: int) -> list[tuple[float, float]]:
    line = LineString(route.coordinates)
    if line.length <= 0:
        lon, lat = route.coordinates[0]
        return [(lat, lon)]
    points = []
    for i in range(count):
        p = line.interpolate(i / max(count - 1, 1), normalized=True)
        points.append((float(p.y), float(p.x)))
    return points


def _fetch_terrain(routes: list[RawRoute]) -> tuple[dict[str, TerrainSummary], str | None]:
    if not routes:
        return {}, "No candidates"
    per_route = max(12, min(24, 96 // max(len(routes), 1)))
    samples: list[tuple[str, float, float]] = []
    for route in routes:
        for lat, lon in _sample_route(route, per_route):
            samples.append((route.candidate_key, lat, lon))
    payload = {"locations": "|".join(f"{lat:.6f},{lon:.6f}" for _, lat, lon in samples), "interpolation": "bilinear"}
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            response = client.post(OPEN_TOPO_URL, data=payload)
            response.raise_for_status()
            rows = list((response.json() or {}).get("results") or [])
    except (httpx.HTTPError, ValueError) as exc:
        return {route.candidate_key: TerrainSummary() for route in routes}, str(exc)
    if len(rows) != len(samples):
        return {route.candidate_key: TerrainSummary() for route in routes}, "Elevation provider returned incomplete samples"

    grouped: dict[str, list[tuple[float, float, float]]] = {route.candidate_key: [] for route in routes}
    for (key, lat, lon), row in zip(samples, rows):
        elev = row.get("elevation")
        if elev is None:
            continue
        grouped[key].append((lat, lon, float(elev)))

    result: dict[str, TerrainSummary] = {}
    for route in routes:
        pts = grouped.get(route.candidate_key) or []
        if len(pts) < 2:
            result[route.candidate_key] = TerrainSummary()
            continue
        elevations = [p[2] for p in pts]
        grades = []
        for a, b in zip(pts, pts[1:]):
            horizontal_m = _haversine_km(a[0], a[1], b[0], b[1]) * 1000
            if horizontal_m < 1:
                continue
            grades.append(abs(b[2] - a[2]) / horizontal_m * 100)
        result[route.candidate_key] = TerrainSummary(
            available=True,
            source="OpenTopoData SRTM30m",
            sample_count=len(pts),
            min_elevation_m=round(min(elevations), 1),
            max_elevation_m=round(max(elevations), 1),
            elevation_range_m=round(max(elevations) - min(elevations), 1),
            mean_abs_grade_percent=round(mean(grades), 2) if grades else 0.0,
            max_grade_percent=round(max(grades), 2) if grades else 0.0,
        )
    return result, None


def _route_corridor_polygon(route: RawRoute, corridor_width_m: float) -> Polygon:
    mean_lat = sum(coord[1] for coord in route.coordinates) / len(route.coordinates)
    # Conservative degree conversion for a narrow district-scale screening corridor.
    half_width_deg = max(corridor_width_m / 2, 4.0) / (111_320.0 * max(cos(radians(mean_lat)), 0.35))
    poly = LineString(route.coordinates).buffer(half_width_deg, cap_style=2, join_style=2)
    return poly.simplify(max(half_width_deg * 0.15, 0.00001), preserve_topology=True)


def _poly_filter(poly: Polygon) -> str:
    exterior = list(poly.exterior.coords)
    # Keep Overpass polygon strings reasonably small while preserving route shape.
    step = max(1, len(exterior) // 70)
    points = exterior[::step]
    if points[-1] != exterior[-1]:
        points.append(exterior[-1])
    return " ".join(f"{lat:.7f} {lon:.7f}" for lon, lat in points)


def _overpass_query_polygon(poly: Polygon) -> str:
    p = _poly_filter(poly)
    filters = [
        'nwr["building"]',
        'nwr["shop"]',
        'nwr["amenity"]',
        'nwr["office"]',
        'nwr["government"]',
        'nwr["healthcare"]',
        'nwr["natural"="water"]',
        'nwr["waterway"]',
        'nwr["railway"]',
        'nwr["power"~"^(line|minor_line)$"]',
        'nwr["boundary"="protected_area"]',
        'nwr["leisure"="nature_reserve"]',
        'nwr["landuse"~"^(forest|farmland|farmyard|meadow|orchard|residential|commercial|industrial)$"]',
        'nwr["natural"="wood"]',
        'nwr["bridge"]',
        'nwr["place"~"^(village|hamlet|town|suburb|neighbourhood)$"]',
    ]
    body = "".join(f'{flt}(poly:"{p}");' for flt in filters)
    return f"[out:json][timeout:12];({body});out center tags geom;"


def _overpass_fetch_polygon(poly: Polygon) -> tuple[list[dict], str | None]:
    query = _overpass_query_polygon(poly)
    last_error: str | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            with httpx.Client(timeout=8.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
                response = client.post(endpoint, data={"data": query})
                response.raise_for_status()
                return list((response.json() or {}).get("elements") or []), None
        except (httpx.HTTPError, ValueError) as exc:
            last_error = f"{endpoint.split('/')[2]}: {exc}"
    return [], last_error or "OpenStreetMap/Overpass unavailable"


def _osm_geometry(element: dict):
    geometry = element.get("geometry") or []
    if geometry:
        coords = [(float(p["lon"]), float(p["lat"])) for p in geometry if "lon" in p and "lat" in p]
        if len(coords) >= 4 and coords[0] == coords[-1]:
            try:
                return Polygon(coords)
            except Exception:
                pass
        if len(coords) >= 2:
            return LineString(coords)
    if element.get("type") == "node" and element.get("lat") is not None:
        return Point(float(element["lon"]), float(element["lat"]))
    center = element.get("center") or {}
    if center.get("lat") is not None and center.get("lon") is not None:
        return Point(float(center["lon"]), float(center["lat"]))
    return None


def _is_water(tags: dict) -> bool:
    return tags.get("natural") == "water" or bool(tags.get("waterway"))


def _candidate_obstacles(route: RawRoute, corridor_width_m: float, osm_rows: list[dict]) -> RouteObstacleSummary:
    corridor = _route_corridor_polygon(route, corridor_width_m)
    mean_lat = sum(coord[1] for coord in route.coordinates) / len(route.coordinates)
    line = LineString(route.coordinates)
    crossing_line = line.buffer(12.0 / (111_320.0 * max(cos(radians(mean_lat)), 0.35)))

    mapped_buildings = residential = commercial = government_public = institutional = 0
    shops = schools = healthcare = religious = named_places = 0
    water_crossings = railway_crossings = powerline_crossings = 0
    forest_protected_hits = settlements = existing_bridge_segments = 0
    farmland_hits = residential_landuse_hits = industrial_commercial_landuse_hits = 0

    seen: set[tuple[str, int]] = set()
    for element in osm_rows:
        key = (str(element.get("type") or ""), int(element.get("id") or 0))
        if key in seen:
            continue
        seen.add(key)
        geom = _osm_geometry(element)
        if geom is None:
            continue
        tags = element.get("tags") or {}
        if not geom.intersects(corridor) and not geom.intersects(crossing_line):
            continue

        natural = str(tags.get("natural") or "").lower()
        landuse = str(tags.get("landuse") or "").lower()
        boundary = str(tags.get("boundary") or "").lower()
        leisure = str(tags.get("leisure") or "").lower()
        railway = str(tags.get("railway") or "").lower()
        power = str(tags.get("power") or "").lower()
        place = str(tags.get("place") or "").lower()

        if _is_water(tags) and geom.intersects(crossing_line):
            water_crossings += 1
        if railway in {"rail", "level_crossing", "tram", "narrow_gauge"} and geom.intersects(crossing_line):
            railway_crossings += 1
        if power in {"line", "minor_line"} and geom.intersects(crossing_line):
            powerline_crossings += 1
        if boundary == "protected_area" or leisure == "nature_reserve" or landuse == "forest" or natural == "wood":
            if geom.intersects(corridor):
                forest_protected_hits += 1
        if tags.get("bridge") and geom.intersects(crossing_line):
            existing_bridge_segments += 1
        if place in {"village", "hamlet", "town", "suburb", "neighbourhood"} and geom.intersects(corridor):
            settlements += 1
        if landuse in {"farmland", "farmyard", "meadow", "orchard"} and geom.intersects(corridor):
            farmland_hits += 1
        if landuse == "residential" and geom.intersects(corridor):
            residential_landuse_hits += 1
        if landuse in {"commercial", "industrial"} and geom.intersects(corridor):
            industrial_commercial_landuse_hits += 1

        if not geom.intersects(corridor):
            continue
        if tags.get("name"):
            named_places += 1
        building = str(tags.get("building") or "").lower()
        amenity = str(tags.get("amenity") or "").lower()
        shop = str(tags.get("shop") or "").lower()
        office = str(tags.get("office") or "").lower()
        if building and building != "no":
            mapped_buildings += 1
            if building in {"house", "residential", "apartments", "detached", "bungalow", "terrace", "hut"}:
                residential += 1
            if building in {"commercial", "retail", "office", "industrial", "warehouse", "hotel"}:
                commercial += 1
            if building in {"government", "public", "civic"}:
                government_public += 1
            if building in {"school", "college", "hospital", "university"}:
                institutional += 1
        if shop:
            shops += 1
        if amenity in {"school", "college", "university", "kindergarten"}:
            schools += 1
        if amenity in {"hospital", "clinic", "doctors", "pharmacy"} or tags.get("healthcare"):
            healthcare += 1
        if amenity == "place_of_worship" or building in {"temple", "mosque", "church", "religious"}:
            religious += 1
        if office == "government" or tags.get("government") or amenity in {"townhall", "courthouse", "police", "fire_station", "post_office", "library"}:
            government_public += 1
        if amenity in {"school", "college", "university", "hospital", "clinic"}:
            institutional += 1

    points = (
        mapped_buildings * 1.3
        + residential * 0.9
        + commercial * 1.3
        + government_public * 3.0
        + institutional * 4.2
        + shops * 1.1
        + schools * 6.0
        + healthcare * 7.0
        + religious * 4.0
        + water_crossings * 7.5
        + railway_crossings * 6.0
        + powerline_crossings * 3.5
        + forest_protected_hits * 8.5
        + settlements * 2.5
        + farmland_hits * 0.4
        + residential_landuse_hits * 2.0
        + industrial_commercial_landuse_hits * 1.0
    )
    return RouteObstacleSummary(
        mapped_buildings=mapped_buildings,
        residential=residential,
        commercial=commercial,
        government_public=government_public,
        institutional=institutional,
        shops_businesses=shops,
        schools=schools,
        healthcare=healthcare,
        religious=religious,
        water_crossings=water_crossings,
        railway_crossings=railway_crossings,
        powerline_crossings=powerline_crossings,
        forest_protected_hits=forest_protected_hits,
        settlements=settlements,
        existing_bridge_segments=existing_bridge_segments,
        named_places=named_places,
        farmland_hits=farmland_hits,
        residential_landuse_hits=residential_landuse_hits,
        industrial_commercial_landuse_hits=industrial_commercial_landuse_hits,
        screening_obstacle_points=round(points, 1),
    )


def _terrain_penalty(summary: TerrainSummary, construction_type: str) -> float:
    if not summary.available:
        return 0.0
    mean_grade = summary.mean_abs_grade_percent or 0.0
    max_grade = summary.max_grade_percent or 0.0
    elev_range = summary.elevation_range_m or 0.0
    if construction_type == "RAILWAY":
        return min(100.0, mean_grade * 18 + max_grade * 8 + elev_range / 3.5)
    if construction_type == "CANAL":
        return min(100.0, mean_grade * 12 + max_grade * 5 + elev_range / 5.0)
    if construction_type == "PIPELINE":
        return min(100.0, mean_grade * 5 + max_grade * 2.5 + elev_range / 10.0)
    return min(100.0, mean_grade * 7 + max_grade * 3.5 + elev_range / 7.0)


def _select_greenfield_for_live_screen(routes: list[RawRoute], terrains: dict[str, TerrainSummary], construction_type: str) -> list[RawRoute]:
    min_len = min(route.distance_km for route in routes)
    scored = []
    for route in routes:
        length_penalty = max(0.0, (route.distance_km / min_len - 1) * 100)
        terrain = terrains.get(route.candidate_key, TerrainSummary())
        score = length_penalty * 0.35 + _terrain_penalty(terrain, construction_type) * 0.65
        scored.append((score, route.candidate_key, route))
    scored.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored[:3]]


def _google_url(origin: RouteLocation, destination: RouteLocation, route: RawRoute) -> str:
    # For greenfield candidates Google Maps is deliberately used only as endpoint context;
    # asking Directions to follow waypoints would snap the concept alignment back to roads.
    params = {
        "api": "1",
        "origin": f"{origin.latitude:.6f},{origin.longitude:.6f}",
        "destination": f"{destination.latitude:.6f},{destination.longitude:.6f}",
        "travelmode": "driving",
    }
    if route.candidate_kind == "EXISTING_NETWORK":
        points = route.coordinates
        waypoints = []
        if len(points) >= 8:
            for fraction in (0.33, 0.66):
                lon, lat = points[min(int((len(points) - 1) * fraction), len(points) - 1)]
                waypoints.append(f"{lat:.6f},{lon:.6f}")
        if waypoints:
            params["waypoints"] = "|".join(waypoints)
    return "https://www.google.com/maps/dir/?" + urlencode(params)


def _official_reference(origin: RouteLocation, destination: RouteLocation, route_distance_km: float) -> OfficialRoadReference | None:
    text = _norm_place(origin.label + " " + destination.label)
    if "gunupur" in text and "padmapur" in text and ("rayagada" in text or "odisha" in text):
        official_length = 22.869
        diff = abs(route_distance_km - official_length) / official_length * 100
        return OfficialRoadReference(
            road_name="Gunupur–Padmapur Road",
            category="MDR-61-A",
            official_length_km=official_length,
            authority="Works Department, Government of Odisha – Rayagada-II R&B",
            source_url="https://works.odisha.gov.in/en/design-planning-and-investigation-roads-wing/rayagada-circle/rayagada-ii-r-b",
            route_length_difference_percent=round(diff, 1),
            note="The official road list identifies Gunupur–Padmapur Road as MDR-61-A, chainage 0/0–22/869 km. It confirms an existing road corridor; it does not approve a new alignment or widening.",
        )
    return None


def _candidate_strengths(
    summary: RouteObstacleSummary,
    terrain: TerrainSummary,
    distance_km: float,
    min_distance: float,
    *,
    obstacle_data_available: bool,
    construction_type: str,
) -> list[str]:
    strengths: list[str] = []
    if distance_km <= min_distance * 1.05:
        strengths.append("Near-shortest screened centreline")
    if terrain.available:
        if construction_type == "RAILWAY" and (terrain.mean_abs_grade_percent or 99) <= 1.5:
            strengths.append("Low average sampled gradient for railway pre-screening")
        elif construction_type != "RAILWAY" and (terrain.mean_abs_grade_percent or 99) <= 4.0:
            strengths.append("Relatively gentle sampled terrain profile")
    if obstacle_data_available:
        if summary.schools + summary.healthcare + summary.religious == 0:
            strengths.append("No sensitive-site object is mapped inside the screening corridor")
        if summary.water_crossings == 0:
            strengths.append("No mapped water crossing detected")
        if summary.forest_protected_hits == 0:
            strengths.append("No mapped forest/protected-area object detected")
    if not strengths:
        strengths.append("Provides a distinct concept alignment for comparison")
    return strengths[:4]


def _candidate_concerns(
    summary: RouteObstacleSummary,
    terrain: TerrainSummary,
    *,
    obstacle_data_available: bool,
    construction_type: str,
) -> list[str]:
    concerns: list[str] = []
    if terrain.available:
        max_grade = terrain.max_grade_percent or 0
        if construction_type == "RAILWAY" and max_grade > 2.5:
            concerns.append(f"Sampled terrain reaches about {max_grade:.1f}% grade; railway earthwork/gradient design needs detailed survey")
        elif construction_type == "ROAD" and max_grade > 8:
            concerns.append(f"Sampled terrain reaches about {max_grade:.1f}% grade; detailed road-gradient design is required")
    if obstacle_data_available:
        if summary.mapped_buildings:
            concerns.append(f"{summary.mapped_buildings} OSM-mapped structures intersect the screening corridor")
        if summary.schools + summary.healthcare + summary.religious:
            concerns.append(f"{summary.schools + summary.healthcare + summary.religious} mapped sensitive facilities require avoidance/impact review")
        if summary.water_crossings:
            concerns.append(f"{summary.water_crossings} mapped water features/crossings need drainage/bridge review")
        if summary.forest_protected_hits:
            concerns.append(f"{summary.forest_protected_hits} mapped forest/protected features require environmental verification")
        if summary.settlements:
            concerns.append(f"{summary.settlements} mapped settlement features intersect the screening corridor")
    else:
        concerns.append("Live OSM obstacle query was unavailable; field verification remains mandatory")
    if not concerns:
        concerns.append("No major mapped constraint was detected, but cadastral/field/engineering survey is still required")
    return concerns[:5]


def _coverage_percent(obstacle_ok: bool, terrain_ok: bool) -> float:
    # Coverage here means provider layers available for this screening run, not completeness of the real world.
    return float((55 if obstacle_ok else 0) + (45 if terrain_ok else 0))


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if abs(high - low) < 1e-9:
        return [0.0 for _ in values]
    return [(value - low) / (high - low) * 100 for value in values]


def _calibrated_screening_burden(
    relative_burden: float,
    obstacle: RouteObstacleSummary,
    terrain: TerrainSummary,
    *,
    obstacle_ok: bool,
    terrain_ok: bool,
    construction_type: str,
) -> float:
    """Return an evidence-adjusted 0-100 screening burden.

    The old score was purely min-max comparative, which allowed the best candidate
    to appear as 100/100 suitability even when important live layers were missing.
    This calibration keeps the useful relative ranking but also accounts for:
    - absolute sampled terrain difficulty,
    - absolute mapped-obstacle intensity when OSM data is available,
    - missing-provider uncertainty,
    - a small pre-feasibility uncertainty floor so a concept route is never shown
      as a perfect / certified alignment.
    """
    coverage = _coverage_percent(obstacle_ok, terrain_ok)
    evidence_gap = 100.0 - coverage
    terrain_absolute = _terrain_penalty(terrain, construction_type) if terrain_ok else 0.0
    # The comparative cost model treats about 300 obstacle points as a strong
    # impact load. Reuse that scale here and clamp it to 0-100.
    obstacle_absolute = min(100.0, obstacle.screening_obstacle_points / 3.0) if obstacle_ok else 0.0

    calibrated = (
        5.0  # pre-feasibility uncertainty floor; maximum screening score is 95
        + relative_burden * 0.45
        + terrain_absolute * 0.20
        + obstacle_absolute * 0.15
        + evidence_gap * 0.20
    )
    return round(max(0.0, min(100.0, calibrated)), 1)


def analyze_route(payload: RouteAnalysisRequest, *, state: str | None = None, district: str | None = None) -> RouteAnalysisResponse:
    origin = _geocode(payload.origin, state=state, district=district)
    destination = _geocode(payload.destination, state=state, district=district)
    straight_km = _haversine_km(origin.latitude, origin.longitude, destination.latitude, destination.longitude)
    if straight_km < 0.15:
        raise RouteAnalysisError("Origin and destination are too close for a route comparison.")

    if payload.alignment_mode == "EXISTING_NETWORK" and payload.construction_type != "ROAD":
        raise RouteAnalysisError("Existing-network mode currently applies to roads/highways. Choose New alignment for railway, canal, pipeline or other infrastructure.")

    if payload.alignment_mode == "EXISTING_NETWORK":
        all_routes = _build_network_candidates(origin, destination)
        if not all_routes:
            raise RouteAnalysisError("No mapped drivable road-network candidates could be generated between those points.")
        terrain_map, terrain_error = _fetch_terrain(all_routes)
        routes = all_routes[:3]
    else:
        all_routes = _build_greenfield_candidates(origin, destination, payload.construction_type)
        terrain_map, terrain_error = _fetch_terrain(all_routes)
        routes = _select_greenfield_for_live_screen(all_routes, terrain_map, payload.construction_type)

    # Real mapped obstacles are requested against each candidate's actual screening polygon.
    # Candidate calls run concurrently; each call itself falls back across current global Overpass mirrors.
    obstacle_rows: dict[str, list[dict]] = {}
    obstacle_errors: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=min(3, len(routes)), thread_name_prefix="landguard-route-osm") as executor:
        futures = {
            executor.submit(_overpass_fetch_polygon, _route_corridor_polygon(route, payload.corridor_width_m)): route
            for route in routes
        }
        for future in as_completed(futures):
            route = futures[future]
            try:
                rows, error = future.result()
            except Exception as exc:  # pragma: no cover - provider/runtime specific
                rows, error = [], str(exc)
            obstacle_rows[route.candidate_key] = rows
            obstacle_errors[route.candidate_key] = error

    obstacles: dict[str, RouteObstacleSummary] = {}
    obstacle_ok_map: dict[str, bool] = {}
    for route in routes:
        rows = obstacle_rows.get(route.candidate_key, [])
        # A successful query returning zero features is still real data coverage; error=None tells us that.
        obstacle_ok = obstacle_errors.get(route.candidate_key) is None
        obstacle_ok_map[route.candidate_key] = obstacle_ok
        obstacles[route.candidate_key] = _candidate_obstacles(route, payload.corridor_width_m, rows) if obstacle_ok else RouteObstacleSummary()

    length_values = [route.distance_km for route in routes]
    obstacle_values = [obstacles[route.candidate_key].screening_obstacle_points for route in routes]
    terrain_values = [_terrain_penalty(terrain_map.get(route.candidate_key, TerrainSummary()), payload.construction_type) for route in routes]
    length_norm = _normalize(length_values)
    obstacle_norm = _normalize(obstacle_values)
    terrain_norm = _normalize(terrain_values)

    if payload.construction_type == "RAILWAY":
        base_weights = (0.18, 0.34, 0.48)
    elif payload.construction_type == "CANAL":
        base_weights = (0.18, 0.37, 0.45)
    elif payload.construction_type == "PIPELINE":
        base_weights = (0.30, 0.40, 0.30)
    else:
        base_weights = (0.28, 0.44, 0.28)

    scored_rows = []
    min_distance = min(length_values)
    for index, route in enumerate(routes):
        terrain = terrain_map.get(route.candidate_key, TerrainSummary())
        obstacle = obstacles[route.candidate_key]
        obstacle_ok = obstacle_ok_map[route.candidate_key]
        terrain_ok = terrain.available

        w_len, w_obs, w_terrain = base_weights
        if not obstacle_ok:
            w_len += w_obs * 0.45
            w_terrain += w_obs * 0.55
            w_obs = 0
        if not terrain_ok:
            w_len += w_terrain * 0.45
            w_obs += w_terrain * 0.55
            w_terrain = 0
        total_w = max(w_len + w_obs + w_terrain, 1e-9)
        relative_burden = (length_norm[index] * w_len + obstacle_norm[index] * w_obs + terrain_norm[index] * w_terrain) / total_w
        relative_burden = round(max(0.0, min(100.0, relative_burden)), 1)
        burden = _calibrated_screening_burden(
            relative_burden,
            obstacle,
            terrain,
            obstacle_ok=obstacle_ok,
            terrain_ok=terrain_ok,
            construction_type=payload.construction_type,
        )
        feasibility = round(max(0.0, 100.0 - burden), 1)
        if burden <= 25:
            feasibility_label = "Lower screened constraint"
        elif burden <= 50:
            feasibility_label = "Moderate screened constraint"
        elif burden <= 75:
            feasibility_label = "High screened constraint"
        else:
            feasibility_label = "Very high screened constraint"

        # Comparative cost combines length and only the real layers that were available.
        impact_factor = 1.0
        if obstacle_ok:
            impact_factor += min(obstacle.screening_obstacle_points / 300.0, 0.30)
        if terrain_ok:
            impact_factor += min(_terrain_penalty(terrain, payload.construction_type) / 500.0, 0.20)
        proxy_cost = route.distance_km * impact_factor
        indicative = None
        note = None
        if payload.base_cost_crore_per_km is not None:
            indicative = round(route.distance_km * payload.base_cost_crore_per_km * impact_factor, 2)
            note = "Indicative screening estimate based on officer-entered base cost, centreline length, mapped constraints and sampled terrain; not a DPR/BOQ estimate."
        scored_rows.append((route, obstacle, terrain, obstacle_ok, terrain_ok, burden, feasibility, feasibility_label, proxy_cost, indicative, note))

    min_proxy = min(row[8] for row in scored_rows)
    # Deterministic recommendation.  Stable candidate keys make A→B and B→A choose the same physical alignment.
    scored_rows.sort(key=lambda row: (row[5], row[8], row[0].distance_km, row[0].candidate_key))
    top_rows = scored_rows[:3]

    candidates: list[RouteCandidate] = []
    for label_index, row in enumerate(top_rows, start=1):
        route, obstacle, terrain, obstacle_ok, terrain_ok, burden, feasibility, feasibility_label, proxy_cost, indicative, note = row
        status = "GOOD" if obstacle_ok and terrain_ok else "PARTIAL" if (obstacle_ok or terrain_ok) else "NETWORK_ONLY"
        coverage = _coverage_percent(obstacle_ok, terrain_ok)
        google_note = (
            "Google Maps shows the endpoints/area for visual reference; the greenfield concept line is LandGuard's screening geometry and is not a Google Directions route."
            if route.candidate_kind == "GREENFIELD_CONCEPT"
            else "Google Maps opens a road-network visual reference for this mapped existing-corridor candidate."
        )
        candidates.append(RouteCandidate(
            route_id=f"ROUTE_{chr(64 + label_index)}",
            label=f"Route {chr(64 + label_index)}",
            distance_km=round(route.distance_km, 2),
            duration_min=round(route.duration_min, 1) if route.duration_min is not None else None,
            geometry={"type": "LineString", "coordinates": route.coordinates},
            google_maps_url=_google_url(origin, destination, route),
            google_maps_note=google_note,
            route_basis=route.source_label,
            candidate_kind=route.candidate_kind,
            mapped_data_status=status,
            data_coverage_percent=coverage,
            screening_area_ha=round(route.distance_km * payload.corridor_width_m / 10.0, 2),
            obstacle_summary=obstacle,
            terrain_summary=terrain,
            comparative_cost_index=round(proxy_cost / min_proxy * 100 if min_proxy else 100, 1),
            route_burden_score=burden,
            feasibility_score=feasibility,
            feasibility_label=feasibility_label,
            indicative_cost_crore=indicative,
            indicative_cost_note=note,
            strengths=_candidate_strengths(
                obstacle,
                terrain,
                route.distance_km,
                min_distance,
                obstacle_data_available=obstacle_ok,
                construction_type=payload.construction_type,
            ),
            concerns=_candidate_concerns(
                obstacle,
                terrain,
                obstacle_data_available=obstacle_ok,
                construction_type=payload.construction_type,
            ),
        ))

    # Because top_rows are sorted by burden, Route A is always the recommended screened option.
    recommended = candidates[0]
    recommendation_title = f"{recommended.label} has the lowest multi-criteria screening burden"
    official_reference = _official_reference(origin, destination, recommended.distance_km)

    available_layers = []
    if recommended.terrain_summary.available:
        available_layers.append("SRTM30m terrain")
    if recommended.data_coverage_percent >= 55:
        available_layers.append("OpenStreetMap corridor constraints")
    confidence = "HIGH" if recommended.data_coverage_percent >= 95 else "MEDIUM" if recommended.data_coverage_percent >= 55 else "LIMITED"

    obs = recommended.obstacle_summary
    terrain = recommended.terrain_summary
    type_name = payload.construction_type.lower().replace("_", " ")
    mode_text = "new concept alignment" if payload.alignment_mode == "NEW_ALIGNMENT" else "existing mapped network corridor"
    obstacle_text = (
        f"The live OSM corridor query found {obs.mapped_buildings} mapped structures, {obs.schools + obs.healthcare + obs.religious} mapped sensitive facilities, "
        f"{obs.water_crossings} water crossings/features, {obs.powerline_crossings} power-line crossings and {obs.forest_protected_hits} forest/protected features."
        if recommended.data_coverage_percent >= 55
        else "The live OSM obstacle layer did not return successfully for this candidate, so LandGuard does not invent structure or obstacle counts."
    )
    terrain_text = (
        f"SRTM30m sampling returned an elevation range of about {terrain.elevation_range_m:.0f} m, mean absolute sampled grade {terrain.mean_abs_grade_percent:.1f}% and maximum sampled grade {terrain.max_grade_percent:.1f}%."
        if terrain.available else
        "Terrain elevation sampling was unavailable in this run."
    )
    cost_text = (
        f" Using the officer-entered base-rate assumption, its indicative comparative cost is about Rs {recommended.indicative_cost_crore:.2f} crore."
        if recommended.indicative_cost_crore is not None else
        f" Its comparative cost index is {recommended.comparative_cost_index:.1f}, with the lowest screened candidate normalized to about 100."
    )
    executive = (
        f"LandGuard recommends {recommended.label} for {type_name} pre-feasibility among the generated {mode_text} candidates because it has the lowest combined distance, mapped-constraint and terrain burden in this run. "
        f"The screened centreline is approximately {recommended.distance_km:.2f} km. {obstacle_text} {terrain_text}{cost_text} "
        "This is a planning-screening result; final alignment requires topographic, cadastral, geotechnical, environmental and competent-authority review."
    )

    key_findings = [
        f"Planning mode: {'new/greenfield concept alignment' if payload.alignment_mode == 'NEW_ALIGNMENT' else 'existing mapped road-network corridor'}; no 45 km route-length cap is applied.",
        f"The {payload.corridor_width_m:.0f} m value is screening/right-of-way width, not route distance. The selected concept footprint is about {recommended.screening_area_ha:.2f} ha (length × width only).",
        f"Direction consistency: LandGuard canonicalizes the endpoint pair before candidate generation, so reversing From/To evaluates the same physical candidate set and should retain the same preferred alignment.",
    ]
    if recommended.data_coverage_percent >= 55:
        key_findings.append(
            f"Mapped land-impact context: {obs.mapped_buildings} structures, {obs.shops_businesses} shops/businesses, {obs.settlements} settlement features, {obs.farmland_hits} farmland/related land-use features and {obs.forest_protected_hits} forest/protected features intersect the screening corridor."
        )
    if terrain.available:
        key_findings.append(
            f"Terrain context: {terrain.sample_count} SRTM30m samples, elevation range {terrain.elevation_range_m:.1f} m, mean absolute grade {terrain.mean_abs_grade_percent:.2f}% and max sampled grade {terrain.max_grade_percent:.2f}%."
        )
    if official_reference:
        key_findings.append(
            f"Official context: {official_reference.road_name} is listed by {official_reference.authority} as {official_reference.category}, {official_reference.official_length_km:.3f} km. This is evidence of an existing corridor, not approval of the screened new alignment."
        )

    provider_bits = []
    successful_obstacle = sum(1 for route in routes if obstacle_ok_map.get(route.candidate_key))
    provider_bits.append(f"OpenStreetMap corridor queries successful for {successful_obstacle}/{len(routes)} screened candidates")
    provider_bits.append("SRTM30m terrain available" if terrain_error is None else f"SRTM30m terrain issue: {terrain_error}")
    errors = sorted({err for err in obstacle_errors.values() if err})
    if errors:
        provider_bits.append("Obstacle fallback detail: " + errors[0][:180])
    provider_status = " · ".join(provider_bits)

    data_sources = [
        "OpenStreetMap / Overpass mapped buildings, amenities, land-use, water, rail, power and protected/forest features",
        "OpenTopoData SRTM30m elevation samples for terrain/gradient screening",
        "Nominatim place resolution constrained by the signed-in officer's district/state scope",
    ]
    if payload.alignment_mode == "EXISTING_NETWORK":
        data_sources.insert(0, "OSRM mapped drivable-road network routing")
    else:
        data_sources.insert(0, "LandGuard deterministic concept-alignment generator; candidates are not snapped to existing roads")

    acquisition_data_readiness = [
        "LIVE SCREENING: mapped structures/amenities/land-use/water/rail/power/protected features are queried from OpenStreetMap along each candidate corridor when the provider responds.",
        "LIVE TERRAIN: SRTM30m elevation is sampled along each candidate and included in road/rail/canal/pipeline-specific screening weights.",
        "LEGAL LAND OWNERSHIP: plot/khata/RoR, private/government title, compensation liability and market valuation are not inferred from maps; connect authoritative cadastral/land-record data for those fields.",
        "FINAL ENGINEERING: detailed contour survey, geotechnical investigation, drainage/bridge design, utilities, forest/environment clearance and DPR quantities remain mandatory before approval.",
    ]

    limitations = [
        "New-alignment candidates are deterministic pre-feasibility concept centrelines, not surveyed or sanctioned engineering alignments.",
        "OpenStreetMap object counts reflect what is mapped in the database, not a complete census of every real structure or utility on the ground.",
        "SRTM30m terrain is suitable for early screening but not a substitute for detailed topographic survey, railway vertical alignment or road geometric design.",
        "Google Maps is used only for endpoint/location reference; it is not the source of LandGuard's greenfield concept geometry or scoring.",
        "Legal acquisition decisions require authoritative cadastral/RoR data and competent-authority verification.",
        "The recommendation is a decision-support ranking among the screened candidates, not autonomous route approval.",
    ]

    overall_status = "GOOD" if recommended.data_coverage_percent >= 95 else "PARTIAL" if recommended.data_coverage_percent > 0 else "NETWORK_ONLY"
    return RouteAnalysisResponse(
        origin=origin,
        destination=destination,
        construction_type=payload.construction_type,
        alignment_mode=payload.alignment_mode,
        corridor_width_m=payload.corridor_width_m,
        base_cost_crore_per_km=payload.base_cost_crore_per_km,
        candidates=candidates,
        recommended_route_id=recommended.route_id,
        recommendation_title=recommendation_title,
        executive_summary=executive,
        key_findings=key_findings,
        data_sources=data_sources,
        provider_status=provider_status,
        mapped_data_status=overall_status,
        analysis_confidence=confidence,
        direction_consistency_note="Endpoint order is canonicalized before candidate generation and scoring; reversing From/To evaluates the same physical alignments in reverse geometry order.",
        official_road_reference=official_reference,
        acquisition_data_readiness=acquisition_data_readiness,
        limitations=limitations,
    )
