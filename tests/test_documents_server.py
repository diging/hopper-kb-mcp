"""The /docs document-management endpoints, called over HTTP with a valid token."""

import json
from unittest.mock import patch

import httpx
import pytest
from unstructured.documents.elements import NarrativeText

import dbconnect
from tests.factories import store_document
from tests.fakes import unit_vector

URL = "https://health.example.com/beds"
PAGE = (b"<html><head><title>State Bed Capacity</title></head><body>"
        b"<p>Hospitals across the state reported staffed bed capacity this quarter.</p></body></html>")
PDF_ELEMENTS = [NarrativeText("The annual report lists staffed beds for every rural hospital.")]


@pytest.fixture
def api(client, auth_headers):
    """The test client with a valid bearer token on every request."""
    client.headers.update(auth_headers)
    return client


def fetched(status=200, content=PAGE):
    return httpx.Response(status, content=content, request=httpx.Request("GET", URL))


# --- GET /docs/list ---------------------------------------------------------

def test_list_paginates_and_includes_chunks(api):
    for i in range(3):
        store_document(title=f"Doc {i}", chunks=[(f"chunk {i}", unit_vector(1))])

    body = api.get("/docs/list", params={"page": 2, "page_size": 2}).json()

    assert (body["total"], body["page"], body["page_size"]) == (3, 2, 2)
    [doc] = body["documents"]
    assert doc["title"] == "Doc 2"
    assert doc["chunks"][0]["content"] == "chunk 2"


def test_list_can_omit_chunks(api):
    store_document(chunks=[("chunk", unit_vector(1))])
    body = api.get("/docs/list", params={"return_chunks": "false"}).json()
    assert body["documents"][0]["chunks"] == []


def test_list_defaults_invalid_paging_params(api):
    body = api.get("/docs/list", params={"page": "abc", "page_size": "xyz"}).json()
    assert (body["page"], body["page_size"]) == (1, 10)


# --- POST /docs/website/add -------------------------------------------------

@patch("website_docs.httpx.get")
def test_add_website_returns_created_document(mock_get, api):
    mock_get.return_value = fetched()

    resp = api.post("/docs/website/add", params={"url": URL}, json={"metadata": {"publisher": "State"}})

    assert resp.status_code == 200
    body = resp.json()
    assert (body["title"], body["type"], body["url"]) == ("State Bed Capacity", "website", URL)
    assert body["metadata"] == {"publisher": "State"}
    assert dbconnect.get_document_by_id(body["doc_id"]) is not None


@patch("website_docs.httpx.get")
def test_add_website_without_body_has_no_metadata(mock_get, api):
    mock_get.return_value = fetched()
    body = api.post("/docs/website/add", params={"url": URL}).json()
    assert body["metadata"] is None


def test_add_website_rejects_invalid_json_body(api):
    resp = api.post("/docs/website/add", params={"url": URL}, content=b"{not json")
    assert resp.status_code == 400
    assert resp.json()["error"].startswith("Invalid JSON body")


@patch("website_docs.httpx.get")
def test_add_website_reports_upstream_http_status(mock_get, api):
    mock_get.return_value = fetched(status=404, content=b"missing")
    resp = api.post("/docs/website/add", params={"url": URL})
    assert resp.status_code == 500
    assert resp.json() == {"error": "Website could not be accessed. Returned status: 404"}
    assert dbconnect.get_documents_count() == 0


@patch("website_docs.add_website", side_effect=ValueError("parser blew up"))
def test_add_website_hides_unexpected_errors(_, api):
    resp = api.post("/docs/website/add", params={"url": URL})
    assert resp.status_code == 500
    assert resp.json() == {"error": "An error occurred while processing the website."}


# --- POST /docs/pdf/add -----------------------------------------------------

def pdf_upload(name="report.pdf", content=b"%PDF-1.4 bytes"):
    return {"file": (name, content, "application/pdf")}


@patch("pdf_docs.partition_pdf", return_value=PDF_ELEMENTS)
def test_add_pdf_stores_file_and_document(_, api, data_dir):
    resp = api.post("/docs/pdf/add", files=pdf_upload(), data={
        "title": "Annual report", "url": "https://example.com/r.pdf",
        "metadata": json.dumps({"year": 2024}),
    })

    assert resp.status_code == 200
    body = resp.json()
    assert (body["title"], body["type"], body["metadata"]) == ("Annual report", "pdf", {"year": 2024})
    stored = dbconnect.get_document_by_id(body["doc_id"])
    assert stored.local_path.startswith(str(data_dir))
    with open(stored.local_path, "rb") as f:
        assert f.read() == b"%PDF-1.4 bytes"


@pytest.mark.parametrize("files, data", [
    ({}, {"title": "No file"}),
    (pdf_upload(), {}),
])
def test_add_pdf_requires_file_and_title(api, files, data):
    resp = api.post("/docs/pdf/add", files=files or None, data=data)
    assert resp.status_code == 400
    assert resp.json() == {"error": "Missing 'file' or 'title' in form data."}


def test_add_pdf_rejects_invalid_metadata(api):
    resp = api.post("/docs/pdf/add", files=pdf_upload(), data={"title": "x", "metadata": "{bad"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "'metadata' must be valid JSON."}


@patch("pdf_docs.partition_pdf", side_effect=ValueError("not a pdf"))
def test_add_pdf_hides_processing_errors(_, api):
    resp = api.post("/docs/pdf/add", files=pdf_upload(), data={"title": "x"})
    assert resp.status_code == 500
    assert resp.json() == {"error": "An error occurred while processing the PDF."}
    assert dbconnect.get_documents_count() == 0


# --- POST /docs/pdf/update --------------------------------------------------

@patch("pdf_docs.partition_pdf", return_value=PDF_ELEMENTS)
def test_update_pdf_replaces_document_in_place(_, api):
    doc = store_document(title="Old", doc_type="pdf", chunks=[("old text", unit_vector(1))])

    resp = api.post("/docs/pdf/update", files=pdf_upload(name="v2.pdf"), data={
        "doc_id": str(doc.id), "title": "Revised",
    })

    assert resp.status_code == 200
    assert resp.json()["doc_id"] == doc.id
    stored = dbconnect.get_document_by_id(doc.id)
    assert stored.title == "Revised"
    assert [c.content for c in stored.chunks] == [PDF_ELEMENTS[0].text]


@pytest.mark.parametrize("files, data", [
    ({}, {"doc_id": "1", "title": "t"}),
    (pdf_upload(), {"doc_id": "1"}),
    (pdf_upload(), {"title": "t"}),
])
def test_update_pdf_requires_all_fields(api, files, data):
    resp = api.post("/docs/pdf/update", files=files or None, data=data)
    assert resp.status_code == 400
    assert resp.json() == {"error": "Missing 'doc_id', 'file', or 'title' in form data."}


def test_update_pdf_rejects_non_integer_id(api):
    resp = api.post("/docs/pdf/update", files=pdf_upload(), data={"doc_id": "abc", "title": "t"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "'doc_id' must be an integer."}


def test_update_pdf_rejects_invalid_metadata(api):
    resp = api.post("/docs/pdf/update", files=pdf_upload(), data={
        "doc_id": "1", "title": "t", "metadata": "{bad",
    })
    assert resp.status_code == 400


@patch("pdf_docs.partition_pdf", return_value=PDF_ELEMENTS)
def test_update_unknown_pdf_returns_404(_, api):
    resp = api.post("/docs/pdf/update", files=pdf_upload(), data={"doc_id": "999", "title": "t"})
    assert resp.status_code == 404
    assert resp.json() == {"error": "Document not found."}


@patch("pdf_docs.partition_pdf", side_effect=ValueError("not a pdf"))
def test_update_pdf_hides_processing_errors(_, api):
    doc = store_document(doc_type="pdf")
    resp = api.post("/docs/pdf/update", files=pdf_upload(), data={"doc_id": str(doc.id), "title": "t"})
    assert resp.status_code == 500


# --- POST /docs/html/add ----------------------------------------------------

def test_add_html_stores_uploaded_page(api):
    resp = api.post("/docs/html/add", files={"file": ("page.html", PAGE, "text/html")}, data={
        "url": URL, "metadata": json.dumps({"source": "upload"}),
    })
    assert resp.status_code == 200
    body = resp.json()
    assert (body["title"], body["type"], body["url"]) == ("State Bed Capacity", "website", URL)
    assert body["metadata"] == {"source": "upload"}


@pytest.mark.parametrize("files, data", [
    ({}, {"url": URL}),
    ({"file": ("page.html", PAGE, "text/html")}, {}),
])
def test_add_html_requires_file_and_url(api, files, data):
    resp = api.post("/docs/html/add", files=files or None, data=data)
    assert resp.status_code == 400
    assert resp.json() == {"error": "Missing 'file' or 'url' in form data."}


@patch("website_docs.add_html", side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))
def test_add_html_hides_processing_errors(_, api):
    resp = api.post("/docs/html/add", files={"file": ("p.html", b"\xff", "text/html")}, data={"url": URL})
    assert resp.status_code == 500
    assert "error" in resp.json()
    assert dbconnect.get_documents_count() == 0


def test_add_html_rejects_invalid_metadata(api):
    resp = api.post("/docs/html/add", files={"file": ("p.html", PAGE, "text/html")}, data={
        "url": URL, "metadata": "{bad",
    })
    assert resp.status_code == 400


# --- GET /docs/{doc_id}/file ------------------------------------------------

def test_get_file_streams_stored_pdf(api, tmp_path):
    pdf = tmp_path / "1780-report.pdf"
    pdf.write_bytes(b"%PDF-1.4 stored")
    doc = store_document(doc_type="pdf", local_path=str(pdf))

    resp = api.get(f"/docs/{doc.id}/file")

    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 stored"
    assert resp.headers["content-type"] == "application/pdf"
    assert 'filename="1780-report.pdf"' in resp.headers["content-disposition"]


def test_get_file_for_unknown_document_returns_404(api):
    resp = api.get("/docs/999/file")
    assert resp.status_code == 404
    assert resp.json() == {"error": "Document not found."}


def test_get_file_rejects_non_integer_id(api):
    assert api.get("/docs/abc/file").status_code == 400


@pytest.mark.parametrize("doc_type, has_file", [
    ("website", True),   # only PDFs are served
    ("pdf", False),      # legacy row: path recorded but file gone
])
def test_get_file_unavailable(api, tmp_path, doc_type, has_file):
    path = tmp_path / "report.pdf"
    if has_file:
        path.write_bytes(b"%PDF")
    doc = store_document(doc_type=doc_type, local_path=str(path))

    resp = api.get(f"/docs/{doc.id}/file")

    assert resp.status_code == 404
    assert resp.json() == {"error": "file_unavailable"}


def test_get_file_for_pdf_without_local_path(api):
    doc = store_document(doc_type="pdf")
    assert api.get(f"/docs/{doc.id}/file").json() == {"error": "file_unavailable"}


# --- DELETE /docs/{doc_id} --------------------------------------------------

def test_delete_document(api):
    doc = store_document(chunks=[("chunk", unit_vector(1))])
    resp = api.delete(f"/docs/{doc.id}")
    assert resp.json() == {"success": True, "doc_id": doc.id}
    assert dbconnect.get_document_by_id(doc.id) is None


def test_delete_unknown_document_returns_404(api):
    resp = api.delete("/docs/999")
    assert resp.status_code == 404
    assert resp.json() == {"error": "Document not found."}


def test_delete_rejects_non_integer_id(api):
    assert api.delete("/docs/abc").status_code == 400
