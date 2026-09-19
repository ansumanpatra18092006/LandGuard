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
