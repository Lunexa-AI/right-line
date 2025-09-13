import types
import json
import pytest


@pytest.mark.unit
def test_merge_tree_and_ocr_nodes_merges_by_title_and_page_index():
    # Import lazily to avoid side-effects at collection time
    from scripts.parse_docs_v3 import _merge_tree_and_ocr_nodes

    tree = [
        {"title": "1. Short title", "node_id": "0000", "page_index": 3},
        {"title": "2. Hypothecation of State for arrear rents or taxes limited", "node_id": "0001", "page_index": 3},
    ]

    ocr_nodes = [
        {"title": "1.  Short  title", "page_index": 3, "text": "<physical_index_3>\n## 1. Short title\nBody A"},
        {"title": "2.  Hypothecation of State for arrear rents or taxes limited", "page_index": 3, "text": "<physical_index_3>\n## 2. Hypothecation...\nBody B"},
    ]

    merged = _merge_tree_and_ocr_nodes(tree, ocr_nodes)

    assert merged[0]["text"].startswith("<physical_index_3>\n## 1. Short title"), "First node text should merge from OCR"
    assert merged[1]["text"].startswith("<physical_index_3>\n## 2. Hypothecation"), "Second node text should merge from OCR"


@pytest.mark.unit
def test_poll_pageindex_fallback_builds_markdown_when_raw_fails(monkeypatch):
    from scripts import parse_docs_v3

    doc_id = "pi-abc123"
    api_key = "test-key"

    # Prepare fake responses
    status_json = {"doc_id": doc_id, "status": "completed", "retrieval_ready": False}
    tree_json = {"result": [
        {"title": "1. Short title", "node_id": "0000", "page_index": 3},
        {"title": "2. Hypothecation of State for arrear rents or taxes limited", "node_id": "0001", "page_index": 3},
    ]}
    ocr_nodes_json = {"result": [
        {"title": "1. Short title", "page_index": 3, "text": "<physical_index_3>\n## 1. Short title\nBody A"},
        {"title": "2. Hypothecation of State for arrear rents or taxes limited", "page_index": 3, "text": "<physical_index_3>\n## 2. Hypothecation...\nBody B"},
    ]}
    ocr_pages_json = {"result": [
        {"page_index": 1, "markdown": "Front matter"},
        {"page_index": 3, "markdown": "## 1. Short title\nBody A\n\n## 2. Hypothecation...\nBody B"},
    ]}

    class FakeResponse:
        def __init__(self, status_code=200, payload=None, text=None):
            self.status_code = status_code
            self._payload = payload
            self.text = text or (json.dumps(payload) if payload is not None else "")

        def raise_for_status(self):
            if self.status_code >= 400:
                import requests
                raise requests.HTTPError(f"{self.status_code} Server Error")

        def json(self):
            return self._payload

    def fake_get(url, headers=None, timeout=None):
        if url.endswith(f"/doc/{doc_id}/"):
            return FakeResponse(200, status_json)
        if url.endswith(f"/doc/{doc_id}/?type=tree"):
            return FakeResponse(200, tree_json)
        if url.endswith(f"/doc/{doc_id}/?type=ocr&format=node"):
            return FakeResponse(200, ocr_nodes_json)
        if url.endswith(f"/doc/{doc_id}/?type=ocr&format=raw"):
            return FakeResponse(500, None, text="Internal Server Error")
        if url.endswith(f"/doc/{doc_id}/?type=ocr&format=page"):
            return FakeResponse(200, ocr_pages_json)
        return FakeResponse(404, None, text="Not Found")

    monkeypatch.setattr(parse_docs_v3.requests, "get", fake_get)

    result = parse_docs_v3.poll_pageindex(doc_id, api_key, poll_interval=0)

    # Expect concatenated markdown from pages because raw failed
    assert result["markdown"].startswith("--- Page 1 ---\n\nFront matter"), "Markdown should be built from page-format OCR when raw fails"
    assert "--- Page 3 ---" in result["markdown"], "Markdown should include later pages"
    # Tree should still be present and merged
    assert isinstance(result["tree"], list) and len(result["tree"]) == 2


@pytest.mark.unit
def test_extract_akn_metadata_overrides_filename_title_with_markdown_title():
    from scripts.parse_docs_v3 import extract_akn_metadata

    filename = "corpus/sources/legislation/acts/akn_zw_act_1861_5_eng_2016-12-31.pdf"
    tree_nodes = []
    full_markdown = (
        "Zimbabwe\n\nTacit Hypothec Amendment Act Chapter 6:05\n\n"
        "Some front matter...\n"
    )

    md = extract_akn_metadata(filename, tree_nodes, full_markdown=full_markdown, ocr_pages=None)

    assert md["title"] == "Tacit Hypothec Amendment Act"
    assert md["chapter"] == "6:05"
    assert md["canonical_citation"] == "Tacit Hypothec Amendment Act [Chapter 6:05]"


@pytest.mark.unit
def test_extract_title_from_short_title_line():
    from scripts.parse_docs_v3 import extract_akn_metadata

    filename = "corpus/sources/legislation/acts/akn_zw_act_1882_41_eng_2016-12-31.pdf"
    tree_nodes = [
        {"title": "Service of Documents (Telegraph) Act Chapter 8:13", "page_index": 3}
    ]
    full_markdown = (
        "# Service of Documents (Telegraph) Act Chapter 8:13\n\n"
        "# 1. Short title\n\n"
        "This Act may be cited as the Service of Documents (Telegraph) Act [Chapter 8:13].\n"
    )

    md = extract_akn_metadata(filename, tree_nodes, full_markdown=full_markdown, ocr_pages=None)

    assert md["title"] == "Service of Documents (Telegraph) Act"
    assert md["chapter"] == "8:13"
    assert md["canonical_citation"] == "Service of Documents (Telegraph) Act [Chapter 8:13]"

@pytest.mark.unit
def test_extract_title_prefers_tree_header():
    from scripts.parse_docs_v3 import extract_akn_metadata

    filename = "corpus/sources/legislation/acts/akn_zw_act_1873_26_eng_2016-12-31.pdf"
    tree_nodes = [
        {"title": "Deceased Estates Succession Act", "page_index": 1},
        {"title": "Part I - Preliminary", "page_index": 3}
    ]
    full_markdown = "Intro text"

    md = extract_akn_metadata(filename, tree_nodes, full_markdown=full_markdown, ocr_pages=None)

    assert md["title"] == "Deceased Estates Succession Act"


@pytest.mark.unit
def test_sanitize_tree_removes_banners_and_chapter_and_hoists_children():
    from scripts.parse_docs_v3 import _sanitize_tree

    tree = [
        {
            "title": "Zimbabwe",
            "page_index": 1,
            "nodes": [
                {
                    "title": "General Law Amendment Act",
                    "page_index": 1,
                    "text": "<physical_index_1>\n## General Law Amendment Act\nFront matter",
                    "nodes": [
                        {"title": "Chapter 8:07", "page_index": 1, "text": "### Chapter 8:07"}
                    ],
                }
            ],
        },
        {"title": "Zimbabwe", "page_index": 3},
    ]

    sanitized = _sanitize_tree(tree)

    # Banner nodes removed/hoisted; first node should be the Act title
    assert sanitized and sanitized[0]["title"] == "General Law Amendment Act"
    # Chapter node removed
    assert not any(n.get("title", "").startswith("Chapter ") for n in sanitized[0].get("nodes", []))
    # Physical markers and duplicate heading removed
    assert "<physical_index_" not in sanitized[0].get("text", "")
    assert not sanitized[0].get("text", "").lstrip().startswith("## General Law Amendment Act")


@pytest.mark.unit
def test_sanitize_text_strips_boilerplate_and_duplicate_heading():
    from scripts.parse_docs_v3 import _sanitize_text

    raw = (
        "<physical_index_1>\n## General Law Amendment Act\n"
        "About this collection\nFRBR URI: /akn/zw/act/...\n"
        "This PDF copy is licensed under a Creative Commons...\n"
        "Body paragraph.\n"
        "![img-0.jpeg](img-0.jpeg)\n"
        "www.laws.africa\ninfo@laws.africa\n"
    )

    cleaned = _sanitize_text(raw, node_title="General Law Amendment Act")

    assert "<physical_index_" not in cleaned
    assert "About this collection" not in cleaned
    assert "FRBR URI" not in cleaned
    assert not cleaned.lstrip().startswith("## General Law Amendment Act")
    assert "![img-" not in cleaned
