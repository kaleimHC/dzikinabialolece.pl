"""
Smoke tests - siatka bezpieczeństwa przed refaktorem.

Uruchom: pytest tests/test_smoke.py -v
Wymaga:  pip install -r requirements-test.txt
         Działające kontenery: db, redis-broker, redis-cache

Testy celowo proste - wykrywają regresję w:
  - views.py przy refaktorze endpointów
  - sightingsStore.js przy refaktorze Zustand store
"""
import pytest
from django.test import Client
from django.db import connection


# TEST 1 - Health endpoint + PostGIS
# Wykrywa: zepsute połączenie z DB, brakujące rozszerzenie PostGIS

@pytest.mark.django_db
def test_health_endpoint_zwraca_strukture():
    """GET /api/health/ musi zwrócić JSON z kluczem 'checks'."""
    client = Client()
    r = client.get('/api/health/')
    assert r.status_code in [200, 503], f"Nieoczekiwany status: {r.status_code}"
    data = r.json()
    assert 'checks' in data, "Brak klucza 'checks' w odpowiedzi health"
    assert 'postgis' in data['checks'], "Brak sprawdzenia PostGIS w health"


@pytest.mark.django_db
def test_postgis_dostepny():
    """PostGIS musi być zainstalowane i dostępne."""
    with connection.cursor() as c:
        c.execute("SELECT PostGIS_Version()")
        version = c.fetchone()[0]
    assert version is not None
    assert len(version) > 0, "PostGIS_Version() zwróciło pusty string"


# TEST 2 - Grid endpoint zwraca poprawny GeoJSON
# Wykrywa: regresję w views.py po refaktorze grid_cells()

@pytest.mark.django_db
def test_grid_endpoint_zwraca_geojson():
    """GET /api/analytics/grid/ musi zwrócić FeatureCollection."""
    client = Client()
    r = client.get('/api/analytics/grid/')
    assert r.status_code == 200, f"Grid endpoint zwrócił {r.status_code}"
    data = r.json()
    assert data.get('type') == 'FeatureCollection', \
        f"Oczekiwano FeatureCollection, dostano: {data.get('type')}"
    assert 'features' in data, "Brak klucza 'features' w GeoJSON"


@pytest.mark.django_db
def test_grid_features_maja_risk():
    """Każda komórka gridu musi mieć właściwość 'risk'."""
    client = Client()
    r = client.get('/api/analytics/grid/')
    data = r.json()
    features = data.get('features', [])
    if not features:
        pytest.skip("Brak danych w gridzie - uruchom init_grids najpierw")
    sample = features[:5]
    for f in sample:
        assert 'risk' in f.get('properties', {}), \
            f"Feature bez właściwości 'risk': {f.get('properties', {}).keys()}"
