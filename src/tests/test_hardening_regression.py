"""
DB-integrity and input-validation regression tests.

Covers:
- ResearchConfig write validation (active_predictors allow-list gap, enums, k-range)
- DB-level CHECK constraints reject serializer-bypassing writes (defense-in-depth)
- Sighting admin-only mutation guard (anon PATCH/DELETE rejected)
- risk_heatmap read-fuzz: malformed params -> 400 (were 500 / silent 200)

DB-constraint tests use bulk_create() to bypass full_clean() on purpose: the
point is that the DATABASE itself (not just the serializer/clean()) rejects any
row no pre-programmed button could emit.
"""
import pytest
from django.contrib.gis.geos import Point
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from sightings.models import Sighting
from analytics.models_research import ResearchConfig


@pytest.fixture
def api():
    return APIClient()


def _warsaw_point():
    return Point(21.0, 52.2, srid=4326)


# --------------------------------------------------------------------------- #
# App-layer: ResearchConfig create validation (POST /api/research/configs/)    #
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_config_rejects_unknown_predictor(api):
    r = api.post("/api/research/configs/", {
        "name": "h_unknown_pred", "geometry_type": "grid_500",
        "active_predictors": ["DROP TABLE sightings"],
    }, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_config_rejects_non_list_predictors(api):
    r = api.post("/api/research/configs/", {
        "name": "h_str_pred", "geometry_type": "grid_500",
        "active_predictors": "forests",
    }, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_config_rejects_nonstring_predictor_element(api):
    r = api.post("/api/research/configs/", {
        "name": "h_int_pred", "geometry_type": "grid_500",
        "active_predictors": [123],
    }, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_config_rejects_bad_geometry_enum(api):
    r = api.post("/api/research/configs/", {
        "name": "h_geo", "geometry_type": "bogus",
    }, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_config_rejects_inverted_k_range(api):
    r = api.post("/api/research/configs/", {
        "name": "h_krange", "geometry_type": "grid_500",
        "k_range_min": 50, "k_range_max": 2,
    }, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_config_rejects_non_integer_k_range(api):
    r = api.post("/api/research/configs/", {
        "name": "h_krange_str", "geometry_type": "grid_500",
        "k_range_min": "abc", "k_range_max": 30,
    }, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_config_accepts_valid_and_dedups_predictors(api):
    r = api.post("/api/research/configs/", {
        "name": "h_valid", "geometry_type": "grid_500", "y_formula": "log_pop",
        "active_predictors": ["forests", "forests", "water"],
    }, format="json")
    assert r.status_code == 201
    cfg = ResearchConfig.objects.get(name="h_valid")
    assert cfg.active_predictors == ["forests", "water"]  # de-duplicated, order kept


# --------------------------------------------------------------------------- #
# DB-layer defense-in-depth: CHECK constraints reject ORM-bypass writes        #
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_db_rejects_bad_sighting_status():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Sighting.objects.bulk_create([Sighting(
                location=_warsaw_point(), observed_at=timezone.now(),
                boar_count="1", sighting_type="encounter", status="garbage",
            )])


@pytest.mark.django_db
def test_db_rejects_bad_boar_count():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Sighting.objects.bulk_create([Sighting(
                location=_warsaw_point(), observed_at=timezone.now(),
                boar_count="9999", sighting_type="encounter", status="verified",
            )])


@pytest.mark.django_db
def test_db_rejects_bad_sighting_type():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Sighting.objects.bulk_create([Sighting(
                location=_warsaw_point(), observed_at=timezone.now(),
                boar_count="1", sighting_type="lol", status="verified",
            )])


@pytest.mark.django_db
def test_db_rejects_config_out_of_range_alpha():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ResearchConfig.objects.bulk_create([ResearchConfig(name="h_db_alpha", alpha=9.0)])


@pytest.mark.django_db
def test_db_rejects_config_bad_w_method():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ResearchConfig.objects.bulk_create([ResearchConfig(name="h_db_w", w_method="evil")])


# --------------------------------------------------------------------------- #
# Authz: Sighting admin-only mutation guard (sightings/views.py get_permissions)#
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_anon_cannot_delete_sighting(api):
    s = Sighting.objects.create(
        location=_warsaw_point(), observed_at=timezone.now(),
        boar_count="1", sighting_type="encounter", status="verified",
    )
    r = api.delete(f"/api/sightings/{s.pk}/")
    assert r.status_code in (401, 403)


@pytest.mark.django_db
def test_anon_cannot_patch_sighting(api):
    s = Sighting.objects.create(
        location=_warsaw_point(), observed_at=timezone.now(),
        boar_count="1", sighting_type="encounter", status="verified",
    )
    r = api.patch(f"/api/sightings/{s.pk}/", {"boar_count": "10+"}, format="json")
    assert r.status_code in (401, 403)


# --------------------------------------------------------------------------- #
# Read-fuzz: risk_heatmap malformed params -> clean 400                        #
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_risk_heatmap_bad_date_is_400(api):
    r = api.get("/api/analytics/risk/?date=garbage")
    assert r.status_code == 400


@pytest.mark.django_db
def test_risk_heatmap_bad_model_is_400(api):
    r = api.get("/api/analytics/risk/?model=injection")
    assert r.status_code == 400


@pytest.mark.django_db
def test_risk_heatmap_valid_is_200(api):
    r = api.get("/api/analytics/risk/")
    assert r.status_code == 200
