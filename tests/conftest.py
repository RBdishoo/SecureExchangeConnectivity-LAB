"""Pytest fixtures for Week 2 authz tests."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

os.environ["JWT_SECRET"] = "changeme-lab-only-jwt-secret"
os.environ["JWT_EXPIRE_MINUTES"] = "30"
os.environ["ORDER_RATE_LIMIT"] = "5"
os.environ["ORDER_RATE_WINDOW_SECONDS"] = "60"
os.environ.pop("DATABASE_URL", None)

if str(SERVICES) not in sys.path:
    sys.path.insert(0, str(SERVICES))


def _load_main(service_dirname: str, module_name: str):
    path = SERVICES / service_dirname / "main.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def identity_module():
    # Reload-safe: always reset after load
    name = "secx_identity_main"
    if name in sys.modules:
        del sys.modules[name]
    mod = _load_main("identity", name)
    mod.reset_state_for_tests()
    return mod


@pytest.fixture()
def identity_client(identity_module):
    with TestClient(identity_module.app) as client:
        yield client


@pytest.fixture()
def matching_module():
    name = "secx_matching_main"
    if name in sys.modules:
        del sys.modules[name]
    mod = _load_main("matching-engine", name)
    mod.reset_state_for_tests()
    return mod


@pytest.fixture()
def matching_client(matching_module):
    with TestClient(matching_module.app) as client:
        yield client


class _ASGIDelegatingClient:
    """Sync httpx.Client stand-in that routes to in-process FastAPI apps."""

    def __init__(self, routes: dict[str, TestClient], timeout=None):
        self.routes = routes

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def _client_for(self, url: str) -> tuple[TestClient, str]:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host not in self.routes:
            raise RuntimeError(f"No ASGI route for host {host} ({url})")
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        return self.routes[host], path

    def _wrap(self, response) -> httpx.Response:
        request = httpx.Request("GET", "http://test")
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )

    def post(self, url, json=None, headers=None):
        client, path = self._client_for(url)
        return self._wrap(client.post(path, json=json, headers=headers or {}))

    def get(self, url, headers=None):
        client, path = self._client_for(url)
        return self._wrap(client.get(path, headers=headers or {}))

    def patch(self, url, json=None, headers=None):
        client, path = self._client_for(url)
        return self._wrap(client.patch(path, json=json, headers=headers or {}))


@pytest.fixture()
def gateway_client(monkeypatch, identity_module, matching_module):
    name = "secx_gateway_main"
    if name in sys.modules:
        del sys.modules[name]

    monkeypatch.setenv("IDENTITY_URL", "http://identity-test")
    monkeypatch.setenv("MATCHING_URL", "http://matching-test")
    monkeypatch.setenv("ORDER_RATE_LIMIT", "5")
    monkeypatch.setenv("ORDER_RATE_WINDOW_SECONDS", "60")

    gateway = _load_main("gateway", name)
    gateway.IDENTITY_URL = "http://identity-test"
    gateway.MATCHING_URL = "http://matching-test"
    gateway.ORDER_RATE_LIMIT = 5
    gateway.order_limiter.reset()

    identity_tc = TestClient(identity_module.app)
    matching_tc = TestClient(matching_module.app)
    routes = {"identity-test": identity_tc, "matching-test": matching_tc}

    def client_factory(*args, **kwargs):
        return _ASGIDelegatingClient(routes)

    monkeypatch.setattr(gateway.httpx, "Client", client_factory)

    with TestClient(gateway.app) as client:
        yield client

