import pytest
from fastapi.routing import APIRoute

from loraflexsim.launcher import web_api


@pytest.mark.xfail(reason="Endpoint de statut REST non implémenté", strict=True)
def test_rest_api_exposes_status_endpoint():
    routes = {
        route.path
        for route in web_api.app.routes
        if isinstance(route, APIRoute)
    }
    assert "/simulations/status" in routes
