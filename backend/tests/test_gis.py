from types import SimpleNamespace

def seed_gis(client, payload):
    rows = [
        payload,
        {**payload, "project_id": "TEST02", "district": "Nashik", "latitude": 19.9975, "longitude": 73.7898,
         "acquisition_stage": "POSSESSION", "project_type": "RAILWAY"},
        {**payload, "project_id": "TEST03", "district": "Nagpur", "latitude": 21.1458, "longitude": 79.0882,
         "acquisition_stage": "COMPENSATION"},
    ]
    for row in rows:
        assert client.post("/api/v1/projects", json=row).status_code == 201


def test_map_data_contains_gis_fields(client, payload):
    seed_gis(client, payload)
    rows = client.get("/api/v1/map-data").json()
    assert len(rows) == 3
    assert {"latitude", "longitude", "project_type", "rehabilitation_completion_pct", "distance_km"} <= rows[0].keys()


def test_map_filters_and_bounds(client, payload):
    seed_gis(client, payload)
    assert len(client.get("/api/v1/map-data?district=Pune").json()) == 1
    assert len(client.get("/api/v1/map-data?stage=POSSESSION").json()) == 1
    rows = client.get("/api/v1/map-data?min_lat=18&max_lat=20.5&min_lon=73&max_lon=75").json()
    assert {row["project_id"] for row in rows} == {"TEST01", "TEST02"}
    assert client.get("/api/v1/map-data?min_lat=18").status_code == 422


def test_nearby_search(client, payload):
    seed_gis(client, payload)
    rows = client.get("/api/v1/map-data?near_lat=18.52&near_lon=73.85&radius_km=30").json()
    assert [row["project_id"] for row in rows] == ["TEST01"]
    assert rows[0]["distance_km"] == 0
    assert client.get("/api/v1/map-data?near_lat=18.52&near_lon=73.85").status_code == 422


def test_ownership_import_parcels_and_summary(client, payload):
    assert client.post("/api/v1/projects", json=payload).status_code == 201
    body = {
        "project_id": "TEST01",
        "state": "Maharashtra",
        "district": "Pune",
        "source_name": "AUTHORIZED_TEST_IMPORT",
        "ror_verified": True,
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[73.84,18.51],[73.85,18.51],[73.85,18.52],[73.84,18.52],[73.84,18.51]]]},
                "properties": {"parcel_id": "PLOT-1", "plot_no": "101", "khata_no": "20", "ownership_type": "GOVERNMENT", "area_acres": 2.0},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[73.85,18.51],[73.86,18.51],[73.86,18.52],[73.85,18.52],[73.85,18.51]]]},
                "properties": {"parcel_id": "PLOT-2", "plot_no": "102", "khata_no": "21", "ownership_type": "PRIVATE", "area_acres": 3.0},
            },
        ],
    }
    imported = client.post("/api/v1/gis/ownership/import", json=body)
    assert imported.status_code == 200
    assert imported.json()["imported"] == 2

    parcels = client.get("/api/v1/gis/ownership/parcels?project_id=TEST01")
    assert parcels.status_code == 200
    assert {row["ownership_type"] for row in parcels.json()} == {"GOVERNMENT", "PRIVATE"}

    summary = client.get("/api/v1/gis/ownership/summary/TEST01")
    assert summary.status_code == 200
    data = summary.json()
    assert data["total_parcels"] == 2
    assert data["verified_parcels"] == 2
    assert data["total_area_acres"] == 5.0
    assert {row["ownership_type"]: row["area_pct"] for row in data["breakdown"]} == {"GOVERNMENT": 40.0, "PRIVATE": 60.0}


def test_bhuvan_config_explains_ownership_boundary(client):
    response = client.get("/api/v1/gis/bhuvan/config")
    assert response.status_code == 200
    assert response.json()["usage"] == "THEMATIC_CONTEXT_ONLY"



def test_ownership_summary_is_unavailable_without_real_parcels(client, payload):
    assert client.post("/api/v1/projects", json=payload).status_code == 201
    response = client.get("/api/v1/gis/ownership/summary/TEST01")
    assert response.status_code == 200
    data = response.json()
    assert data["data_status"] == "UNAVAILABLE"
    assert data["total_parcels"] == 0
    assert data["breakdown"] == []
    assert "does not fabricate" in data["disclaimer"]


def test_cadastral_import_computes_area_and_never_infers_missing_ownership(client, payload):
    assert client.post("/api/v1/projects", json=payload).status_code == 201
    body = {
        "project_id": "TEST01",
        "state": "Maharashtra",
        "district": "Pune",
        "source_name": "AUTHORISED_CADASTRAL_EXPORT",
        "ror_verified": False,
        "replace_project_dataset": True,
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[73.84,18.51],[73.841,18.51],[73.841,18.511],[73.84,18.511],[73.84,18.51]]]},
            "properties": {"plot_no": "501", "khata_no": "88"},
        }],
    }
    response = client.post("/api/v1/gis/ownership/import", json=body)
    assert response.status_code == 200
    assert response.json()["data_status"] == "IMPORTED_DATASET"
    parcels = client.get("/api/v1/gis/ownership/parcels?project_id=TEST01").json()
    assert len(parcels) == 1
    assert parcels[0]["ownership_type"] == "UNKNOWN"
    assert parcels[0]["area_acres"] > 0


def test_synthetic_cadastral_source_is_rejected(client, payload):
    assert client.post("/api/v1/projects", json=payload).status_code == 201
    body = {
        "project_id": "TEST01",
        "state": "Maharashtra",
        "district": "Pune",
        "source_name": "ILLUSTRATIVE_SIH_DEMO",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[73.84,18.51],[73.85,18.51],[73.85,18.52],[73.84,18.52],[73.84,18.51]]]},
            "properties": {"ownership_type": "PRIVATE"},
        }],
    }
    response = client.post("/api/v1/gis/ownership/import", json=body)
    assert response.status_code == 422


def test_land_records_config_points_to_official_reference_workflow(client):
    response = client.get("/api/v1/gis/land-records/config")
    assert response.status_code == 200
    data = response.json()
    assert data["geometry_policy"] == "IMPORT_AUTHORISED_CADASTRAL_EXPORT"
    assert data["ownership_policy"] == "SOURCE_ATTRIBUTE_ONLY"
    assert "bhunakshaodisha.nic.in" in data["odisha_bhunaksha_url"]
    assert "bhulekh.ori.nic.in" in data["odisha_bhulekh_url"]


def test_physical_context_maps_buildings_and_places(client, payload, monkeypatch):
    assert client.post("/api/v1/projects", json=payload).status_code == 201
    rows = (
        {
            "type": "way", "id": 101,
            "tags": {"building": "house", "name": "Mapped House"},
            "geometry": [
                {"lat": 18.5200, "lon": 73.8500}, {"lat": 18.5201, "lon": 73.8500},
                {"lat": 18.5201, "lon": 73.8501}, {"lat": 18.5200, "lon": 73.8501},
                {"lat": 18.5200, "lon": 73.8500},
            ],
        },
        {"type": "node", "id": 102, "lat": 18.5202, "lon": 73.8502, "tags": {"shop": "grocery", "name": "Mapped Shop"}},
        {"type": "node", "id": 103, "lat": 18.5203, "lon": 73.8503, "tags": {"amenity": "school", "name": "Mapped School"}},
    )
    monkeypatch.setattr("app.api.routes.gis._overpass_fetch", lambda _query: rows)
    monkeypatch.setattr("app.api.routes.gis.fetch_overture_features", lambda *_args, **_kwargs: SimpleNamespace(available=False, features=[], error="disabled in unit test"))
    response = client.get("/api/v1/gis/physical-context/TEST01?radius_m=500")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["mapped_structures"] == 1
    assert data["summary"]["shops_businesses"] == 1
    assert data["summary"]["schools"] == 1
    assert data["summary"]["source_name"] == "OpenStreetMap"
    assert {row["category"] for row in data["features"]} >= {"BUILDING", "SHOP", "PUBLIC_FACILITY"}


def test_physical_impact_requires_local_polygon(client, payload, monkeypatch):
    assert client.post("/api/v1/projects", json=payload).status_code == 201
    monkeypatch.setattr("app.api.routes.gis._overpass_fetch", lambda _query: tuple())
    monkeypatch.setattr("app.api.routes.gis.fetch_overture_features", lambda *_args, **_kwargs: SimpleNamespace(available=False, features=[], error=None))
    response = client.post("/api/v1/gis/physical-impact/TEST01", json={"points": [[18.519, 73.849], [18.521, 73.849], [18.521, 73.851]]})
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["mode"] == "DRAWN_IMPACT_AREA"
    assert summary["source_name"] == "OpenStreetMap"
    assert summary["source_status"] == "NO_MAPPED_FEATURES_IN_AREA"
    assert summary["analysis_area_hectares"] > 0
    assert "does not prove" in summary["result_message"]
    far = client.post("/api/v1/gis/physical-impact/TEST01", json={"points": [[19.0, 75.0], [19.1, 75.0], [19.0, 75.1]]})
    assert far.status_code == 422



def test_overture_fallback_supplies_real_building_footprints(client, payload, monkeypatch):
    assert client.post("/api/v1/projects", json=payload).status_code == 201
    monkeypatch.setattr("app.api.routes.gis._overpass_fetch", lambda _query: tuple())
    overture_rows = [
        {
            "feature_id": "overture-building-1",
            "category": "BUILDING",
            "subtype": "house",
            "name": None,
            "latitude": 18.5201,
            "longitude": 73.8501,
            "geometry": {"type": "Polygon", "coordinates": [[[73.8500,18.5200],[73.8502,18.5200],[73.8502,18.5202],[73.8500,18.5202],[73.8500,18.5200]]]},
            "tags": {"overture_class": "house", "source_dataset": "Microsoft ML Buildings"},
            "use_class": "RESIDENTIAL",
            "classification_basis": "Overture building class=house",
            "source_name": "Overture Maps",
        },
        {
            "feature_id": "overture-place-2",
            "category": "SHOP",
            "subtype": "grocery_store",
            "name": "Real Grocery",
            "latitude": 18.52015,
            "longitude": 73.85015,
            "geometry": {"type": "Point", "coordinates": [73.85015,18.52015]},
            "tags": {"overture_category": "grocery_store"},
            "use_class": "COMMERCIAL",
            "classification_basis": "Overture place category=grocery_store",
            "source_name": "Overture Maps",
        },
    ]
    monkeypatch.setattr(
        "app.api.routes.gis.fetch_overture_features",
        lambda *_args, **_kwargs: SimpleNamespace(available=True, features=overture_rows, error=None),
    )
    response = client.get("/api/v1/gis/physical-context/TEST01?radius_m=500")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["mapped_structures"] == 1
    assert data["summary"]["residential_mapped"] == 1
    assert data["summary"]["shops_businesses"] == 1
    assert data["summary"]["source_name"] == "Overture Maps"
    assert data["summary"]["source_status"] == "LIVE_OVERTURE_MAPS"
    assert {row["source_name"] for row in data["features"]} == {"Overture Maps"}
