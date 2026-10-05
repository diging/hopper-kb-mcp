import dbconnect
from dbmodel import Document, DocumentChunk
from tests.factories import store_document
from tests.fakes import unit_vector

QUERY = unit_vector(1)


def test_add_and_fetch_document_by_id_and_url():
    doc = store_document(
        title="Bed capacity", url="https://example.com/beds",
        chunks=[("Hospital bed counts by state", unit_vector(1))],
        metadata={"publisher": "State"},
    )
    assert doc.id is not None

    by_id = dbconnect.get_document_by_id(doc.id)
    by_url = dbconnect.get_document_by_url("https://example.com/beds")

    assert by_id.id == by_url.id == doc.id
    assert by_id.metadata_json == {"publisher": "State"}
    assert [c.content for c in by_id.chunks] == ["Hospital bed counts by state"]
    assert by_id.created_at is not None


def test_missing_document_lookups_return_none():
    assert dbconnect.get_document_by_id(999) is None
    assert dbconnect.get_document_by_url("https://nowhere.test") is None


def test_search_keeps_only_chunks_within_distance_threshold_ordered_by_distance():
    store_document(title="Doc", url="https://example.com", chunks=[
        ("exact", unit_vector(1)),          # distance 0
        ("close", unit_vector(1, 1)),       # distance ~0.29
        ("too far", unit_vector(1, 2)),     # distance ~0.55
        ("unrelated", unit_vector(0, 1)),   # distance 1
    ])

    results = dbconnect.search_documents(QUERY)

    assert [r["chunk"] for r in results] == ["exact", "close"]


def test_search_result_shape():
    doc = store_document(
        title="Bed capacity", url="https://example.com/beds",
        chunks=[("intro", unit_vector(0, 1)), ("beds", unit_vector(1))],
    )

    [result] = dbconnect.search_documents(QUERY)

    assert result == {
        "title": "Bed capacity",
        "url": "https://example.com/beds",
        "chunk": "beds",
        "id": f"{doc.id}-1",
        "document_id": doc.id,
        "order_index": 1,
        "metadata": {"source": "https://example.com/beds", "page_number": 1},
    }


def test_search_can_be_restricted_to_one_document():
    first = store_document(title="First", chunks=[("first match", unit_vector(1))])
    store_document(title="Second", chunks=[("second match", unit_vector(1))])

    results = dbconnect.search_documents(QUERY, document_id=first.id)

    assert [r["chunk"] for r in results] == ["first match"]


def test_search_respects_result_limit(monkeypatch):
    monkeypatch.setattr(dbconnect, "NUM_OF_SEARCH_RESULTS", 2)
    store_document(chunks=[(f"chunk {i}", unit_vector(1)) for i in range(5)])

    assert len(dbconnect.search_documents(QUERY)) == 2


def test_search_with_no_matches_returns_empty_list():
    store_document(chunks=[("unrelated", unit_vector(0, 1))])
    assert dbconnect.search_documents(QUERY) == []


def test_get_documents_paginates_in_id_order():
    for i in range(5):
        store_document(title=f"Doc {i}")

    page = dbconnect.get_documents(offset=2, page_size=2)

    assert [d.title for d in page] == ["Doc 2", "Doc 3"]
    assert dbconnect.get_documents_count() == 5


def test_update_document_replaces_chunks():
    doc = store_document(title="Old", chunks=[("old one", unit_vector(1)), ("old two", unit_vector(1))])
    stored = dbconnect.get_document_by_id(doc.id)

    stored.title = "New"
    stored.chunks = [DocumentChunk(order_index=0, content="new", content_vector=unit_vector(1))]
    dbconnect.update_document(stored)

    refreshed = dbconnect.get_document_by_id(doc.id)
    assert refreshed.title == "New"
    assert [c.content for c in refreshed.chunks] == ["new"]
    assert dbconnect.get_documents_count() == 1


def test_delete_document_removes_row_chunks_and_file(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF")
    doc = store_document(doc_type="pdf", chunks=[("text", unit_vector(1))], local_path=str(pdf))

    assert dbconnect.delete_document(doc.id) is True

    assert dbconnect.get_document_by_id(doc.id) is None
    assert dbconnect.search_documents(QUERY) == []
    assert not pdf.exists()


def test_delete_missing_document_returns_false():
    assert dbconnect.delete_document(999) is False


def test_delete_document_whose_file_is_already_gone(tmp_path):
    doc = store_document(local_path=str(tmp_path / "gone.pdf"))
    assert dbconnect.delete_document(doc.id) is True
    assert dbconnect.get_document_by_id(doc.id) is None


def test_failed_file_removal_still_deletes_row(tmp_path, monkeypatch):
    pdf = tmp_path / "locked.pdf"
    pdf.write_bytes(b"%PDF")
    doc = store_document(local_path=str(pdf))

    def refuse(path):
        raise OSError("permission denied")

    monkeypatch.setattr(dbconnect.os, "remove", refuse)

    assert dbconnect.delete_document(doc.id) is False
    assert dbconnect.get_document_by_id(doc.id) is None


def test_document_model_defaults():
    doc = Document(title="t", doc_type="website")
    dbconnect.add_document(doc)
    assert doc.created_at is not None
    assert doc.modified_at is not None
    assert dbconnect.get_document_by_id(doc.id).chunks == []
