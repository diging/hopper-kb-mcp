"""End-to-end tests: real document parsers, the real embedding model, pgvector search.

Documents go in over HTTP with a signed token, exactly as hosp-explorer sends
them, and come back out through the MCP search tool.

Run only these with ``pytest -m functional``; skip them with ``-m "not functional"``.
The first run downloads BAAI/bge-small-en-v1.5 into data/fastembed_cache.
"""

import asyncio
from unittest.mock import patch

import httpx
import pytest
from fastmcp import Client

from mcp_server import mcp_server
from tests.fakes import build_pdf

pytestmark = [pytest.mark.functional, pytest.mark.usefixtures("real_embeddings")]

HOSPITAL_PAGE = b"""<html><head><title>Rural Hospital Capacity Report</title></head><body>
<h1>Intensive care capacity</h1>
<p>Rural hospitals in the state operate 412 staffed intensive care beds. Occupancy in
critical care units averaged 87 percent during the winter respiratory season, and three
facilities diverted ambulances when every ICU bed was full.</p>
</body></html>"""

COOKING_PAGE = b"""<html><head><title>Weeknight Pasta</title></head><body>
<h1>Quick dinners</h1>
<p>Boil the spaghetti in salted water for nine minutes, then toss it with garlic, olive
oil, chili flakes and grated parmesan cheese for a fast weeknight dinner.</p>
</body></html>"""


@pytest.fixture
def api(client, auth_headers):
    client.headers.update(auth_headers)
    return client


def mcp_search(query, document_id=None):
    async def main():
        async with Client(mcp_server) as client:
            if document_id is None:
                return await client.call_tool("search", {"query": query})
            return await client.call_tool("get_document_chunks", {"id": document_id, "query": query})
    return asyncio.run(main()).data["results"]


def upload_html(api, page, url):
    resp = api.post("/docs/html/add", files={"file": ("page.html", page, "text/html")}, data={"url": url})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_html_document_is_found_by_semantic_search_and_can_be_deleted(api):
    hospital = upload_html(api, HOSPITAL_PAGE, "https://health.example.com/capacity")
    cooking = upload_html(api, COOKING_PAGE, "https://food.example.com/pasta")

    # paraphrased queries: no exact keyword overlap is needed to rank the right document first
    icu_hits = mcp_search("How full were critical care units in country hospitals?")
    food_hits = mcp_search("easy noodle recipe for dinner")

    assert icu_hits and icu_hits[0]["document_id"] == hospital["doc_id"]
    assert icu_hits[0]["title"] == "Rural Hospital Capacity Report"
    assert "412 staffed intensive care beds" in icu_hits[0]["chunk"]
    assert food_hits and food_hits[0]["document_id"] == cooking["doc_id"]

    listing = api.get("/docs/list").json()
    assert listing["total"] == 2
    assert all(doc["chunks"] for doc in listing["documents"])

    assert api.delete(f"/docs/{hospital['doc_id']}").json()["success"] is True
    assert all(hit["document_id"] != hospital["doc_id"]
               for hit in mcp_search("How full were critical care units in country hospitals?"))


def test_pdf_is_parsed_searchable_downloadable_and_updatable(api):
    original = build_pdf([
        "Annual Emergency Department Report",
        "Median emergency department wait time was 47 minutes across urban hospitals.",
        "Patients who left without being seen fell to 2 percent after triage changes.",
    ])
    resp = api.post("/docs/pdf/add", files={"file": ("ed-report.pdf", original, "application/pdf")},
                    data={"title": "ED Report", "metadata": '{"year": 2024}'})
    assert resp.status_code == 200, resp.text
    doc_id = resp.json()["doc_id"]

    hits = mcp_search("How long did patients wait in the ER?", document_id=doc_id)
    assert hits and "47 minutes" in hits[0]["chunk"]
    assert hits[0]["metadata"]["page_number"] == 1

    download = api.get(f"/docs/{doc_id}/file")
    assert download.status_code == 200
    assert download.content == original

    revised = build_pdf([
        "Revised Emergency Department Report",
        "Median emergency department wait time improved to 31 minutes after adding staff.",
        "Ambulance offload delays dropped below fifteen minutes at every hospital.",
    ])
    resp = api.post("/docs/pdf/update", files={"file": ("ed-report-v2.pdf", revised, "application/pdf")},
                    data={"doc_id": str(doc_id), "title": "ED Report (revised)"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["doc_id"] == doc_id
    assert resp.json()["metadata"] == {"year": 2024}

    chunks = " ".join(h["chunk"] for h in mcp_search("How long did patients wait in the ER?", document_id=doc_id))
    assert "31 minutes" in chunks
    assert "47 minutes" not in chunks
    assert api.get(f"/docs/{doc_id}/file").content == revised
    assert api.get("/docs/list").json()["total"] == 1


@patch("website_docs.httpx.get")
def test_re_ingesting_a_website_updates_it_instead_of_duplicating(mock_get, api):
    url = "https://health.example.com/capacity"

    def serve(content):
        mock_get.return_value = httpx.Response(200, content=content, request=httpx.Request("GET", url))

    serve(HOSPITAL_PAGE)
    first = api.post("/docs/website/add", params={"url": url}).json()

    serve(HOSPITAL_PAGE.replace(b"412 staffed intensive care beds", b"530 staffed intensive care beds"))
    second = api.post("/docs/website/add", params={"url": url}).json()

    assert second["doc_id"] == first["doc_id"]
    assert api.get("/docs/list").json()["total"] == 1
    [hit, *_] = mcp_search("number of ICU beds in rural hospitals")
    assert "530 staffed intensive care beds" in hit["chunk"]
