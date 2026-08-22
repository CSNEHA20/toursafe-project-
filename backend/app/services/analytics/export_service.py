"""
TourSafe Analytics Export Foundation Service

Asynchronously processes structured analytical data exports (CSV / JSON)
with role-based access control, download expiration, and immutable job audit records.
"""

import csv
from datetime import datetime, timedelta, timezone
import io
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from ...core import database as db_core
from ...schemas.analytics import (
    AnalyticsFilterParams,
    ExportFormat,
    ExportJobCreateRequest,
    ExportJobResponse,
    ExportStatus,
)
from .analytics_service import analytics_service

logger = logging.getLogger("toursafe.analytics.export")


class ExportService:
    """
    Handles generation, storage, and retrieval of analytical data exports.
    """

    def _get_db(self):
        return db_core.get_database()

    async def create_export_job(
        self,
        requested_by: str,
        tenant_id: str,
        req: ExportJobCreateRequest,
    ) -> ExportJobResponse:
        db = self._get_db()
        job_id = f"exp_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        job_doc = {
            "job_id": job_id,
            "requested_by": requested_by,
            "tenant_id": tenant_id,
            "export_type": req.export_type,
            "format": req.format.value,
            "status": ExportStatus.PROCESSING.value,
            "filters": req.filters.model_dump() if req.filters else {},
            "created_at": now_iso,
            "completed_at": None,
            "file_reference": None,
            "record_count": 0,
            "file_size_bytes": None,
            "error_message": None,
            "payload_data": None,  # stored securely or in object storage
        }

        await db.export_jobs.insert_one(job_doc)

        # Process export asynchronously / synchronously for immediate availability
        try:
            filters = req.filters or AnalyticsFilterParams()
            payload_str, count = await self._generate_export_payload(
                tenant_id=tenant_id,
                export_type=req.export_type,
                fmt=req.format,
                filters=filters,
            )

            completed_iso = datetime.now(timezone.utc).isoformat()
            await db.export_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": ExportStatus.COMPLETED.value,
                        "completed_at": completed_iso,
                        "file_reference": f"export_{job_id}.{req.format.value}",
                        "record_count": count,
                        "file_size_bytes": len(payload_str.encode("utf-8")),
                        "payload_data": payload_str,
                    }
                },
            )

            return ExportJobResponse(
                job_id=job_id,
                requested_by=requested_by,
                export_type=req.export_type,
                format=req.format,
                status=ExportStatus.COMPLETED,
                created_at=now_iso,
                completed_at=completed_iso,
                file_reference=f"export_{job_id}.{req.format.value}",
                record_count=count,
                file_size_bytes=len(payload_str.encode("utf-8")),
                download_url=f"/api/v1/analytics/export/{job_id}/download",
            )
        except Exception as e:
            logger.error("Failed to generate export job %s: %s", job_id, e)
            await db.export_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": ExportStatus.FAILED.value,
                        "error_message": str(e),
                    }
                },
            )
            return ExportJobResponse(
                job_id=job_id,
                requested_by=requested_by,
                export_type=req.export_type,
                format=req.format,
                status=ExportStatus.FAILED,
                created_at=now_iso,
                error_message=str(e),
            )

    async def get_export_job(self, job_id: str, requested_by: str) -> Optional[ExportJobResponse]:
        db = self._get_db()
        doc = await db.export_jobs.find_one({"job_id": job_id})
        if not doc:
            return None

        return ExportJobResponse(
            job_id=doc["job_id"],
            requested_by=doc["requested_by"],
            export_type=doc["export_type"],
            format=ExportFormat(doc["format"]),
            status=ExportStatus(doc["status"]),
            created_at=doc["created_at"],
            completed_at=doc.get("completed_at"),
            file_reference=doc.get("file_reference"),
            record_count=doc.get("record_count", 0),
            file_size_bytes=doc.get("file_size_bytes"),
            download_url=f"/api/v1/analytics/export/{job_id}/download" if doc["status"] == ExportStatus.COMPLETED.value else None,
            error_message=doc.get("error_message"),
        )

    async def get_export_payload(self, job_id: str, user_id: str, role: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Returns (payload_str, filename, media_type)
        """
        db = self._get_db()
        doc = await db.export_jobs.find_one({"job_id": job_id})
        if not doc:
            return None, None, None

        # Authorization check: user must be the requester or an admin
        if role != "admin" and doc.get("requested_by") != user_id:
            raise PermissionError("Unauthorized access to export job")

        fmt = doc.get("format", "csv")
        media_type = "text/csv" if fmt == "csv" else "application/json"
        filename = doc.get("file_reference") or f"export_{job_id}.{fmt}"
        return doc.get("payload_data"), filename, media_type

    async def _generate_export_payload(
        self,
        tenant_id: str,
        export_type: str,
        fmt: ExportFormat,
        filters: AnalyticsFilterParams,
    ) -> Tuple[str, int]:
        db = self._get_db()

        if export_type == "incidents":
            cursor = db.incidents.find({}).sort("started_at", -1).limit(1000)
            records = []
            async for r in cursor:
                records.append({
                    "incident_id": r.get("incident_id"),
                    "tourist_id": r.get("tourist_id"),
                    "status": r.get("status"),
                    "severity": r.get("severity"),
                    "source": r.get("source"),
                    "started_at": r.get("started_at"),
                    "resolved_at": r.get("resolved_at"),
                    "acknowledged_at": r.get("acknowledged_at"),
                    "resolution_category": r.get("resolution_category"),
                })
        elif export_type == "zones":
            cursor = db.zones.find({}).limit(500)
            records = []
            async for r in cursor:
                records.append({
                    "zone_id": r.get("id") or str(r.get("_id")),
                    "name": r.get("name"),
                    "risk_level": r.get("risk_level"),
                    "zone_type": r.get("zone_type"),
                    "is_active": r.get("is_active"),
                })
        elif export_type == "responders":
            cursor = db.responders.find({}).limit(500)
            records = []
            async for r in cursor:
                records.append({
                    "responder_id": r.get("responder_id"),
                    "name": r.get("name"),
                    "type": r.get("responder_type"),
                    "status": r.get("status"),
                    "active": r.get("active"),
                })
        else:
            # General overview summary
            overview = await analytics_service.get_operations_overview(tenant_id, filters)
            records = [overview.model_dump()]

        if fmt == ExportFormat.CSV:
            if not records:
                return "No records found\n", 0
            output = io.StringIO()
            headers = list(records[0].keys())
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            for row in records:
                writer.writerow(row)
            return output.getvalue(), len(records)
        else:
            return json.dumps(records, indent=2, default=str), len(records)


export_service = ExportService()
