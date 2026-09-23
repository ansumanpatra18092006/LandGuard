from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, wait
from math import asin, cos, radians, sin, sqrt
from threading import Lock
from time import monotonic, sleep
from typing import Annotated

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_roles
from app.core.access import OPERATIONAL_ROLES, assert_project_access, scope_projects
from app.models.project import Project
from app.models.land_parcel import LandParcel
from app.schemas.gis import (
    GeocodeResult, ImpactPolygonRequest, LandParcelFeature, MapProject,
    OwnershipBreakdown, OwnershipSummary, ParcelImportRequest, ParcelImportResult,
    PhysicalFeature, PhysicalImpactResponse, PhysicalImpactSummary,
)
from app.services.intelligence_service import risk_snapshot
from app.services.open_world_map_service import fetch_overture_features
from app.services.project_history_service import record_audit

router = APIRouter(tags=["GIS"])


_GEOCODE_LOCK = Lock()
_LAST_GEOCODE_AT = 0.0


@lru_cache(maxsize=256)
def _nominatim_search(query: str) -> tuple[tuple[str, float, float, str | None], ...]:
    """Low-volume demo geocoder with cache + public-service rate limit.

    Keep this provider replaceable. Production/government deployment should use
    an approved/self-hosted geocoder rather than depend on the public endpoint.
    """
    global _LAST_GEOCODE_AT
    with _GEOCODE_LOCK:
        wait_for = 1.05 - (monotonic() - _LAST_GEOCODE_AT)
        if wait_for > 0:
            sleep(wait_for)
        with httpx.Client(
            timeout=8.0,
            follow_redirects=True,
            headers={
                "User-Agent": "LandGuard-SIH2026/0.3",
                "Accept-Language": "en",
            },
        ) as client:
            response = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 5,
                    "countrycodes": "in",
                },
            )
            _LAST_GEOCODE_AT = monotonic()
            response.raise_for_status()
            rows = response.json()

    results = []
    for row in rows[:5]:
        try:
            lat = float(row["lat"])
            lon = float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        results.append((
            str(row.get("display_name") or query)[:300],
            lat,
            lon,
            str(row.get("type"))[:80] if row.get("type") else None,
        ))
    return tuple(results)


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine fallback used for SQLite/tests and response display."""
    radius = 6371.0088
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return radius * 2 * asin(sqrt(a))


def _as_map_project(project: Project, distance_km: float | None = None) -> MapProject:
    risk = risk_snapshot(project)
    return MapProject(
        project_id=project.project_id,
        project_name=project.project_name,
        state=project.state,
        district=project.district,
        latitude=project.latitude,
        longitude=project.longitude,
        acquisition_stage=project.acquisition_stage,
        pending_approvals=project.pending_approvals,
        legal_disputes=project.legal_disputes,
        compensation_completion_pct=project.compensation_completion_pct,
        possession_pct=project.possession_pct,
        rehabilitation_completion_pct=project.rehabilitation_completion_pct,
        project_type=project.project_type,
        distance_km=round(distance_km, 2) if distance_km is not None else None,
        delay_probability=risk["delay_probability"] if risk else None,
        risk_category=risk["risk_category"] if risk else None,
        slip_alert=risk["slip_alert"] if risk else None,
    )


@router.get("/map-data", response_model=list[MapProject])
def map_data(
    db: Annotated[Session, Depends(get_db)],
    state: str | None = Query(None, max_length=100),
    district: str | None = Query(None, max_length=100),
    stage: str | None = Query(None, max_length=40),
    min_lat: float | None = Query(None, ge=-90, le=90),
    max_lat: float | None = Query(None, ge=-90, le=90),
    min_lon: float | None = Query(None, ge=-180, le=180),
    max_lon: float | None = Query(None, ge=-180, le=180),
    near_lat: float | None = Query(None, ge=-90, le=90),
    near_lon: float | None = Query(None, ge=-180, le=180),
    radius_km: float | None = Query(None, gt=0, le=1000),
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    bbox_values = (min_lat, max_lat, min_lon, max_lon)
    if any(value is not None for value in bbox_values) and not all(value is not None for value in bbox_values):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="All map bounds must be supplied together.")
    if min_lat is not None and (min_lat > max_lat or min_lon > max_lon):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Map bounds are invalid.")
    nearby_values = (near_lat, near_lon, radius_km)
    if any(value is not None for value in nearby_values) and not all(value is not None for value in nearby_values):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="near_lat, near_lon and radius_km must be supplied together.")

    query = scope_projects(select(Project), user)
    if state:
        query = query.where(Project.state == state)
    if district:
        query = query.where(Project.district == district)
    if stage:
        query = query.where(Project.acquisition_stage == stage)

    dialect = db.get_bind().dialect.name
    point = func.ST_SetSRID(func.ST_MakePoint(Project.longitude, Project.latitude), 4326)
    if min_lat is not None:
        if dialect == "postgresql":
            envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
            query = query.where(func.ST_Intersects(point, envelope))
        else:
            query = query.where(
                Project.latitude.between(min_lat, max_lat),
                Project.longitude.between(min_lon, max_lon),
            )

    if near_lat is not None and dialect == "postgresql":
        origin = func.ST_SetSRID(func.ST_MakePoint(near_lon, near_lat), 4326)
        query = query.where(func.ST_DistanceSphere(point, origin) <= radius_km * 1000)

    projects = db.scalars(query.order_by(Project.state, Project.district, Project.project_id)).all()
    result = []
    for project in projects:
        distance = None
        if near_lat is not None:
            distance = _distance_km(near_lat, near_lon, project.latitude, project.longitude)
            if dialect != "postgresql" and distance > radius_km:
                continue
        result.append(_as_map_project(project, distance))
    return result


_ALLOWED_OWNERSHIP = {"GOVERNMENT", "PRIVATE", "GOVERNMENT_LEASEHOLD", "INSTITUTIONAL", "UNKNOWN"}
_OWNERSHIP_ALIASES = {
    "GOVERNMENT": "GOVERNMENT",
    "GOVT": "GOVERNMENT",
    "GOVT LAND": "GOVERNMENT",
    "GOVERNMENT LAND": "GOVERNMENT",
    "SARKARI": "GOVERNMENT",
    "PRIVATE": "PRIVATE",
    "PRIVATE LAND": "PRIVATE",
    "RAIYAT": "PRIVATE",
    "RYOT": "PRIVATE",
    "GOVERNMENT LEASEHOLD": "GOVERNMENT_LEASEHOLD",
    "GOVT LEASEHOLD": "GOVERNMENT_LEASEHOLD",
    "LEASEHOLD": "GOVERNMENT_LEASEHOLD",
    "INSTITUTIONAL": "INSTITUTIONAL",
    "INSTITUTION": "INSTITUTIONAL",
    "UNKNOWN": "UNKNOWN",
    "UNVERIFIED": "UNKNOWN",
}


def _parcel_feature(parcel: LandParcel) -> LandParcelFeature:
    return LandParcelFeature(
        parcel_id=parcel.parcel_id,
        project_id=parcel.project_id,
        state=parcel.state,
        district=parcel.district,
        tahasil=parcel.tahasil,
        village=parcel.village,
        plot_no=parcel.plot_no,
        khata_no=parcel.khata_no,
        unique_plot_id=parcel.unique_plot_id,
        ownership_type=parcel.ownership_type,
        government_category=parcel.government_category,
        tenant_name=parcel.tenant_name,
        kisam=parcel.kisam,
        area_acres=round(parcel.area_acres or 0, 4),
        ror_verified=bool(parcel.ror_verified),
        source_name=parcel.source_name,
        source_record_id=parcel.source_record_id,
        geometry=parcel.geometry_geojson,
    )




def _get_accessible_project(db: Session, project_id: str, user):
    project = db.scalar(select(Project).where(Project.project_id == project_id))
    if project is None:
        raise HTTPException(404, "Project not found")
    assert_project_access(project, user)
    return project


def _first(props: dict, *keys):
    lower = {str(key).lower(): value for key, value in props.items()}
    for key in keys:
        value = lower.get(key.lower())
        if value not in (None, ""):
            return value
    return None


def _normalise_ownership(value) -> str:
    if value is None:
        return "UNKNOWN"
    text = str(value).replace("_", " ").replace("-", " ").strip().upper()
    text = " ".join(text.split())
    return _OWNERSHIP_ALIASES.get(text, "UNKNOWN")


def _ring_area_m2(ring) -> float:
    """Small-area WGS84 approximation used when source data omits parcel area."""
    if not isinstance(ring, list) or len(ring) < 3:
        return 0.0
    try:
        coords = [(float(point[0]), float(point[1])) for point in ring if len(point) >= 2]
    except (TypeError, ValueError, IndexError):
        return 0.0
    if len(coords) < 3:
        return 0.0
    radius = 6371008.8
    mean_lat = radians(sum(lat for _, lat in coords) / len(coords))
    xy = [(radius * radians(lon) * cos(mean_lat), radius * radians(lat)) for lon, lat in coords]
    area = 0.0
    for i, (x1, y1) in enumerate(xy):
        x2, y2 = xy[(i + 1) % len(xy)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def _valid_wgs84_geometry(geometry: dict) -> bool:
    """Reject projected-coordinate files accidentally labelled as EPSG:4326."""
    def walk(value):
        if not isinstance(value, list):
            return True
        if len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
            lon, lat = float(value[0]), float(value[1])
            return -180 <= lon <= 180 and -90 <= lat <= 90
        return all(walk(child) for child in value)

    return walk(geometry.get("coordinates") or [])


def _geometry_area_acres(geometry: dict) -> float:
    coords = geometry.get("coordinates") or []
    geometry_type = geometry.get("type")
    if geometry_type == "Polygon":
        polygons = [coords]
    elif geometry_type == "MultiPolygon":
        polygons = coords
    else:
        return 0.0
    area_m2 = 0.0
    for polygon in polygons:
        if not polygon:
            continue
        area_m2 += _ring_area_m2(polygon[0])
        for hole in polygon[1:]:
            area_m2 -= _ring_area_m2(hole)
    return max(area_m2, 0.0) / 4046.8564224


def _ownership_status(parcels: list[LandParcel]) -> str:
    if not parcels:
        return "UNAVAILABLE"
    if all(bool(parcel.ror_verified) for parcel in parcels):
        return "AUTHORITY_VERIFIED"
    return "IMPORTED_DATASET"


@router.get("/gis/ownership/parcels", response_model=list[LandParcelFeature])
def ownership_parcels(
    db: Annotated[Session, Depends(get_db)],
    project_id: str = Query(..., min_length=1, max_length=40),
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    _get_accessible_project(db, project_id, user)
    parcels = db.scalars(
        select(LandParcel)
        .where(LandParcel.project_id == project_id)
        .order_by(LandParcel.village, LandParcel.plot_no, LandParcel.parcel_id)
    ).all()
    return [_parcel_feature(parcel) for parcel in parcels]


@router.get("/gis/ownership/summary/{project_id}", response_model=OwnershipSummary)
def ownership_summary(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    _get_accessible_project(db, project_id, user)
    parcels = list(db.scalars(select(LandParcel).where(LandParcel.project_id == project_id)).all())
    status = _ownership_status(parcels)
    total_area = sum(max(parcel.area_acres or 0, 0) for parcel in parcels)
    breakdown = []
    for ownership in ["GOVERNMENT", "PRIVATE", "GOVERNMENT_LEASEHOLD", "INSTITUTIONAL", "UNKNOWN"]:
        rows = [parcel for parcel in parcels if parcel.ownership_type == ownership]
        if not rows:
            continue
        area = sum(max(parcel.area_acres or 0, 0) for parcel in rows)
        breakdown.append(OwnershipBreakdown(
            ownership_type=ownership,
            parcel_count=len(rows),
            area_acres=round(area, 3),
            area_pct=round((area / total_area * 100) if total_area else 0, 1),
        ))
    sources = sorted({parcel.source_name for parcel in parcels if parcel.source_name})
    if status == "UNAVAILABLE":
        disclaimer = (
            "No cadastral/RoR parcel dataset is loaded for this project. LandGuard intentionally does not fabricate "
            "parcel boundaries or infer ownership from imagery. Import a WGS84 GeoJSON export from an authorised cadastral source."
        )
    elif status == "AUTHORITY_VERIFIED":
        disclaimer = (
            "These parcels were marked authority-verified at import. LandGuard displays the supplied record classification; "
            "final acquisition decisions should still be checked against the competent land-record authority."
        )
    else:
        disclaimer = (
            "This is an imported cadastral dataset but it has not been marked authority-verified. Ownership is displayed only "
            "from source attributes; LandGuard does not infer legal ownership from satellite imagery or land use."
        )
    return OwnershipSummary(
        project_id=project_id,
        data_status=status,
        total_parcels=len(parcels),
        total_area_acres=round(total_area, 3),
        verified_parcels=sum(1 for parcel in parcels if parcel.ror_verified),
        source_names=sources,
        breakdown=breakdown,
        disclaimer=disclaimer,
    )


@router.post("/gis/ownership/import", response_model=ParcelImportResult)
def import_ownership_parcels(
    payload: ParcelImportRequest,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    if payload.crs_epsg != 4326:
        raise HTTPException(422, "Cadastral GeoJSON must be converted to WGS84 / EPSG:4326 before import.")
    if payload.project_id:
        _get_accessible_project(db, payload.project_id, user)
    elif payload.replace_project_dataset:
        raise HTTPException(422, "replace_project_dataset requires a project_id.")

    role = user.get("role")
    if role == "DISTRICT_OFFICER" and (user.get("state") != payload.state or user.get("district") != payload.district):
        raise HTTPException(403, "Import is outside your assigned district.")
    if role == "STATE_OFFICER" and user.get("state") != payload.state:
        raise HTTPException(403, "Import is outside your assigned state.")

    source_name = payload.source_name.strip()[:120] or "CADASTRAL_GEOJSON_IMPORT"
    if source_name.upper().startswith(("ILLUSTRATIVE", "DEMO", "SYNTHETIC")):
        raise HTTPException(422, "Synthetic/demo parcel sources are not accepted by the cadastral ownership layer.")

    prepared = []
    rejected = 0
    for index, feature in enumerate(payload.features, start=1):
        geometry = feature.geometry or {}
        if geometry.get("type") not in {"Polygon", "MultiPolygon"} or not geometry.get("coordinates") or not _valid_wgs84_geometry(geometry):
            rejected += 1
            continue
        props = feature.properties or {}
        ownership = _normalise_ownership(_first(
            props, "ownership_type", "ownership", "owner_type", "land_ownership", "tenure"
        ))
        plot_no = _first(props, "plot_no", "plot", "plotnumber", "plot_number")
        khata_no = _first(props, "khata_no", "khata", "khatiyan_no", "khatiyan")
        unique_plot_id = _first(props, "unique_plot_id", "plot_unique_id", "upi", "unique_id")
        explicit_id = _first(props, "parcel_id", "feature_id", "id")
        parcel_id = str(explicit_id or unique_plot_id or f"{source_name}:{payload.project_id or payload.district}:{plot_no or index}")[:80]
        area_value = _first(props, "area_acres", "area_acre", "acres")
        try:
            area_acres = max(float(area_value), 0) if area_value is not None else _geometry_area_acres(geometry)
        except (TypeError, ValueError):
            area_acres = _geometry_area_acres(geometry)
        prepared.append((parcel_id, dict(
            project_id=payload.project_id,
            state=payload.state,
            district=payload.district,
            tahasil=_first(props, "tahasil", "tehsil", "tahsil"),
            village=_first(props, "village", "village_name", "mouza"),
            plot_no=str(plot_no) if plot_no is not None else None,
            khata_no=str(khata_no) if khata_no is not None else None,
            unique_plot_id=str(unique_plot_id) if unique_plot_id is not None else None,
            ownership_type=ownership,
            government_category=_first(props, "government_category", "govt_category", "department"),
            tenant_name=_first(props, "tenant_name", "tenant", "raiyat_name"),
            kisam=_first(props, "kisam", "land_class", "classification"),
            area_acres=round(area_acres, 6),
            ror_verified=payload.ror_verified,
            source_name=source_name,
            source_record_id=str(_first(props, "source_record_id", "record_id"))[:160] if _first(props, "source_record_id", "record_id") is not None else None,
            geometry_geojson=geometry,
        )))

    if not prepared:
        raise HTTPException(422, "No valid Polygon or MultiPolygon features were found in the cadastral GeoJSON.")

    if payload.replace_project_dataset and payload.project_id:
        db.execute(delete(LandParcel).where(LandParcel.project_id == payload.project_id))
        db.flush()

    imported = updated = 0
    for parcel_id, values in prepared:
        parcel = db.scalar(select(LandParcel).where(LandParcel.parcel_id == parcel_id))
        if parcel is None:
            db.add(LandParcel(parcel_id=parcel_id, **values))
            imported += 1
        else:
            for key, value in values.items():
                setattr(parcel, key, value)
            updated += 1
    if payload.project_id:
        record_audit(
            db, project_id=payload.project_id, event_type="CADASTRAL_IMPORT", user=user,
            source=source_name, detail=f"Imported/updated {imported + updated} cadastral parcel records; {rejected} rejected.",
        )
    db.commit()
    status = "AUTHORITY_VERIFIED" if payload.ror_verified else "IMPORTED_DATASET"
    return ParcelImportResult(
        imported=imported,
        updated=updated,
        rejected=rejected,
        source_name=source_name,
        data_status=status,
    )


@router.delete("/gis/ownership/parcels/{project_id}")
def clear_ownership_parcels(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    _get_accessible_project(db, project_id, user)
    result = db.execute(delete(LandParcel).where(LandParcel.project_id == project_id))
    record_audit(
        db, project_id=project_id, event_type="CADASTRAL_DATA_REMOVED", user=user,
        detail=f"Removed {result.rowcount or 0} cadastral parcel records from the project GIS layer.",
    )
    db.commit()
    return {"project_id": project_id, "deleted": result.rowcount or 0, "data_status": "UNAVAILABLE"}


@router.get("/gis/land-records/config")
def land_records_config(user=Depends(require_roles(*OPERATIONAL_ROLES))):
    return {
        "odisha_bhunaksha_url": "https://bhunakshaodisha.nic.in/bhunaksha/",
        "odisha_bhulekh_url": "https://bhulekh.ori.nic.in/",
        "odisha_bhulekh_map_url": "https://bhulekh.ori.nic.in/frmMapView.aspx",
        "odisha_unique_plot_url": "https://bhulekh.ori.nic.in/SearchYourPlot.aspx",
        "bhulekh_service_url": "https://bhulekh.ori.nic.in/bhulekhservice.asmx",
        "geometry_policy": "IMPORT_AUTHORISED_CADASTRAL_EXPORT",
        "ownership_policy": "SOURCE_ATTRIBUTE_ONLY",
        "note": (
            "BhuNaksha/Bhulekh are reference and record-validation sources. LandGuard does not scrape map geometry or infer "
            "ownership. Import an authorised WGS84 cadastral GeoJSON and mark it verified only when its provenance is confirmed."
        ),
    }


@router.get("/gis/geocode", response_model=list[GeocodeResult])
def geocode_place(
    q: str = Query(..., min_length=2, max_length=240),
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    """User-initiated place search for the project-location picker."""
    try:
        rows = _nominatim_search(q.strip())
    except (httpx.HTTPError, ValueError):
        from fastapi import HTTPException
        raise HTTPException(503, "Place search is temporarily unavailable. Click the map to select the project location.")

    return [
        GeocodeResult(
            display_name=display_name,
            latitude=latitude,
            longitude=longitude,
            result_type=result_type,
        )
        for display_name, latitude, longitude, result_type in rows
    ]


@router.get("/gis/bhuvan/config")
def bhuvan_config(user=Depends(require_roles(*OPERATIONAL_ROLES))):
    return {
        "wms_url": "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms",
        "version": "1.1.1",
        "usage": "THEMATIC_CONTEXT_ONLY",
        "note": "Bhuvan WMS provides real thematic/geospatial context such as LULC and water/urban layers. Parcel ownership must come from authorised cadastral/RoR records and is never inferred from imagery or LULC.",
    }

# ---------------------------------------------------------------------------
# Physical context / acquisition-impact layer
# ---------------------------------------------------------------------------
# Legal ownership remains in the cadastral/RoR layer above.  This layer is
# deliberately separate: it answers "what is mapped on the ground here?" using
# OpenStreetMap physical features.  It must never be presented as proof of
# ownership or as an automatic demolition order.

_OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
_PUBLIC_AMENITIES = {
    "school", "college", "university", "kindergarten", "hospital", "clinic",
    "doctors", "police", "fire_station", "townhall", "courthouse",
    "community_centre", "library", "post_office", "bus_station",
    "public_building", "government", "place_of_worship",
}
_RESIDENTIAL_BUILDINGS = {
    "house", "residential", "apartments", "detached", "semidetached_house",
    "terrace", "bungalow", "dormitory", "hut", "cabin",
}
_COMMERCIAL_BUILDINGS = {
    "commercial", "retail", "office", "industrial", "warehouse", "hotel",
    "supermarket", "kiosk", "service",
}
_TAG_KEYS = {
    "name", "building", "building:use", "shop", "amenity", "office",
    "tourism", "healthcare", "leisure", "operator", "operator:type", "government",
    "religion", "place", "ownership", "access", "addr:housenumber", "addr:street",
}


def _physical_category(tags: dict) -> tuple[str, str | None]:
    if tags.get("building") and tags.get("building") != "no":
        return "BUILDING", str(tags.get("building"))
    if tags.get("shop"):
        return "SHOP", str(tags.get("shop"))
    if tags.get("office"):
        return "OFFICE", str(tags.get("office"))
    amenity = tags.get("amenity")
    if amenity:
        return ("PUBLIC_FACILITY" if amenity in _PUBLIC_AMENITIES else "AMENITY"), str(amenity)
    if tags.get("government"):
        return "PUBLIC_FACILITY", str(tags.get("government"))
    if tags.get("healthcare"):
        return "AMENITY", str(tags.get("healthcare"))
    if tags.get("tourism"):
        return "PLACE", str(tags.get("tourism"))
    if tags.get("place"):
        return "PLACE", str(tags.get("place"))
    return "PLACE", None


def _mapped_use_class(tags: dict) -> tuple[str, str]:
    """Classify mapped *use/context* from explicit OSM tags, never legal ownership."""
    building = str(tags.get("building") or "").lower()
    amenity = str(tags.get("amenity") or "").lower()
    office = str(tags.get("office") or "").lower()
    shop = str(tags.get("shop") or "").lower()
    government = str(tags.get("government") or "").lower()
    operator_type = str(tags.get("operator:type") or "").lower()

    if office == "government" or building in {"government", "government_office"} or government or operator_type == "government":
        basis = "office=government" if office == "government" else (f"building={building}" if building in {"government", "government_office"} else (f"government={government}" if government else "operator:type=government"))
        return "GOVERNMENT", basis

    if amenity in {"townhall", "courthouse", "police", "fire_station", "post_office", "community_centre", "library", "public_building", "bus_station"} or building in {"public", "civic", "fire_station"}:
        return "PUBLIC_CIVIC", (f"amenity={amenity}" if amenity else f"building={building}")

    if amenity in {"school", "college", "university", "kindergarten", "hospital", "clinic", "doctors"} or building in {"school", "college", "university", "hospital"} or tags.get("healthcare"):
        return "INSTITUTIONAL", (f"amenity={amenity}" if amenity else (f"building={building}" if building else f"healthcare={tags.get('healthcare')}"))

    if amenity == "place_of_worship" or building in {"religious", "church", "mosque", "temple", "chapel", "cathedral", "synagogue", "shrine"}:
        return "RELIGIOUS", (f"amenity={amenity}" if amenity else f"building={building}")

    if shop or office or building in _COMMERCIAL_BUILDINGS or amenity in {"marketplace", "bank", "atm", "fuel", "restaurant", "cafe", "fast_food", "pub", "bar", "pharmacy"}:
        if shop:
            basis = f"shop={shop}"
        elif office:
            basis = f"office={office}"
        elif building in _COMMERCIAL_BUILDINGS:
            basis = f"building={building}"
        else:
            basis = f"amenity={amenity}"
        return "COMMERCIAL", basis

    if building in _RESIDENTIAL_BUILDINGS:
        return "RESIDENTIAL", f"building={building}"

    return "OTHER_UNKNOWN", "No explicit government/public/institutional/commercial/residential use tag"


def _element_geometry(element: dict) -> tuple[dict, float, float] | None:
    element_type = element.get("type")
    if element_type == "node" and element.get("lat") is not None and element.get("lon") is not None:
        lat, lon = float(element["lat"]), float(element["lon"])
        return {"type": "Point", "coordinates": [lon, lat]}, lat, lon

    geometry = element.get("geometry") or []
    coords = []
    for point in geometry:
        if point.get("lat") is None or point.get("lon") is None:
            continue
        coords.append([float(point["lon"]), float(point["lat"])])
    if coords:
        lat = sum(point[1] for point in coords) / len(coords)
        lon = sum(point[0] for point in coords) / len(coords)
        tags = element.get("tags") or {}
        if len(coords) >= 3 and tags.get("building"):
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            return {"type": "Polygon", "coordinates": [coords]}, lat, lon
        return {"type": "LineString", "coordinates": coords}, lat, lon

    center = element.get("center") or {}
    if center.get("lat") is not None and center.get("lon") is not None:
        lat, lon = float(center["lat"]), float(center["lon"])
        return {"type": "Point", "coordinates": [lon, lat]}, lat, lon
    return None


def _parse_overpass(rows: list[dict]) -> list[PhysicalFeature]:
    features: list[PhysicalFeature] = []
    seen: set[str] = set()
    for element in rows:
        tags = element.get("tags") or {}
        if not any(tags.get(key) for key in ("building", "shop", "amenity", "office", "government", "healthcare", "tourism", "place")):
            continue
        feature_id = f"osm-{element.get('type', 'feature')}-{element.get('id', 'unknown')}"
        if feature_id in seen:
            continue
        parsed = _element_geometry(element)
        if parsed is None:
            continue
        geometry, lat, lon = parsed
        category, subtype = _physical_category(tags)
        use_class, classification_basis = _mapped_use_class(tags)
        clean_tags = {str(k): str(v)[:160] for k, v in tags.items() if k in _TAG_KEYS and v is not None}
        features.append(PhysicalFeature(
            feature_id=feature_id,
            category=category,
            subtype=subtype,
            name=str(tags.get("name"))[:180] if tags.get("name") else None,
            latitude=lat,
            longitude=lon,
            geometry=geometry,
            tags=clean_tags,
            use_class=use_class,
            classification_basis=classification_basis,
            source_name="OpenStreetMap",
        ))
        seen.add(feature_id)
        if len(features) >= 700:
            break
    return features


@lru_cache(maxsize=128)
def _overpass_fetch(query: str) -> tuple[dict, ...]:
    last_error: Exception | None = None
    for endpoint in _OVERPASS_ENDPOINTS:
        try:
            with httpx.Client(
                timeout=5.5,
                follow_redirects=True,
                headers={"User-Agent": "LandGuard-SIH2026/0.4"},
            ) as client:
                response = client.post(endpoint, data={"data": query})
                response.raise_for_status()
                payload = response.json()
                return tuple(payload.get("elements") or [])
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
    if last_error:
        raise last_error
    return tuple()


def _overpass_radius_query(lat: float, lon: float, radius_m: int) -> str:
    area = f"(around:{radius_m},{lat:.7f},{lon:.7f})"
    return (
        "[out:json][timeout:7];("
        f'nwr["building"]{area};'
        f'nwr["shop"]{area};'
        f'nwr["amenity"]{area};'
        f'nwr["office"]{area};'
        f'nwr["government"]{area};'
        f'nwr["healthcare"]{area};'
        f'nwr["tourism"]{area};'
        ");out center tags geom;"
    )


def _overpass_polygon_query(points: list[tuple[float, float]]) -> str:
    poly = " ".join(f"{lat:.7f} {lon:.7f}" for lat, lon in points)
    return (
        "[out:json][timeout:7];("
        f'nwr["building"](poly:"{poly}");'
        f'nwr["shop"](poly:"{poly}");'
        f'nwr["amenity"](poly:"{poly}");'
        f'nwr["office"](poly:"{poly}");'
        f'nwr["government"](poly:"{poly}");'
        f'nwr["healthcare"](poly:"{poly}");'
        f'nwr["tourism"](poly:"{poly}");'
        ");out center tags geom;"
    )


def _polygon_area_hectares(points: list[tuple[float, float]]) -> float:
    """Approximate polygon area for small local acquisition footprints."""
    if len(points) < 3:
        return 0.0
    mean_lat = sum(lat for lat, _ in points) / len(points)
    metres_per_deg_lat = 111_320.0
    metres_per_deg_lon = 111_320.0 * cos(radians(mean_lat))
    xy = [(lon * metres_per_deg_lon, lat * metres_per_deg_lat) for lat, lon in points]
    area = 0.0
    for i, (x1, y1) in enumerate(xy):
        x2, y2 = xy[(i + 1) % len(xy)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0 / 10_000.0


def _physical_summary(
    project_id: str,
    mode: str,
    features: list[PhysicalFeature],
    source: str,
    source_status: str,
    analysis_area_hectares: float | None = None,
) -> PhysicalImpactSummary:
    def has_tag(feature: PhysicalFeature, key: str, values: set[str] | None = None) -> bool:
        value = feature.tags.get(key)
        return bool(value) if values is None else value in values

    building_features = [f for f in features if f.category == "BUILDING"]
    residential = sum(1 for f in building_features if (f.subtype or "") in _RESIDENTIAL_BUILDINGS)
    commercial = sum(1 for f in building_features if (f.subtype or "") in _COMMERCIAL_BUILDINGS or has_tag(f, "shop"))
    shops = sum(1 for f in features if f.category == "SHOP" or has_tag(f, "shop"))
    public = sum(1 for f in features if f.category == "PUBLIC_FACILITY" or has_tag(f, "amenity", _PUBLIC_AMENITIES))
    schools = sum(1 for f in features if has_tag(f, "amenity", {"school", "college", "university", "kindergarten"}))
    healthcare = sum(1 for f in features if has_tag(f, "amenity", {"hospital", "clinic", "doctors", "pharmacy"}) or has_tag(f, "healthcare"))
    offices = sum(1 for f in features if f.category == "OFFICE" or has_tag(f, "office"))
    government_mapped = sum(1 for f in features if f.use_class == "GOVERNMENT")
    public_civic_mapped = sum(1 for f in features if f.use_class == "PUBLIC_CIVIC")
    institutional_mapped = sum(1 for f in features if f.use_class == "INSTITUTIONAL")
    commercial_mapped = sum(1 for f in features if f.use_class == "COMMERCIAL")
    residential_mapped = sum(1 for f in features if f.use_class == "RESIDENTIAL")
    religious_mapped = sum(1 for f in features if f.use_class == "RELIGIOUS")
    other_unknown_mapped = sum(1 for f in features if f.use_class == "OTHER_UNKNOWN")

    if source_status in {"LIVE_COMMUNITY_MAP", "LIVE_OVERTURE_MAPS", "LIVE_OPEN_DATA_FUSION"}:
        provider_label = source or "open map sources"
        result_message = (
            f"{len(features)} real mapped features found inside the drawn acquisition area from {provider_label}."
            if mode == "DRAWN_IMPACT_AREA"
            else f"{len(features)} real mapped features found around the project location from {provider_label}."
        )
    elif source_status == "NO_MAPPED_FEATURES_IN_AREA":
        result_message = "No building footprints or mapped places were returned by the connected open-data providers inside this drawn area. This does not prove that the land is empty; verify the project location and field-survey the footprint."
    elif source_status == "NO_MAPPED_FEATURES":
        result_message = "No building footprints or mapped places were returned by the connected open-data providers within the current scan. This is a coverage result, not proof that the area is empty."
    elif source_status == "SERVICE_UNAVAILABLE":
        result_message = "Live open-map feature providers could not be reached. No synthetic fallback is used; retry when connectivity is available."
    else:
        result_message = None

    disclaimer = (
        "Real-world mapped-use context from open geospatial sources (OpenStreetMap and/or Overture Maps). "
        "Government/public/institutional/commercial/residential labels describe mapped use/classification, not legal parcel ownership. "
        "Field survey and competent-authority verification are required before acquisition, compensation, relocation or demolition action."
    )
    return PhysicalImpactSummary(
        project_id=project_id,
        mode=mode,
        feature_count=len(features),
        mapped_structures=len(building_features),
        residential_structures=residential,
        commercial_structures=commercial,
        shops_businesses=shops,
        public_facilities=public,
        schools=schools,
        healthcare=healthcare,
        offices=offices,
        government_mapped=government_mapped,
        public_civic_mapped=public_civic_mapped,
        institutional_mapped=institutional_mapped,
        commercial_mapped=commercial_mapped,
        residential_mapped=residential_mapped,
        religious_mapped=religious_mapped,
        other_unknown_mapped=other_unknown_mapped,
        named_places=sum(1 for f in features if f.name),
        source_name=source,
        source_status=source_status,
        analysis_area_hectares=round(analysis_area_hectares, 3) if analysis_area_hectares is not None else None,
        result_message=result_message,
        disclaimer=disclaimer,
    )


def _point_in_polygon(lat: float, lon: float, points: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(points) - 1
    for i in range(len(points)):
        yi, xi = points[i]
        yj, xj = points[j]
        crosses = ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi)
        if crosses:
            inside = not inside
        j = i
    return inside



def _bbox_from_radius(lat: float, lon: float, radius_m: int) -> tuple[float, float, float, float]:
    lat_delta = radius_m / 111_320.0
    lon_scale = max(cos(radians(lat)), 0.15)
    lon_delta = radius_m / (111_320.0 * lon_scale)
    return (lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta)


def _bbox_from_polygon(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    lats = [lat for lat, _ in points]
    lons = [lon for _, lon in points]
    return (min(lons), min(lats), max(lons), max(lats))


def _merge_real_world_features(
    osm_features: list[PhysicalFeature],
    overture_rows: list[dict],
) -> list[PhysicalFeature]:
    """Fuse OSM semantics with Overture's denser real building footprint coverage.

    When Overture buildings are available they replace OSM building outlines to
    avoid double-counting the same physical structures.  OSM named POIs are kept
    because they often contain richer local semantics.  Overture places are used
    only when an equivalent named/category POI was not already returned by OSM.
    """
    overture_features = [PhysicalFeature(**row) for row in overture_rows]
    overture_buildings = [row for row in overture_features if row.category == "BUILDING"]
    osm_non_buildings = [row for row in osm_features if row.category != "BUILDING"]
    base = overture_buildings if overture_buildings else [row for row in osm_features if row.category == "BUILDING"]

    seen_place_keys: set[tuple[str, str, int, int]] = set()
    merged_places: list[PhysicalFeature] = []
    for feature in osm_non_buildings + [row for row in overture_features if row.category != "BUILDING"]:
        key = (
            (feature.name or "").strip().lower(),
            (feature.subtype or feature.category or "").strip().lower(),
            round(float(feature.latitude) * 10000),
            round(float(feature.longitude) * 10000),
        )
        if key in seen_place_keys:
            continue
        seen_place_keys.add(key)
        merged_places.append(feature)
    return (base + merged_places)[:1500]


def _load_osm_features(query: str) -> tuple[list[PhysicalFeature], str | None]:
    try:
        return _parse_overpass(list(_overpass_fetch(query))), None
    except (httpx.HTTPError, ValueError, OSError) as exc:
        return [], str(exc)


def _load_overture_features(
    bbox: tuple[float, float, float, float],
    polygon: list[tuple[float, float]] | None,
):
    # Overture Places is intentionally disabled in the fast path. OSM already
    # provides the local POI semantics while Overture is used for the denser
    # real building-footprint layer. This cuts a second cloud parquet query.
    return fetch_overture_features(
        bbox, polygon_points=polygon, include_places=False,
        max_buildings=900, max_places=0,
    )


def _physical_response(
    project: Project,
    mode: str,
    query: str,
    *,
    bbox: tuple[float, float, float, float],
    polygon: list[tuple[float, float]] | None = None,
) -> PhysicalImpactResponse:
    """Fetch real GIS providers concurrently with a hard response budget.

    Public map/cloud providers can occasionally stall.  The old implementation
    called Overpass and then Overture sequentially and Overture used read_all(),
    which is why the browser could remain on "Loading/Analyzing" indefinitely.
    This path returns within a bounded time and uses whichever provider replied.
    """
    area_ha = _polygon_area_hectares(polygon) if polygon else None
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="landguard-gis")
    osm_future = executor.submit(_load_osm_features, query)
    overture_future = executor.submit(_load_overture_features, bbox, polygon)
    done, pending = wait({osm_future, overture_future}, timeout=11.0)

    osm_features: list[PhysicalFeature] = []
    overpass_error: str | None = None
    overture_rows: list[dict] = []
    overture_error: str | None = None

    if osm_future in done:
        try:
            osm_features, overpass_error = osm_future.result()
        except Exception as exc:  # defensive provider boundary
            overpass_error = str(exc)
    else:
        overpass_error = "OpenStreetMap/Overpass timed out after 11 seconds"

    if overture_future in done:
        try:
            overture = overture_future.result()
            if overture.available:
                overture_rows = overture.features
            overture_error = overture.error
        except Exception as exc:  # defensive provider boundary
            overture_error = str(exc)
    else:
        overture_error = "Overture Maps timed out after 11 seconds"

    for future in pending:
        future.cancel()
    # Never wait for a slow remote provider after our response budget expires.
    executor.shutdown(wait=False, cancel_futures=True)

    if overture_rows:
        features = _merge_real_world_features(osm_features, overture_rows)
        source_names = sorted({feature.source_name for feature in features if feature.source_name})
        source = " + ".join(source_names) or "Overture Maps"
    else:
        features = osm_features
        source = "OpenStreetMap"

    if features:
        status = "LIVE_OPEN_DATA_FUSION" if "Overture" in source and "OpenStreetMap" in source else (
            "LIVE_OVERTURE_MAPS" if "Overture" in source else "LIVE_COMMUNITY_MAP"
        )
    elif overpass_error and overture_error:
        status = "SERVICE_UNAVAILABLE"
    else:
        status = "NO_MAPPED_FEATURES_IN_AREA" if mode == "DRAWN_IMPACT_AREA" else "NO_MAPPED_FEATURES"

    summary = _physical_summary(project.project_id, mode, features, source, status, analysis_area_hectares=area_ha)
    if not features and (overpass_error or overture_error):
        detail = "; ".join(value for value in (overpass_error, overture_error) if value)
        summary.result_message = (
            "Real-world providers did not return map features within the 11-second live-data budget. "
            "The request was stopped instead of leaving the officer screen stuck. Retry once, or verify the project point/footprint."
        )
        if detail:
            summary.result_message += f" Provider detail: {detail[:260]}"
    return PhysicalImpactResponse(features=features, summary=summary)


@router.get("/gis/physical-context/{project_id}", response_model=PhysicalImpactResponse)
def physical_context(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    radius_m: int = Query(500, ge=100, le=1500),
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    project = _get_accessible_project(db, project_id, user)
    return _physical_response(
        project,
        "CONTEXT_RADIUS",
        _overpass_radius_query(project.latitude, project.longitude, radius_m),
        bbox=_bbox_from_radius(project.latitude, project.longitude, radius_m),
    )


@router.post("/gis/physical-impact/{project_id}", response_model=PhysicalImpactResponse)
def physical_impact(
    project_id: str,
    payload: ImpactPolygonRequest,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(*OPERATIONAL_ROLES)),
):
    project = _get_accessible_project(db, project_id, user)
    points = [(float(lat), float(lon)) for lat, lon in payload.points]
    for lat, lon in points:
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            from fastapi import HTTPException
            raise HTTPException(422, "Impact-area coordinates are invalid.")
    # Keep a demo/request polygon local enough to the selected project.  This
    # prevents accidental country-scale Overpass queries from a stray click.
    if any(_distance_km(project.latitude, project.longitude, lat, lon) > 12 for lat, lon in points):
        from fastapi import HTTPException
        raise HTTPException(422, "Draw the impact area within 12 km of the selected project location.")
    return _physical_response(
        project,
        "DRAWN_IMPACT_AREA",
        _overpass_polygon_query(points),
        bbox=_bbox_from_polygon(points),
        polygon=points,
    )
