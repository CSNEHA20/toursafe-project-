# TourSafe AI Copilot RAG Architecture & Policy Knowledge Engine

The Retrieval-Augmented Generation (RAG) subsystem equips the AI Copilot with authoritative, version-controlled operational knowledge while preventing model hallucinations.

---

## 1. Knowledge Base Data Model

Stored in MongoDB collection `copilot_knowledge_docs`:

```json
{
  "document_id": "sop_sos_handling_v1",
  "title": "Standard Operating Procedure: Tourist Emergency Response & SOS Handling",
  "category": "sop",
  "version": "1.2.0",
  "jurisdiction_id": null,
  "status": "active",
  "effective_date": "2026-01-01T00:00:00Z",
  "sections": [
    {
      "heading": "Section 1: SOS Triage & Priority Classification",
      "content": "All SOS signals received via the Tourist App or physical SOS beacons must be acknowledged by an operational dispatcher within 60 seconds of signal ingress..."
    }
  ],
  "tags": ["emergency", "sos", "dispatch", "sla"]
}
```

---

## 2. Hybrid Retrieval Pipeline

The RAG engine employs a two-stage hybrid retrieval strategy:

1. **Pre-Filtering**:
   - Status Check: Only documents with `status == "active"` are retrieved by default. Documents tagged as `"retired"` or `"superseded"` are strictly filtered out to avoid outdated operational advice.
   - Jurisdiction Scoping: Documents must match the requesting authority's `jurisdiction_id` or be universal (`jurisdiction_id == null`).
2. **Dense Vector + Sparse Keyword Matching**:
   - Generates cosine similarity over document section embeddings.
   - Computes BM25/keyword term frequency overlap.
   - Merges scores: `Final_Score = (0.7 * Cosine_Similarity) + (0.3 * Keyword_Overlap)`.
3. **Citation Synthesis**:
   - Output documents include explicit citation identifiers: `[Doc: sop_sos_handling_v1 | Ver: 1.2.0 | Sec: Section 1]`.

---

## 3. Grounded Generation & Hallucination Prevention

When an authority operator inquires about a policy or operational SOP:
1. The model must ground its explanation directly in the retrieved section text.
2. The model generates structured citation badges referencing the document ID, version, and section.
3. If no matching active policy document exists, the Copilot explicitly states: *"No approved active standard operating procedure found for this query in the current jurisdiction."*
