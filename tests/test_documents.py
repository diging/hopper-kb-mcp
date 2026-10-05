import datetime

from unstructured.documents.elements import ElementMetadata, NarrativeText, Title

import dbconnect
import documents
from tests.factories import store_document
from tests.fakes import fake_vector, unit_vector

URL = "https://example.com/report"
LONG_PARAGRAPH = "Hospitals reported their staffed bed capacity for the quarter. " * 5


def test_chunks_carry_source_type_and_default_page_number():
    elements = [Title("Bed capacity"), NarrativeText(LONG_PARAGRAPH)]

    [chunk] = documents._calculate_chunks(elements, URL)

    assert chunk["id"] == "file-0"
    assert chunk["text"].startswith("Bed capacity")
    assert chunk["metadata"] == {"source": URL, "type": "CompositeElement", "page_number": 1}


def test_chunks_keep_page_number_from_elements():
    element = NarrativeText(LONG_PARAGRAPH, metadata=ElementMetadata(page_number=4))
    [chunk] = documents._calculate_chunks([element], URL)
    assert chunk["metadata"]["page_number"] == 4


def test_short_chunks_are_skipped():
    assert documents._calculate_chunks([NarrativeText("Too short")], URL) == []


def test_chunk_text_is_cleaned():
    text = "Staffed\x00beds\\nreported\\tby   the state health department today"
    [chunk] = documents._calculate_chunks([NarrativeText(text)], URL)
    assert chunk["text"] == "Staffed beds reported by the state health department today"


def test_long_text_is_split_into_multiple_chunks():
    elements = [NarrativeText(f"Paragraph {i}. " + LONG_PARAGRAPH * 2) for i in range(6)]
    chunks = documents._calculate_chunks(elements, URL)
    assert len(chunks) > 1
    assert all(len(c["text"]) <= 2000 for c in chunks)


def test_add_document_embeds_and_stores_chunks():
    elements = [Title("Bed capacity"), NarrativeText(LONG_PARAGRAPH)]

    doc = documents.add_document(
        elements, "Bed report", "pdf", URL, metadata={"year": 2024}, local_path="/data/pdfs/x.pdf",
    )

    stored = dbconnect.get_document_by_id(doc.id)
    assert (stored.title, stored.doc_type, stored.url) == ("Bed report", "pdf", URL)
    assert stored.metadata_json == {"year": 2024}
    assert stored.local_path == "/data/pdfs/x.pdf"
    [chunk] = stored.chunks
    assert chunk.order_index == 0
    assert list(chunk.content_vector) == fake_vector(chunk.content)


def test_update_document_replaces_chunks_and_fields():
    doc = documents.add_document(
        [NarrativeText("Original text about emergency department wait times.")],
        "Old title", "website", URL, metadata={"v": 1},
    )
    before = dbconnect.get_document_by_id(doc.id)

    documents.update_document(
        before, [NarrativeText("Replacement text about intensive care occupancy rates.")],
        "New title", "website", "https://example.com/new",
    )

    after = dbconnect.get_document_by_id(doc.id)
    assert after.title == "New title"
    assert after.url == "https://example.com/new"
    assert [c.content for c in after.chunks] == ["Replacement text about intensive care occupancy rates."]
    assert after.metadata_json == {"v": 1}  # untouched when no metadata is passed
    assert after.modified_at > before.created_at


def test_update_document_replaces_metadata_when_given():
    doc = documents.add_document(
        [NarrativeText("Original text about emergency department wait times.")],
        "Title", "website", URL, metadata={"v": 1},
    )
    documents.update_document(
        dbconnect.get_document_by_id(doc.id),
        [NarrativeText("Original text about emergency department wait times.")],
        "Title", "website", URL, metadata={"v": 2},
    )
    assert dbconnect.get_document_by_id(doc.id).metadata_json == {"v": 2}


def test_get_documents_returns_count_and_serialised_page():
    doc = store_document(
        title="Beds", url=URL, doc_type="pdf", metadata={"publisher": "State"},
        chunks=[("bed counts", unit_vector(1))],
    )
    store_document(title="Other")

    count, page = documents.get_documents(page=1, page_size=1)

    assert count == 2
    [item] = page
    assert item["id"] == doc.id
    assert (item["title"], item["url"], item["doc_type"]) == ("Beds", URL, "pdf")
    assert item["metadata"] == {"publisher": "State"}
    datetime.datetime.fromisoformat(item["created_at"])
    datetime.datetime.fromisoformat(item["modified_at"])
    assert item["chunks"] == [{
        "order_index": 0, "content": "bed counts",
        "metadata": {"source": URL, "page_number": 1},
    }]


def test_get_documents_without_chunks_and_clamped_page():
    store_document(title="Beds", chunks=[("bed counts", unit_vector(1))])

    count, page = documents.get_documents(page=0, page_size=10, return_chunks=False)

    assert count == 1
    assert page[0]["chunks"] == []


def test_get_documents_past_last_page_is_empty():
    store_document()
    assert documents.get_documents(page=5, page_size=10) == (1, [])


def test_lookup_and_delete_delegate_to_database():
    doc = store_document(url=URL)
    assert documents.get_document_by_url(URL).id == doc.id
    assert documents.get_document_by_id(doc.id).id == doc.id
    assert documents.delete_document(doc.id) is True
    assert documents.get_document_by_id(doc.id) is None
