from typing import Any, Literal

from pydantic import BaseModel, Field


ConstructionType = Literal["ROAD", "RAILWAY", "CANAL", "PIPELINE", "OTHER"]
AlignmentMode = Literal["NEW_ALIGNMENT", "EXISTING_NETWORK"]
CoverageStatus = Literal["GOOD", "PARTIAL", "NETWORK_ONLY"]


class RouteAnalysisRequest(BaseModel):
    origin: str = Field(min_length=2, max_length=240)
    destination: str = Field(min_length=2, max_length=240)
    construction_type: ConstructionType = "ROAD"
    alignment_mode: AlignmentMode = "NEW_ALIGNMENT"
    # This is the screening / right-of-way width around the centreline, not a route-length limit.
    corridor_width_m: float = Field(default=40, ge=5, le=2000)
    base_cost_crore_per_km: float | None = Field(default=None, gt=0, le=10000)


class RouteLocation(BaseModel):
    label: str
    latitude: float
    longitude: float


class OfficialRoadReference(BaseModel):
    road_name: str
    category: str
    official_length_km: float
    authority: str
    source_url: str
    route_length_difference_percent: float | None = None
    note: str | None = None


class TerrainSummary(BaseModel):
    available: bool = False
    source: str | None = None
    sample_count: int = 0
    min_elevation_m: float | None = None
    max_elevation_m: float | None = None
    elevation_range_m: float | None = None
    mean_abs_grade_percent: float | None = None
    max_grade_percent: float | None = None


class RouteObstacleSummary(BaseModel):
    mapped_buildings: int = 0
    residential: int = 0
    commercial: int = 0
    government_public: int = 0
    institutional: int = 0
    shops_businesses: int = 0
    schools: int = 0
    healthcare: int = 0
    religious: int = 0
    water_crossings: int = 0
    railway_crossings: int = 0
    powerline_crossings: int = 0
    forest_protected_hits: int = 0
    settlements: int = 0
    existing_bridge_segments: int = 0
    named_places: int = 0
    farmland_hits: int = 0
    residential_landuse_hits: int = 0
    industrial_commercial_landuse_hits: int = 0
    screening_obstacle_points: float = 0


class RouteCandidate(BaseModel):
    route_id: str
    label: str
    distance_km: float
    duration_min: float | None = None
    geometry: dict[str, Any]
    google_maps_url: str
    google_maps_note: str
    route_basis: str
    candidate_kind: Literal["GREENFIELD_CONCEPT", "EXISTING_NETWORK"]
    mapped_data_status: CoverageStatus
    data_coverage_percent: float = 0
    screening_area_ha: float
    obstacle_summary: RouteObstacleSummary
    terrain_summary: TerrainSummary
    comparative_cost_index: float
    route_burden_score: float | None = None
    feasibility_score: float | None = None
    feasibility_label: str
    indicative_cost_crore: float | None = None
    indicative_cost_note: str | None = None
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class RouteAnalysisResponse(BaseModel):
    origin: RouteLocation
    destination: RouteLocation
    construction_type: ConstructionType
    alignment_mode: AlignmentMode
    corridor_width_m: float
    base_cost_crore_per_km: float | None = None
    candidates: list[RouteCandidate]
    recommended_route_id: str
    recommendation_title: str
    executive_summary: str
    key_findings: list[str]
    data_sources: list[str]
    provider_status: str
    mapped_data_status: CoverageStatus
    analysis_confidence: str
    direction_consistency_note: str
    official_road_reference: OfficialRoadReference | None = None
    acquisition_data_readiness: list[str] = Field(default_factory=list)
    limitations: list[str]


class RouteReportRequest(BaseModel):
    analysis: RouteAnalysisResponse
