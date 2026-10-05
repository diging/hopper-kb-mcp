"""require_api_key, exercised through a real protected route with real signed JWTs."""

import pytest
from fastmcp.server.auth.providers.jwt import RSAKeyPair

LIST_URL = "/docs/list"


def get(client, authorization=None):
    headers = {"Authorization": authorization} if authorization is not None else {}
    return client.get(LIST_URL, headers=headers)


def test_valid_token_is_accepted(client, make_token):
    resp = get(client, f"Bearer {make_token()}")
    assert resp.status_code == 200


@pytest.mark.parametrize("authorization", [None, "", "Bearer ", "Bearer not-a-jwt", "Basic dXNlcjpwYXNz"])
def test_missing_or_malformed_token_is_forbidden(client, authorization):
    resp = get(client, authorization)
    assert resp.status_code == 403
    assert resp.json() == {"error": "Forbidden"}


def test_expired_token_is_forbidden(client, make_token):
    assert get(client, f"Bearer {make_token(expires_in_seconds=-60)}").status_code == 403


def test_token_from_wrong_issuer_is_forbidden(client, make_token):
    assert get(client, f"Bearer {make_token(issuer='https://evil.test')}").status_code == 403


def test_token_signed_with_another_key_is_forbidden(client):
    forged = RSAKeyPair.generate().create_token(issuer="https://hopper-kb.test")
    assert get(client, f"Bearer {forged}").status_code == 403


@pytest.mark.parametrize("method, path", [
    ("GET", "/docs/list"),
    ("POST", "/docs/website/add?url=https://example.com"),
    ("POST", "/docs/pdf/add"),
    ("POST", "/docs/pdf/update"),
    ("POST", "/docs/html/add"),
    ("GET", "/docs/1/file"),
    ("DELETE", "/docs/1"),
])
def test_every_documents_route_requires_a_token(client, method, path):
    assert client.request(method, path).status_code == 403


def test_mcp_endpoint_rejects_unauthenticated_requests(client):
    resp = client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Accept": "application/json, text/event-stream"},
    )
    assert resp.status_code == 401
