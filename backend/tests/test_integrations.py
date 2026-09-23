def test_bulk_integration_upserts_projects_and_records_source(client, payload):
    request = {"source_system": "Gov-LA-MIS", "projects": [payload]}
    created = client.post('/api/v1/integrations/projects/bulk-upsert', json=request)
    assert created.status_code == 200
    assert created.json()['created'] == 1
    project = client.get('/api/v1/projects/TEST01').json()
    assert project['data_source'] == 'INTEGRATED'

    request['projects'][0]['compensation_completion_pct'] = 77
    updated = client.post('/api/v1/integrations/projects/bulk-upsert', json=request)
    assert updated.status_code == 200
    assert updated.json()['updated'] == 1
    assert client.get('/api/v1/projects/TEST01').json()['compensation_completion_pct'] == 77
    history = client.get('/api/v1/projects/TEST01/history').json()
    assert any(row['source'] == 'INTEGRATION:Gov-LA-MIS' for row in history['events'])


def test_integration_capabilities_are_exposed(client):
    response = client.get('/api/v1/integrations/capabilities')
    assert response.status_code == 200
    data = response.json()
    assert data['project_bulk_upsert'] is True
    assert data['cadastral_geojson_import'].endswith('/gis/ownership/import')
