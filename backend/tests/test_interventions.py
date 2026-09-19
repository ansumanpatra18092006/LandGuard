from datetime import date, timedelta


def _create_project(client, payload):
    response = client.post('/api/v1/projects', json=payload)
    assert response.status_code == 201


def test_readiness_endpoint(client, payload):
    _create_project(client, payload)
    response = client.get('/api/v1/projects/TEST01/readiness')
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body['readiness_score'] <= 100
    assert body['readiness_label'] in {'BLOCKED','CONSTRAINED','READY'}
    assert len(body['components']) == 4
    assert 'not an ML prediction' in body['methodology']


def test_intervention_lifecycle_and_events(client, payload):
    _create_project(client, payload)
    due = (date.today() + timedelta(days=7)).isoformat()
    created = client.post('/api/v1/projects/TEST01/interventions', json={
        'action':'Clear pending approval chain', 'assigned_to':'District Acquisition Cell',
        'due_date':due, 'priority':'HIGH', 'source':'RECOMMENDATION'
    })
    assert created.status_code == 201
    row = created.json()
    assert row['status'] == 'OPEN'
    assert row['events'][0]['event_type'] == 'CREATED'

    started = client.patch(f"/api/v1/projects/TEST01/interventions/{row['id']}", json={'status':'IN_PROGRESS'})
    assert started.status_code == 200
    assert started.json()['status'] == 'IN_PROGRESS'
    assert any(e['event_type'] == 'STATUS_CHANGED' for e in started.json()['events'])

    resolved = client.patch(f"/api/v1/projects/TEST01/interventions/{row['id']}", json={
        'status':'RESOLVED','resolution_note':'Approval cleared in review meeting.'
    })
    assert resolved.status_code == 200
    assert resolved.json()['status'] == 'RESOLVED'
    assert resolved.json()['resolved_at'] is not None
    assert any(e['event_type'] == 'RESOLVED' for e in resolved.json()['events'])


def test_intervention_summary_is_scoped(client, payload):
    _create_project(client, payload)
    due = (date.today() + timedelta(days=7)).isoformat()
    client.post('/api/v1/projects/TEST01/interventions', json={
        'action':'Review compensation processing','assigned_to':'District Acquisition Cell',
        'due_date':due,'priority':'MEDIUM','source':'OFFICER'
    })
    body = client.get('/api/v1/interventions/summary').json()
    assert body['open_count'] == 1
    assert body['resolved_count'] == 0
