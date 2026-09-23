from app.schemas.route_analysis import RouteAnalysisRequest, RouteLocation, TerrainSummary
from app.services import route_analysis_service as service


def _stub_geocode(query: str, **_kwargs):
    if "gun" in query.lower():
        return RouteLocation(label="Gunupur, Rayagada, Odisha, India", latitude=19.08, longitude=83.81)
    return RouteLocation(label="Padmapur, Rayagada, Odisha, India", latitude=19.20, longitude=83.70)


def _stub_terrain(routes):
    return {
        route.candidate_key: TerrainSummary(
            available=True,
            source="test-srtm",
            sample_count=12,
            min_elevation_m=100,
            max_elevation_m=130,
            elevation_range_m=30,
            mean_abs_grade_percent=1.2,
            max_grade_percent=3.0,
        )
        for route in routes
    }, None


def _stub_osm(_poly):
    return [
        {"type": "node", "id": 1, "lat": 19.14, "lon": 83.75, "tags": {"amenity": "school", "name": "Mapped School"}},
        {"type": "node", "id": 2, "lat": 19.13, "lon": 83.76, "tags": {"place": "village", "name": "Mapped Village"}},
    ], None


def test_greenfield_screening_uses_real_layers_and_no_45km_cap(monkeypatch):
    monkeypatch.setattr(service, "_geocode", _stub_geocode)
    monkeypatch.setattr(service, "_fetch_terrain", _stub_terrain)
    monkeypatch.setattr(service, "_overpass_fetch_polygon", _stub_osm)

    result = service.analyze_route(RouteAnalysisRequest(origin="Gunupur", destination="Padmapur"))

    assert result.alignment_mode == "NEW_ALIGNMENT"
    assert len(result.candidates) == 3
    assert result.candidates[0].candidate_kind == "GREENFIELD_CONCEPT"
    assert result.candidates[0].terrain_summary.available is True
    assert result.candidates[0].route_burden_score is not None
    assert result.candidates[0].feasibility_score is not None
    assert "no 45 km" in " ".join(result.key_findings).lower()


def test_direction_reversal_keeps_same_preferred_physical_alignment(monkeypatch):
    monkeypatch.setattr(service, "_geocode", _stub_geocode)
    monkeypatch.setattr(service, "_fetch_terrain", _stub_terrain)
    monkeypatch.setattr(service, "_overpass_fetch_polygon", lambda _poly: ([], None))

    forward = service.analyze_route(RouteAnalysisRequest(origin="Gunupur", destination="Padmapur"))
    reverse = service.analyze_route(RouteAnalysisRequest(origin="Padmapur", destination="Gunupur"))

    assert forward.recommended_route_id == reverse.recommended_route_id
    assert forward.candidates[0].distance_km == reverse.candidates[0].distance_km
    assert forward.candidates[0].geometry["coordinates"] == list(reversed(reverse.candidates[0].geometry["coordinates"]))
    assert "canonical" in forward.direction_consistency_note.lower()


def test_long_district_scale_route_is_not_rejected(monkeypatch):
    def far_geocode(query: str, **_kwargs):
        if "alpha" == query.lower():
            return RouteLocation(label="A, District, Odisha, India", latitude=19.0, longitude=83.0)
        return RouteLocation(label="B, District, Odisha, India", latitude=20.0, longitude=83.0)

    monkeypatch.setattr(service, "_geocode", far_geocode)
    monkeypatch.setattr(service, "_fetch_terrain", _stub_terrain)
    monkeypatch.setattr(service, "_overpass_fetch_polygon", lambda _poly: ([], None))

    result = service.analyze_route(RouteAnalysisRequest(origin="Alpha", destination="Beta", corridor_width_m=60))
    assert result.candidates[0].distance_km > 100


def test_gunupur_padmapur_has_verified_official_road_reference(monkeypatch):
    monkeypatch.setattr(service, "_geocode", _stub_geocode)
    monkeypatch.setattr(service, "_fetch_terrain", _stub_terrain)
    monkeypatch.setattr(service, "_overpass_fetch_polygon", lambda _poly: ([], None))

    result = service.analyze_route(RouteAnalysisRequest(origin="Gunupur", destination="Padmapur"))

    assert result.official_road_reference is not None
    assert result.official_road_reference.category == "MDR-61-A"
    assert result.official_road_reference.official_length_km == 22.869
    assert "Works Department" in result.official_road_reference.authority


def test_geocode_prefers_rayagada_town_over_rayagada_district_boundary():
    rows = [
        ({
            "display_name": "Rayagada district, Odisha, India",
            "class": "boundary",
            "type": "administrative",
            "addresstype": "state_district",
            "lat": "19.2500",
            "lon": "83.5000",
            "importance": 0.72,
            "address": {"state_district": "Rayagada", "state": "Odisha", "country": "India"},
            "namedetails": {"name": "Rayagada"},
            "osm_type": "relation",
            "osm_id": 1,
        }, 0),
        ({
            "display_name": "Rayagada, Rayagada, Odisha, India",
            "class": "place",
            "type": "town",
            "addresstype": "town",
            "lat": "19.1713",
            "lon": "83.4143",
            "importance": 0.55,
            "address": {"town": "Rayagada", "state_district": "Rayagada", "state": "Odisha", "country": "India"},
            "namedetails": {"name": "Rayagada"},
            "osm_type": "node",
            "osm_id": 2,
        }, 1),
    ]

    row = service._choose_geocode_row(rows, query="Rayagada", state="Odisha", district="Rayagada")

    assert row is not None
    assert row["type"] == "town"
    assert row["lat"] == "19.1713"
    assert row["lon"] == "83.4143"


def test_geocode_prefers_gunupur_town_over_same_name_locality():
    rows = [
        ({
            "display_name": "Gunupur, Rayagada, Odisha, India",
            "class": "place",
            "type": "locality",
            "addresstype": "locality",
            "lat": "19.1285",
            "lon": "83.7657",
            "importance": 0.80,
            "address": {"locality": "Gunupur", "state_district": "Rayagada", "state": "Odisha", "country": "India"},
            "namedetails": {"name": "Gunupur"},
            "osm_type": "node",
            "osm_id": 3,
        }, 0),
        ({
            "display_name": "Gunupur, Rayagada, Odisha, India",
            "class": "place",
            "type": "town",
            "addresstype": "town",
            "lat": "19.0714",
            "lon": "83.8149",
            "importance": 0.52,
            "address": {"town": "Gunupur", "state_district": "Rayagada", "state": "Odisha", "country": "India"},
            "namedetails": {"name": "Gunupur"},
            "osm_type": "node",
            "osm_id": 4,
        }, 1),
    ]

    row = service._choose_geocode_row(rows, query="Gunupur", state="Odisha", district="Rayagada")

    assert row is not None
    assert row["type"] == "town"
    assert row["lat"] == "19.0714"
    assert row["lon"] == "83.8149"


def test_geocode_keeps_district_scope_for_same_name_places():
    rows = [
        ({
            "display_name": "Gunupur, Kalahandi, Odisha, India",
            "class": "place", "type": "village", "addresstype": "village",
            "lat": "19.6100", "lon": "83.1160", "importance": 0.70,
            "address": {"village": "Gunupur", "state_district": "Kalahandi", "state": "Odisha"},
            "namedetails": {"name": "Gunupur"}, "osm_type": "node", "osm_id": 5,
        }, 0),
        ({
            "display_name": "Gunupur, Rayagada, Odisha, India",
            "class": "place", "type": "town", "addresstype": "town",
            "lat": "19.0714", "lon": "83.8149", "importance": 0.50,
            "address": {"town": "Gunupur", "state_district": "Rayagada", "state": "Odisha"},
            "namedetails": {"name": "Gunupur"}, "osm_type": "node", "osm_id": 6,
        }, 1),
    ]

    row = service._choose_geocode_row(rows, query="Gunupur", state="Odisha", district="Rayagada")
    assert row is not None
    assert "Rayagada" in row["display_name"]


def test_greenfield_geometry_starts_and_ends_at_resolved_locations(monkeypatch):
    def point_geocode(query: str, **_kwargs):
        if query.lower() == "gunupur":
            return RouteLocation(label="Gunupur town", latitude=19.0714, longitude=83.8149)
        return RouteLocation(label="Rayagada town", latitude=19.1713, longitude=83.4143)

    monkeypatch.setattr(service, "_geocode", point_geocode)
    monkeypatch.setattr(service, "_fetch_terrain", _stub_terrain)
    monkeypatch.setattr(service, "_overpass_fetch_polygon", lambda _poly: ([], None))

    result = service.analyze_route(RouteAnalysisRequest(origin="Gunupur", destination="Rayagada"))

    for candidate in result.candidates:
        assert candidate.geometry["coordinates"][0] == [83.8149, 19.0714]
        assert candidate.geometry["coordinates"][-1] == [83.4143, 19.1713]


def test_screening_score_is_not_perfect_and_missing_layers_reduce_confidence(monkeypatch):
    monkeypatch.setattr(service, "_geocode", _stub_geocode)
    monkeypatch.setattr(service, "_fetch_terrain", _stub_terrain)
    monkeypatch.setattr(service, "_overpass_fetch_polygon", lambda _poly: ([], "provider timeout"))

    result = service.analyze_route(RouteAnalysisRequest(origin="Gunupur", destination="Padmapur"))

    assert result.analysis_confidence == "LIMITED"
    assert result.mapped_data_status == "PARTIAL"
    assert all(candidate.feasibility_score is not None for candidate in result.candidates)
    assert max(candidate.feasibility_score for candidate in result.candidates) < 95
    assert min(candidate.route_burden_score for candidate in result.candidates) > 0


def test_calibrated_screening_score_has_prefeasibility_ceiling():
    terrain = TerrainSummary(
        available=True,
        source="test-srtm",
        sample_count=10,
        min_elevation_m=100,
        max_elevation_m=100,
        elevation_range_m=0,
        mean_abs_grade_percent=0,
        max_grade_percent=0,
    )
    burden = service._calibrated_screening_burden(
        0.0,
        service.RouteObstacleSummary(),
        terrain,
        obstacle_ok=True,
        terrain_ok=True,
        construction_type="ROAD",
    )
    assert burden == 5.0
    assert 100.0 - burden == 95.0
