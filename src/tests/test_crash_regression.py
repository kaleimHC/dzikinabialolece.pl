"""
Crash Regression Test Suite - Dziki na Białołęce

These tests pin two production crashes that were fixed and which previously had
NO coverage (both endpoints returned HTTP 500 in production while the test suite
stayed green):

  C1: analytics.views_admin.apply_preset
      Used to 500 because the preset/config code path referenced removed
      mcmc_* fields. After the fix:
        - an authenticated POST with a valid preset returns 200, and the
          returned `config` object must NOT carry mcmc_iterations / mcmc_chains;
        - an anonymous POST returns 401 (regression S2 - endpoint now requires
          Bearer/Session auth via IsBearerAuthenticated).

  C2: analytics.views_pub.combined_results / export_results_csv
      Public AllowAny GET endpoints. They used to 500 on valid alternate grid
      types and on bad query params. After the fix:
        - ?grid_type=grid_500 returns 200 (count 0 on an empty DB, not 500);
        - ?grid_type=bogus returns 400;
        - ?min_risk=abc returns 400.

Run:
    pytest src/tests/test_crash_regression.py -v
"""

import pytest

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient


# Routed paths (see src/dziki/urls.py + src/analytics/urls.py):
#   /api/analytics/config/apply-preset/   -> apply_preset
#   /api/analytics/results/combined/      -> combined_results
#   /api/analytics/results/export/        -> export_results_csv
APPLY_PRESET_URL = "/api/analytics/config/apply-preset/"
COMBINED_RESULTS_URL = "/api/analytics/results/combined/"
EXPORT_CSV_URL = "/api/analytics/results/export/"


# ---------------------------------------------------------------------------
# C1 - apply_preset must not 500 on removed mcmc_* fields, and is auth-gated
# ---------------------------------------------------------------------------

class TestApplyPresetCrashRegression(TestCase):
    """
    C1: POST /api/analytics/config/apply-preset/

    Previously crashed with HTTP 500 because the preset application path touched
    mcmc_iterations / mcmc_chains fields that no longer exist on the model.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="preset-tester", password="x"
        )

    def test_authenticated_valid_preset_returns_200(self):
        """C1: authenticated POST with a valid preset must return 200 (not 500)."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            APPLY_PRESET_URL,
            {"preset": "quick_preview", "activate": True},
            format="json",
        )
        assert response.status_code == 200, (
            f"apply_preset returned {response.status_code} for a valid preset "
            f"(C1 regression - must be 200): {response.content!r}"
        )

    def test_response_config_has_no_mcmc_fields(self):
        """C1: the returned config must NOT expose mcmc_iterations / mcmc_chains."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            APPLY_PRESET_URL,
            {"preset": "quick_preview", "activate": True},
            format="json",
        )
        assert response.status_code == 200
        config = response.json().get("config", {})
        assert "mcmc_iterations" not in config, (
            f"config leaked removed field mcmc_iterations: {config}"
        )
        assert "mcmc_chains" not in config, (
            f"config leaked removed field mcmc_chains: {config}"
        )

    def test_anonymous_post_is_rejected(self):
        """S2: anonymous POST must be rejected (auth required, IsBearerAuthenticated).

        DRF returns 401 here because TokenAuthentication is the primary
        authenticator (it sets a WWW-Authenticate header). The security contract
        is "anon cannot apply presets" - assert rejection (401 or 403), not a
        specific code, so the test pins the contract without being brittle.
        """
        response = self.client.post(
            APPLY_PRESET_URL,
            {"preset": "quick_preview"},
            format="json",
        )
        assert response.status_code in (401, 403), (
            f"apply_preset must require auth - anon got {response.status_code}, "
            f"expected 401 or 403"
        )


# ---------------------------------------------------------------------------
# C2 - combined_results / export_results_csv must not 500 on valid/bad params
# ---------------------------------------------------------------------------

class TestCombinedResultsCrashRegression(TestCase):
    """
    C2: GET /api/analytics/results/combined/

    Public AllowAny endpoint. Must handle alternate grid types and reject bad
    query parameters with 400 instead of crashing with 500.
    """

    def setUp(self):
        self.client = APIClient()

    @pytest.mark.django_db
    def test_grid_500_returns_200_on_empty_db(self):
        """C2: ?grid_type=grid_500 must return 200 (count 0 on empty DB, not 500)."""
        response = self.client.get(COMBINED_RESULTS_URL, {"grid_type": "grid_500"})
        assert response.status_code == 200, (
            f"combined_results?grid_type=grid_500 returned {response.status_code} "
            f"(C2 regression - must be 200): {response.content!r}"
        )

    @pytest.mark.django_db
    def test_bogus_grid_type_returns_400(self):
        """C2: an unknown grid_type must be rejected with 400 (allowlist)."""
        response = self.client.get(COMBINED_RESULTS_URL, {"grid_type": "bogus"})
        assert response.status_code == 400, (
            f"combined_results?grid_type=bogus returned {response.status_code}, "
            f"expected 400"
        )

    @pytest.mark.django_db
    def test_non_numeric_min_risk_returns_400(self):
        """C2: a non-numeric min_risk must be rejected with 400, not 500."""
        response = self.client.get(
            COMBINED_RESULTS_URL, {"grid_type": "grid_500", "min_risk": "abc"}
        )
        assert response.status_code == 400, (
            f"combined_results?min_risk=abc returned {response.status_code}, "
            f"expected 400"
        )


class TestExportResultsCsvCrashRegression(TestCase):
    """
    C2: GET /api/analytics/results/export/

    Public AllowAny CSV export. Must handle alternate grid types and reject
    unknown ones with 400 instead of crashing with 500.
    """

    def setUp(self):
        self.client = APIClient()

    @pytest.mark.django_db
    def test_grid_500_returns_200_on_empty_db(self):
        """C2: ?grid_type=grid_500 export must return 200 (not 500) on empty DB."""
        response = self.client.get(EXPORT_CSV_URL, {"grid_type": "grid_500"})
        assert response.status_code == 200, (
            f"export_results_csv?grid_type=grid_500 returned {response.status_code} "
            f"(C2 regression - must be 200): {response.content!r}"
        )

    @pytest.mark.django_db
    def test_bogus_grid_type_returns_400(self):
        """C2: an unknown grid_type must be rejected with 400 (allowlist)."""
        response = self.client.get(EXPORT_CSV_URL, {"grid_type": "bogus"})
        assert response.status_code == 400, (
            f"export_results_csv?grid_type=bogus returned {response.status_code}, "
            f"expected 400"
        )
