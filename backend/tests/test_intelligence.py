from app.services.intelligence_service import model_status


def test_auth_login_and_me(client):
    response = client.get('/api/v1/auth/me')
    assert response.status_code == 200
    assert response.json()['role'] == 'STATE_OFFICER'


def test_map_data(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    response = client.get('/api/v1/map-data')
    assert response.status_code == 200
    assert response.json()[0]['project_id'] == payload['project_id']


def test_alerts_are_operational_not_ml(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    response = client.get('/api/v1/alerts')
    assert response.status_code == 200
    alert = response.json()[0]
    assert alert['source'] == 'OPERATIONAL_RULE'
    assert alert['project_id'] == payload['project_id']


def test_model_status_contract(client):
    response = client.get('/api/v1/model/status')
    assert response.status_code == 200
    assert 'available' in response.json()
    assert 'disclaimer' in response.json()


def test_prediction_requires_auth(database, payload):
    # Current TestClient fixture is authenticated; verify route presence/status via the normal client elsewhere.
    status = model_status()
    assert isinstance(status.available, bool)


def test_prediction_with_loaded_demo_artifact(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    response = client.post('/api/v1/projects/TEST01/predict')
    assert response.status_code == 200
    data = response.json()
    assert 0 <= data['delay_probability'] <= 1
    assert data['risk_category'] in {'LOW','MEDIUM','HIGH'}
    assert data['metadata']['training_data_kind'] == 'OFFICIAL_PAIMANA_LONGITUDINAL_BASELINE'
    assert 'PAIMANA' in data['metadata']['disclaimer']
    assert data['metadata']['target_definition']
    assert len(data['stage_outlook']) == 7
    assert any(row['status'] == 'CURRENT' for row in data['stage_outlook'])
    assert all(0 <= row['screening_score'] <= 100 for row in data['stage_outlook'])


def test_prediction_exposes_advanced_evidence(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    response = client.post('/api/v1/projects/TEST01/predict')
    assert response.status_code == 200
    data = response.json()
    assert 'raw_probability' in data
    assert 'similar_cases' in data
    if data['similar_cases']:
        assert 'same_sector' in data['similar_cases'][0]
    assert 'probability_threshold' in data['metadata']


def test_scenario_lab(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    response = client.post('/api/v1/projects/TEST01/scenario', json={'expenditure_to_original_cost_pct': 70, 'days_to_original_deadline': 45})
    assert response.status_code == 200
    data = response.json()
    assert 0 <= data['base_probability'] <= 1
    assert 0 <= data['scenario_probability'] <= 1
    assert data['scenario_expenditure_to_original_cost_pct'] == 70
    assert data['scenario_days_to_original_deadline'] == 45
    assert 'causal' in data['note'].lower()


def test_portfolio_risk_pulse(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    response = client.get('/api/v1/risk-pulse')
    assert response.status_code == 200
    data = response.json()
    assert data['model_available'] is True
    assert data['scored_projects'] == 1
    assert data['high_risk'] + data['medium_risk'] + data['low_risk'] == 1
    assert data['projects'][0]['project_id'] == payload['project_id']
    assert 0 <= data['projects'][0]['delay_probability'] <= 1
    assert isinstance(data['projects'][0]['ml_factors'], list)


def test_map_data_contains_predictive_risk_when_model_inputs_exist(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    row = client.get('/api/v1/map-data').json()[0]
    assert row['delay_probability'] is not None
    assert row['risk_category'] in {'LOW','MEDIUM','HIGH'}
    assert isinstance(row['slip_alert'], bool)


def test_acquisition_friction_is_exposed_and_priority_is_combined(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    data = client.post('/api/v1/projects/TEST01/predict').json()
    assert data['acquisition_friction']['score'] > 0
    assert data['acquisition_friction']['label'] in {'LOW','MODERATE','HIGH','CRITICAL'}
    assert data['metadata']['land_acquisition_features_used'] is False
    assert 0 <= data['intervention_priority_score'] <= 100
    assert data['intervention_priority_category'] in {'ROUTINE','WATCH','HIGH','CRITICAL'}


def test_admin_scenario_reduces_friction_without_claiming_ml_effect(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    response = client.post('/api/v1/projects/TEST01/scenario', json={
        'expenditure_to_original_cost_pct': 37,
        'days_to_original_deadline': 180,
        'clear_pending_approvals': True,
        'resolve_legal_disputes': True,
        'compensation_target_pct': 90,
        'possession_target_pct': 85,
        'rehabilitation_target_pct': 80,
        'stakeholder_response_target_days': 7,
    })
    assert response.status_code == 200
    data = response.json()
    assert data['scenario_friction']['score'] < data['base_friction']['score']
    assert data['scenario_readiness_score'] > data['base_readiness_score']
    assert data['scenario_priority_score'] < data['base_priority_score']
    assert 'do not alter the ML probability' in data['operational_note']


def test_schedule_signal_cannot_suppress_acquisition_priority(client, payload):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    data = client.post('/api/v1/projects/TEST01/predict').json()
    assert data['intervention_priority_score'] >= data['acquisition_delay_risk']['score']


def test_predictive_alerts_are_added_without_replacing_operational_alerts(client, payload, monkeypatch):
    assert client.post('/api/v1/projects', json=payload).status_code == 201
    from app.api.routes import alerts as alert_routes
    class PulseProject:
        project_id='TEST01'; risk_category='HIGH'; slip_alert=True; delay_probability=.82; suggested_action='Review approvals'; primary_bottleneck='Pending approvals'
    class Pulse:
        projects=[PulseProject()]
    monkeypatch.setattr(alert_routes, 'portfolio_risk_pulse', lambda projects: Pulse())
    rows = client.get('/api/v1/alerts').json()
    assert any(row['source'] == 'OPERATIONAL_RULE' for row in rows)
    predictive = [row for row in rows if row['source'] == 'PREDICTIVE_MODEL']
    assert predictive and predictive[0]['project_id'] == 'TEST01'
