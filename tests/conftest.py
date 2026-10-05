"""Shared test setup.

The app connects to Postgres and loads the embedding model at import time,
so the environment is prepared here, before any app module is imported:
- POSTGRES_DB is pointed at a dedicated ``*_test`` database (created if missing)
- fastembed.TextEmbedding is swapped for a fast deterministic fake; tests marked
  ``functional`` opt back into the real model via the ``real_embeddings`` fixture
"""

import os

import fastembed
import psycopg
import pytest
from psycopg import sql

from tests.fakes import FakeTextEmbedding

TEST_DB = os.environ.get("TEST_POSTGRES_DB", "knowledge_base_test")
if not TEST_DB.endswith("_test"):
    raise RuntimeError(f"Refusing to run tests against non-test database {TEST_DB!r}")
os.environ["POSTGRES_DB"] = TEST_DB


def _ensure_test_database():
    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname="postgres",
        autocommit=True,
    ) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)
        ).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB)))


_ensure_test_database()

RealTextEmbedding = fastembed.TextEmbedding
fastembed.TextEmbedding = FakeTextEmbedding

# app imports must come after the setup above
import dbconnect  # noqa: E402
import decorators  # noqa: E402
import documents  # noqa: E402
import searchdocs  # noqa: E402
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair  # noqa: E402
from sqlalchemy import text  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

ISSUER = "https://hopper-kb.test"


@pytest.fixture(autouse=True)
def clean_database():
    assert dbconnect.engine.url.database == TEST_DB
    with dbconnect.engine.begin() as conn:
        conn.execute(text("TRUNCATE chunks, documents RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Keep uploaded files out of the real ./data directory."""
    path = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(path))
    return path


@pytest.fixture(scope="session")
def rsa_key_pair():
    return RSAKeyPair.generate()


@pytest.fixture
def auth_verifier(rsa_key_pair, monkeypatch):
    """Verify /docs tokens against a local key instead of the remote JWKS endpoint."""
    verifier = JWTVerifier(public_key=rsa_key_pair.public_key, issuer=ISSUER, algorithm="RS256")
    monkeypatch.setattr(decorators, "auth", verifier)
    return verifier


@pytest.fixture
def make_token(rsa_key_pair):
    def make(**kwargs):
        kwargs.setdefault("issuer", ISSUER)
        return rsa_key_pair.create_token(**kwargs)
    return make


@pytest.fixture
def auth_headers(make_token):
    return {"Authorization": f"Bearer {make_token()}"}


@pytest.fixture(scope="session")
def app_client():
    # the MCP session manager in the app lifespan can only start once per process
    from server import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(app_client, auth_verifier):
    app_client.headers.pop("Authorization", None)
    yield app_client
    app_client.headers.pop("Authorization", None)


@pytest.fixture(scope="session")
def real_embedding_model():
    cache_dir = os.environ.get("FASTEMBED_CACHE_PATH", os.path.join("data", "fastembed_cache"))
    return RealTextEmbedding(cache_dir=cache_dir)


@pytest.fixture
def real_embeddings(real_embedding_model, monkeypatch):
    monkeypatch.setattr(documents, "model", real_embedding_model)
    monkeypatch.setattr(searchdocs, "model", real_embedding_model)
    return real_embedding_model
