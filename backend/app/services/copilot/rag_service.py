"""
TourSafe Copilot RAG (Retrieval-Augmented Generation) & Knowledge Service.
Manages ingestion, chunking, semantic retrieval, jurisdiction filtering,
active status verification, and precise citations for approved documentation,
SOPs, emergency response protocols, and policy manuals.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from ...core.database import get_database
from ...models.copilot import KnowledgeDocument
from .llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


DEFAULT_SEEDED_DOCS = [
    {
        "document_id": "sop_emergency_response_v1",
        "title": "Standard Operating Procedure: Tourist Emergency Response & SOS Handling",
        "category": "sop",
        "version": "v1.2.0",
        "jurisdiction_id": None,  # Universal
        "status": "active",
        "effective_date": "2026-01-01",
        "sections": [
            {
                "heading": "Section 1: SOS Ingestion and Verification",
                "content": "Upon receipt of a tourist SOS signal or High-Risk State Trigger (Safety Candidate State), an incident record is created immediately. Dispatch operators must review tourist location coordinates, battery telemetry, and recent IMU kinematics within 60 seconds.",
            },
            {
                "heading": "Section 2: Responder Dispatch SLA",
                "content": "The nearest available responder unit with matching capabilities (Medical / Police / Search & Rescue) must be assigned within 120 seconds. The responder must acknowledge receipt within 180 seconds. If unacknowledged, the automated response engine initiates Stage 1 redispatch.",
            },
            {
                "heading": "Section 3: Proximity Arrival Verification",
                "content": "Responders must approach within 500 meters of the tourist incident location coordinates to trigger proximity arrival verification. In areas with degraded GPS (DOP > 5.0), manual operator override is authorized with mandatory rationale logging.",
            },
        ],
        "tags": ["emergency", "sos", "dispatch", "sla", "sop"],
    },
    {
        "document_id": "pol_escalation_protocol_v2",
        "title": "Policy Manual: Multi-Tier Incident Escalation & Supervisor Override",
        "category": "policy",
        "version": "v2.0.0",
        "jurisdiction_id": None,
        "status": "active",
        "effective_date": "2026-02-15",
        "sections": [
            {
                "heading": "Section 1: Escalation Thresholds",
                "content": "Incidents with Composite Risk Scores exceeding 0.75 or unresolved distress alerts exceeding 15 minutes are classified as Priority 1 Critical. Automatic supervisor notification is triggered via high-priority push and SMS channels.",
            },
            {
                "heading": "Section 2: Multi-Party Coordination Channels",
                "content": "Priority 1 incidents mandate the creation of an isolated incident communication channel linking the Tourist, Assigned Responder, Authority Dispatcher, and Medical Support team. All messages are monotonically sequenced and audited.",
            },
            {
                "heading": "Section 3: Incident Closure Requirements",
                "content": "An incident cannot be closed until the assigned responder submits a structured Scene Assessment, confirms tourist safety status, and the dispatch operator verifies resolution in the Command Center.",
            },
        ],
        "tags": ["escalation", "priority", "supervisor", "closure", "policy"],
    },
    {
        "document_id": "sop_geofencing_danger_zones_v1",
        "title": "Standard Operating Procedure: Danger Zone Geofencing & Intrusion Response",
        "category": "protocol",
        "version": "v1.1.0",
        "jurisdiction_id": None,
        "status": "active",
        "effective_date": "2026-01-10",
        "sections": [
            {
                "heading": "Section 1: Restricted and Danger Zone Entry",
                "content": "When a tourist GPS fix intersects a Danger or Restricted safety zone polygon with dwell time exceeding 30 seconds, an automated advisory notification is transmitted to the tourist mobile application and the risk state elevates to WATCH or ELEVATED.",
            },
            {
                "heading": "Section 2: High Tide and Curfew Management",
                "content": "Temporary risk zones activated during storm surges or night curfews enforce active beaconing at 10-second intervals for all tourist devices present within the boundary.",
            },
        ],
        "tags": ["geofencing", "zones", "danger", "curfew", "protocol"],
    },
    {
        "document_id": "pol_legacy_response_v0",
        "title": "Archived Protocol: 2024 Legacy Emergency Handling (RETIRED)",
        "category": "sop",
        "version": "v0.9.0",
        "jurisdiction_id": None,
        "status": "retired",
        "effective_date": "2024-01-01",
        "sections": [
            {
                "heading": "Section 1: Retired Dispatch SLA",
                "content": "Legacy manual phone dispatch without automated SLA timers. This document is retired and superseded by v1.2.0.",
            }
        ],
        "tags": ["retired", "legacy"],
    },
]


class RAGService:
    """RAG Service for Authority Copilot operational documentation."""

    async def init_indexes(self) -> None:
        db = get_database()
        coll = db["copilot_knowledge_docs"]
        await coll.create_index("document_id", unique=True)
        await coll.create_index("status")
        await coll.create_index("jurisdiction_id")
        await coll.create_index("category")
        await self.seed_default_documents()

    async def seed_default_documents(self) -> None:
        db = get_database()
        coll = db["copilot_knowledge_docs"]
        for doc in DEFAULT_SEEDED_DOCS:
            existing = await coll.find_one({"document_id": doc["document_id"]})
            if not existing:
                doc_obj = KnowledgeDocument(
                    document_id=doc["document_id"],
                    title=doc["title"],
                    category=doc["category"],
                    version=doc["version"],
                    jurisdiction_id=doc["jurisdiction_id"],
                    status=doc["status"],
                    effective_date=doc["effective_date"],
                    sections=doc["sections"],
                    tags=doc["tags"],
                )
                await coll.insert_one(doc_obj.to_dict())
                logger.info(f"Seeded knowledge document: {doc['document_id']}")

    async def search(
        self,
        query: str,
        jurisdiction_id: Optional[str] = None,
        include_retired: bool = False,
        limit: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using hybrid semantic + keyword matching with
        strict jurisdiction filtering and retired-policy exclusion.
        """
        db = get_database()
        coll = db["copilot_knowledge_docs"]
        if await coll.count_documents({}) == 0:
            await self.seed_default_documents()

        # Filter criteria: active status (unless specifically asking for retired), matching jurisdiction or universal
        query_filter: Dict[str, Any] = {}
        if not include_retired:
            query_filter["status"] = "active"

        if jurisdiction_id:
            query_filter["$or"] = [{"jurisdiction_id": None}, {"jurisdiction_id": jurisdiction_id}]
        else:
            query_filter["jurisdiction_id"] = None

        cursor = coll.find(query_filter)
        docs = await cursor.to_list(length=50)


        query_terms = set(query.lower().split())
        scored_results: List[Dict[str, Any]] = []

        llm = get_llm_provider()
        query_embedding = await llm.embed(query)

        for doc in docs:
            title = doc.get("title", "")
            version = doc.get("version", "v1")
            sections = doc.get("sections", [])

            for sec in sections:
                heading = sec.get("heading", "")
                content = sec.get("content", "")
                text_to_match = f"{title} {heading} {content}".lower()

                # Keyword overlap score
                matched_terms = [t for t in query_terms if t in text_to_match]
                kw_score = len(matched_terms) / max(len(query_terms), 1)

                # Semantic cosine similarity score
                sec_embedding = await llm.embed(f"{heading} {content}")
                dot_product = sum(a * b for a, b in zip(query_embedding, sec_embedding))

                total_score = (kw_score * 0.6) + (dot_product * 0.4)

                if total_score > 0.05 or kw_score > 0.1:
                    scored_results.append({
                        "document_id": doc["document_id"],
                        "title": title,
                        "version": version,
                        "category": doc.get("category", "sop"),
                        "section": heading,
                        "snippet": content,
                        "score": total_score,
                        "status": doc.get("status", "active"),
                        "effective_date": doc.get("effective_date"),
                    })

        # Sort descending by relevance score
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:limit]


rag_service = RAGService()
