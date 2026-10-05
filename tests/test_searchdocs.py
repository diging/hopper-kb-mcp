import searchdocs
from tests.factories import store_document
from tests.fakes import fake_vector


def test_search_embeds_query_and_returns_matching_chunks():
    store_document(title="Beds", chunks=[
        ("staffed hospital beds by county", fake_vector("staffed hospital beds by county")),
        ("pasta recipes for weeknight dinners", fake_vector("pasta recipes for weeknight dinners")),
    ])

    results = searchdocs.search("staffed hospital beds by county")

    assert [r["chunk"] for r in results] == ["staffed hospital beds by county"]


def test_search_with_document_id_only_returns_that_document():
    text = "emergency department wait times"
    first = store_document(title="First", chunks=[(text, fake_vector(text))])
    store_document(title="Second", chunks=[(text, fake_vector(text))])

    results = searchdocs.search(text, document_id=first.id)

    assert [r["document_id"] for r in results] == [first.id]


def test_search_without_matches_returns_empty_list():
    text = "emergency department wait times"
    store_document(chunks=[(text, fake_vector(text))])
    assert searchdocs.search("completely different words entirely") == []
