"""
Tests for Copilot RAG Knowledge Retrieval, Jurisdiction Scoping,
Retired Policy Exclusion, and Document Injection Defense.
"""

import pytest
from app.core.database import get_database
from app.services.copilot.rag_service import rag_service
from app.services.copilot.test_utils import setup_mock_db



@pytest.fixture(autouse=True)
def mock_db_fixture(monkeypatch):
    return setup_mock_db(monkeypatch)



@pytest.mark.asyncio
async def test_01_rag_seeding_and_indexing():
    """Verify default knowledge documents are seeded into database with indexes."""
    await rag_service.init_indexes()
    db = get_database()
    count = await db["copilot_knowledge_docs"].count_documents({})
    assert count >= 3


@pytest.mark.asyncio
async def test_02_rag_search_and_citations():
    """Verify semantic retrieval returns relevant approved documents with citations."""
    results = await rag_service.search(query="responder acknowledgement timeout", limit=2)
    assert len(results) >= 1
    top_doc = results[0]
    assert any(term in top_doc["title"] for term in ["Procedure", "Policy", "Standard", "Manual"])
    assert "version" in top_doc
    assert "section" in top_doc
    assert top_doc["status"] == "active"



@pytest.mark.asyncio
async def test_03_retired_document_exclusion():
    """Verify retired policies are excluded by default from operational guidance."""
    results = await rag_service.search(query="2024 legacy response", include_retired=False)
    for r in results:
        assert r["status"] != "retired"


@pytest.mark.asyncio
async def test_04_jurisdiction_scoping():
    """Verify documents for Jurisdiction A are not leaked to Jurisdiction B."""
    db = get_database()
    doc_jur_a = {
        "document_id": "pol_jur_alpha_secret_sop",
        "title": "Alpha Sector Local SOP",
        "category": "sop",
        "version": "v1.0.0",
        "jurisdiction_id": "jur_alpha_99",
        "status": "active",
        "effective_date": "2026-01-01",
        "sections": [{"heading": "Alpha Rules", "content": "Special local procedure for Alpha sector only."}],
        "tags": ["alpha", "local"],
    }
    await db["copilot_knowledge_docs"].delete_many({"document_id": "pol_jur_alpha_secret_sop"})
    await db["copilot_knowledge_docs"].insert_one(doc_jur_a)

    # Search from Beta jurisdiction -> should not find Alpha doc
    results_beta = await rag_service.search(query="Special local procedure Alpha", jurisdiction_id="jur_beta_88")
    for r in results_beta:
        assert r["document_id"] != "pol_jur_alpha_secret_sop"

    # Search from Alpha jurisdiction -> should find Alpha doc
    results_alpha = await rag_service.search(query="Special local procedure Alpha", jurisdiction_id="jur_alpha_99")
    found = any(r["document_id"] == "pol_jur_alpha_secret_sop" for r in results_alpha)
    assert found is True
