from typing import Any, Literal

from pydantic import BaseModel, Field


class MapProject(BaseModel):
    project_id: str
    project_name: str
    state: str
    district: str
    latitude: float
    longitude: float
    acquisition_stage: str
    pending_approvals: int
    legal_disputes: int
    compensation_completion_pct: float
    possession_pct: float
    rehabilitation_completion_pct: float
    project_type: str
    distance_km: float | None = None
    delay_probability: float | None = None
    risk_category: str | None = None
    slip_alert: bool | None = None


OwnershipType = Literal["GOVERNMENT", "PRIVATE", "GOVERNMENT_LEASEHOLD", "INSTITUTIONAL", "UNKNOWN"]
OwnershipDataStatus = Literal["AUTHORITY_VERIFIED", "IMPORTED_DATASET", "UNAVAILABLE"]


class LandParcelFeature(BaseModel):
    parcel_id: str
    project_id: str | None = None
    state: str
    district: str
    tahasil: str | None = None
    village: str | None = None
    plot_no: str | None = None
    khata_no: str | None = None
    unique_plot_id: str | None = None
    ownership_type: OwnershipType
    government_category: str | None = None
    tenant_name: str | None = None
    kisam: str | None = None
    area_acres: float
    ror_verified: bool
    source_name: str
    source_record_id: str | None = None
    geometry: dict[str, Any]


class OwnershipBreakdown(BaseModel):
    ownership_type: OwnershipType
    parcel_count: int
    area_acres: float
    area_pct: float


class OwnershipSummary(BaseModel):
    project_id: str
    data_status: OwnershipDataStatus
    total_parcels: int
    total_area_acres: float
    verified_parcels: int
    source_names: list[str]
    breakdown: list[OwnershipBreakdown]
    disclaimer: str


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any]
    properties: dict[str, Any] = Field(default_factory=dict)


class ParcelImportRequest(BaseModel):
    project_id: str | None = None
    state: str
    district: str
    source_name: str = "CADASTRAL_GEOJSON_IMPORT"
    ror_verified: bool = False
    crs_epsg: int = 4326
    replace_project_dataset: bool = False
    features: list[GeoJSONFeature] = Field(min_length=1, max_length=10000)


class ParcelImportResult(BaseModel):
    imported: int
    updated: int
    rejected: int
    source_name: str
    data_status: OwnershipDataStatus

class GeocodeResult(BaseModel):
    display_name: str
    latitude: float
    longitude: float
    result_type: str | None = None


PhysicalCategory = Literal["BUILDING", "SHOP", "PUBLIC_FACILITY", "OFFICE", "AMENITY", "PLACE"]
MappedUseClass = Literal["GOVERNMENT", "PUBLIC_CIVIC", "INSTITUTIONAL", "COMMERCIAL", "RESIDENTIAL", "RELIGIOUS", "OTHER_UNKNOWN"]


class PhysicalFeature(BaseModel):
    feature_id: str
    category: PhysicalCategory
    subtype: str | None = None
    name: str | None = None
    latitude: float
    longitude: float
    geometry: dict[str, Any]
    tags: dict[str, str] = Field(default_factory=dict)
    use_class: MappedUseClass = "OTHER_UNKNOWN"
    classification_basis: str | None = None
    source_name: str = "OpenStreetMap"


class PhysicalImpactSummary(BaseModel):
    project_id: str
    mode: Literal["CONTEXT_RADIUS", "DRAWN_IMPACT_AREA"]
    feature_count: int
    mapped_structures: int
    residential_structures: int
    commercial_structures: int
    shops_businesses: int
    public_facilities: int
    schools: int
    healthcare: int
    offices: int
    government_mapped: int
    public_civic_mapped: int
    institutional_mapped: int
    commercial_mapped: int
    residential_mapped: int
    religious_mapped: int
    other_unknown_mapped: int
    named_places: int
    source_name: str
    source_status: str
    analysis_area_hectares: float | None = None
    result_message: str | None = None
    disclaimer: str


class PhysicalImpactResponse(BaseModel):
    features: list[PhysicalFeature]
    summary: PhysicalImpactSummary


class ImpactPolygonRequest(BaseModel):
    points: list[tuple[float, float]] = Field(min_length=3, max_length=80)
