"""MCP tools and resources, called through an in-memory fastmcp client."""

import asyncio
import datetime

from fastmcp import Client

from mcp_server import mcp_server
from tests.factories import store_document
from tests.fakes import fake_vector

BEDS = "staffed hospital beds by county"
PASTA = "pasta recipes for weeknight dinners"


def run(coro_fn):
    async def main():
        async with Client(mcp_server) as client:
            return await coro_fn(client)
    return asyncio.run(main())


def call(tool, args=None):
    return run(lambda client: client.call_tool(tool, args or {})).data


def test_exposes_expected_tools():
    tools = run(lambda client: client.list_tools())
    assert {t.name for t in tools} == {"search", "datetime", "get_document_chunks"}


def test_search_tool_returns_matching_chunks():
    doc = store_document(title="Beds", url="https://example.com/beds", chunks=[
        (BEDS, fake_vector(BEDS)), (PASTA, fake_vector(PASTA)),
    ])

    result = call("search", {"query": BEDS})

    [hit] = result["results"]
    assert hit["chunk"] == BEDS
    assert hit["document_id"] == doc.id
    assert hit["url"] == "https://example.com/beds"


def test_search_tool_with_no_matches():
    assert call("search", {"query": "nothing indexed yet"}) == {"results": []}


def test_get_document_chunks_is_limited_to_one_document():
    first = store_document(title="First", chunks=[(BEDS, fake_vector(BEDS))])
    store_document(title="Second", chunks=[(BEDS, fake_vector(BEDS))])

    result = call("get_document_chunks", {"id": first.id, "query": BEDS})

    assert [r["document_id"] for r in result["results"]] == [first.id]


def test_datetime_tool_returns_current_iso_timestamp():
    value = datetime.datetime.fromisoformat(call("datetime"))
    assert abs((datetime.datetime.now() - value).total_seconds()) < 60


def test_document_resource_reads_bundled_html():
    def read(uri):
        return run(lambda client: client.read_resource(uri))[0].text

    with open("documents/DOC1.html") as f:
        assert read("hopper://documents/DOC1") == f.read()
    with open("documents/DOC2.html") as f:
        assert read("hopper://documents/anything-else") == f.read()
