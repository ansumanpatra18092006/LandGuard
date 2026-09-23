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
    # Project creation now auto-generates operational workflow actions in addition to the manual action.
    assert body['open_count'] >= 1
    assert body['resolved_count'] == 0


def test_automation_creates_deduplicated_actions(client, payload):
    _create_project(client, payload)
    rows = client.get('/api/v1/projects/TEST01/interventions').json()
    automated = [row for row in rows if row['source'] == 'AUTOMATION']
    assert automated
    actions = {row['action'] for row in automated}
    assert 'Legal review required' in actions
    assert 'Approval clearance required' in actions
    assert 'Possession and handover review' in actions

    rerun = client.post('/api/v1/projects/TEST01/automation/evaluate')
    assert rerun.status_code == 200
    assert rerun.json()['created'] == 0
    rows_after = client.get('/api/v1/projects/TEST01/interventions').json()
    assert len([row for row in rows_after if row['source'] == 'AUTOMATION']) == len(automated)


def test_automation_condition_clear_requires_officer_resolution(client, payload):
    _create_project(client, payload)
    rows = client.get('/api/v1/projects/TEST01/interventions').json()
    legal = next(row for row in rows if row['action'] == 'Legal review required')

    changed = dict(payload)
    changed['legal_disputes'] = 0
    updated = client.put('/api/v1/projects/TEST01', json=changed)
    assert updated.status_code == 200

    rows = client.get('/api/v1/projects/TEST01/interventions').json()
    legal = next(row for row in rows if row['id'] == legal['id'])
    assert legal['status'] != 'RESOLVED'
    assert any(event['event_type'] == 'CONDITION_CLEARED' for event in legal['events'])
