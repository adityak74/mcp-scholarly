import pytest

from mcp_scholarly.google_scholar import GoogleScholar


@pytest.fixture(autouse=True)
def reset_proxy_state():
    """GoogleScholar._proxy_ready is process-global state; isolate tests from it."""
    original = GoogleScholar._proxy_ready
    GoogleScholar._proxy_ready = False
    yield
    GoogleScholar._proxy_ready = original
