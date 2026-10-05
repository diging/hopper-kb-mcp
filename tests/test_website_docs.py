from unittest.mock import patch

import httpx
import pytest

import dbconnect
import website_docs

URL = "https://health.example.com/beds"
PAGE = b"""<html><head><title>  State Bed Capacity  </title></head>
<body><h1>Bed capacity</h1>
<p>Hospitals across the state reported staffed bed capacity for intensive care units this quarter.</p>
</body></html>"""


def respond(status=200, content=PAGE):
    return httpx.Response(status, content=content, request=httpx.Request("GET", URL))


@patch("website_docs.httpx.get")
def test_add_website_fetches_page_and_stores_document(mock_get):
    mock_get.return_value = respond()

    doc = website_docs.add_website(URL, metadata={"publisher": "State"})

    mock_get.assert_called_once_with(URL, headers={"User-Agent": "HopperKbBot/1.0.0"})
    stored = dbconnect.get_document_by_id(doc.id)
    assert stored.title == "State Bed Capacity"
    assert (stored.doc_type, stored.url) == ("website", URL)
    assert stored.metadata_json == {"publisher": "State"}
    assert stored.local_path is None
    assert any("staffed bed capacity" in c.content for c in stored.chunks)


@patch("website_docs.httpx.get")
def test_page_without_title_gets_placeholder(mock_get):
    mock_get.return_value = respond(content=b"<p>" + b"Emergency department wait times by hospital. " * 3 + b"</p>")
    assert website_docs.add_website(URL).title == "No Title Found"


@patch("website_docs.httpx.get")
def test_http_error_raises_and_stores_nothing(mock_get):
    mock_get.return_value = respond(status=404, content=b"not found")
    with pytest.raises(httpx.HTTPStatusError):
        website_docs.add_website(URL)
    assert dbconnect.get_documents_count() == 0


@patch("website_docs.httpx.get")
def test_re_adding_same_url_updates_existing_document(mock_get):
    mock_get.return_value = respond()
    first = website_docs.add_website(URL)

    mock_get.return_value = respond(content=PAGE.replace(
        b"intensive care units", b"pediatric wards and neonatal units"
    ))
    second = website_docs.add_website(URL, metadata={"v": 2})

    assert second.id == first.id
    assert dbconnect.get_documents_count() == 1
    stored = dbconnect.get_document_by_id(first.id)
    assert any("neonatal" in c.content for c in stored.chunks)
    assert not any("intensive care" in c.content for c in stored.chunks)
    assert stored.metadata_json == {"v": 2}


def test_add_html_stores_uploaded_page_without_fetching():
    with patch("website_docs.httpx.get") as mock_get:
        doc = website_docs.add_html(PAGE, URL, metadata={"source": "upload"})
    mock_get.assert_not_called()
    stored = dbconnect.get_document_by_id(doc.id)
    assert stored.title == "State Bed Capacity"
    assert stored.metadata_json == {"source": "upload"}
