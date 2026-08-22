"""
TourSafe Organization & Jurisdiction Governance Service.
Manages:
- Government and agency organizations (Police, EMS, Tourism Boards, National Parks)
- Geographic jurisdictions with RFC 7946 GeoJSON boundary verification
- Geometry validation, self-intersection / overlap conflict analysis
- Cross-jurisdiction operational policies and explicit ownership rules
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from pymongo import ASCENDING, IndexModel

from ...core.database import get_database
from ...core.geo_validation import validate_zone_geometry, GeoValidationError
from ...models.governance import (
    AuditAction,
    Jurisdiction,
    JurisdictionStatus,
    Organization,
    OrganizationStatus,
    OrganizationType,
)
from ...schemas.governance import (
    JurisdictionBoundaryValidation,
    JurisdictionCreateRequest,
    JurisdictionResponse,
    JurisdictionUpdateRequest,
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
    OverlapAnalysisResult,
)
from .audit_service import audit_service


class JurisdictionService:
    def __init__(self):
        self.orgs_collection = "governance_organizations"
        self.jurisdictions_collection = "governance_jurisdictions"

    def _get_orgs_collection(self):
        return get_database()[self.orgs_collection]

    def _get_jurisdictions_collection(self):
        return get_database()[self.jurisdictions_collection]

    async def init_indexes(self):
        """Initializes geospatial and unique indexes for organizations and jurisdictions."""
        try:
            orgs_coll = self._get_orgs_collection()
            await orgs_coll.create_indexes([
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("code", ASCENDING)], unique=True),
                IndexModel([("status", ASCENDING)]),
            ])

            jur_coll = self._get_jurisdictions_collection()
            await jur_coll.create_indexes([
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("code", ASCENDING)], unique=True),
                IndexModel([("organization_id", ASCENDING)]),
                IndexModel([("boundary", "2dsphere")]),
                IndexModel([("status", ASCENDING)]),
            ])
        except Exception as e:
            print(f"⚠️ JurisdictionService index initialization note: {e}")

    # -----------------------------------------------------------------------
    # Organization Management
    # -----------------------------------------------------------------------

    async def create_organization(
        self,
        req: OrganizationCreateRequest,
        actor_id: str,
        actor_role: str,
    ) -> OrganizationResponse:
        coll = self._get_orgs_collection()
        existing = await coll.find_one({"code": req.code.strip().upper()})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization with code '{req.code}' already exists.",
            )

        org = Organization(
            name=req.name.strip(),
            code=req.code.strip().upper(),
            type=req.type,
            jurisdiction_ids=req.jurisdiction_ids,
            status=OrganizationStatus.ACTIVE,
            contact_email=str(req.contact_email) if req.contact_email else None,
            contact_phone=req.contact_phone,
            address=req.address,
            metadata=req.metadata,
        )

        doc = org.to_dict()
        await coll.insert_one(doc)

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.CREATE,
            resource_type="ORGANIZATION",
            resource_id=org.id,
            after_state=doc,
            change_reason=f"Created organization {org.name} ({org.code})",
        )

        return OrganizationResponse(**doc)

    async def list_organizations(
        self,
        status_filter: Optional[OrganizationStatus] = None,
        type_filter: Optional[OrganizationType] = None,
    ) -> List[OrganizationResponse]:
        coll = self._get_orgs_collection()
        query: Dict[str, Any] = {}
        if status_filter:
            query["status"] = status_filter.value if hasattr(status_filter, "value") else str(status_filter)
        if type_filter:
            query["type"] = type_filter.value if hasattr(type_filter, "value") else str(type_filter)

        cursor = coll.find(query, {"_id": 0}).sort("name", ASCENDING)
        res = []
        async for doc in cursor:
            res.append(OrganizationResponse(**doc))
        return res

    async def get_organization(self, org_id: str) -> Optional[OrganizationResponse]:
        coll = self._get_orgs_collection()
        doc = await coll.find_one({"id": org_id}, {"_id": 0})
        if not doc:
            return None
        return OrganizationResponse(**doc)

    async def update_organization(
        self,
        org_id: str,
        req: OrganizationUpdateRequest,
        actor_id: str,
        actor_role: str,
    ) -> OrganizationResponse:
        coll = self._get_orgs_collection()
        existing = await coll.find_one({"id": org_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Organization {org_id} not found")

        updates: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if req.name is not None:
            updates["name"] = req.name.strip()
        if req.type is not None:
            updates["type"] = req.type.value if hasattr(req.type, "value") else str(req.type)
        if req.jurisdiction_ids is not None:
            updates["jurisdiction_ids"] = req.jurisdiction_ids
        if req.status is not None:
            updates["status"] = req.status.value if hasattr(req.status, "value") else str(req.status)
        if req.contact_email is not None:
            updates["contact_email"] = str(req.contact_email)
        if req.contact_phone is not None:
            updates["contact_phone"] = req.contact_phone
        if req.address is not None:
            updates["address"] = req.address
        if req.metadata is not None:
            updates["metadata"] = req.metadata

        await coll.update_one({"id": org_id}, {"$set": updates})
        updated = await coll.find_one({"id": org_id}, {"_id": 0})

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.EDIT,
            resource_type="ORGANIZATION",
            resource_id=org_id,
            before_state=existing,
            after_state=updated,
            change_reason="Updated organization details",
        )

        return OrganizationResponse(**updated)

    # -----------------------------------------------------------------------
    # Jurisdiction Boundary Validation & Overlap Checks
    # -----------------------------------------------------------------------

    def validate_boundary_geometry(self, boundary: Dict[str, Any]) -> JurisdictionBoundaryValidation:
        """
        Performs strict geospatial validation on GeoJSON polygon / multipolygon boundaries.
        Verifies coordinate bounding ranges, closed linear rings, and computes bounding box.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not isinstance(boundary, dict):
            return JurisdictionBoundaryValidation(
                valid=False,
                geometry_type="UNKNOWN",
                coordinates_count=0,
                bounding_box=[-180, -90, 180, 90],
                errors=["Boundary must be a valid GeoJSON object dictionary."],
            )

        geom_type = boundary.get("type", "")
        if geom_type not in ("Polygon", "MultiPolygon"):
            errors.append(f"Invalid geometry type '{geom_type}'. Only 'Polygon' and 'MultiPolygon' are supported for jurisdictions.")
            return JurisdictionBoundaryValidation(
                valid=False,
                geometry_type=geom_type or "INVALID",
                coordinates_count=0,
                bounding_box=[-180, -90, 180, 90],
                errors=errors,
            )

        coords = boundary.get("coordinates", [])
        if not coords:
            errors.append("Boundary coordinates array is empty.")
            return JurisdictionBoundaryValidation(
                valid=False,
                geometry_type=geom_type,
                coordinates_count=0,
                bounding_box=[-180, -90, 180, 90],
                errors=errors,
            )

        all_points = []
        if geom_type == "Polygon":
            for ring_idx, ring in enumerate(coords):
                if len(ring) < 4:
                    errors.append(f"Polygon ring {ring_idx} has {len(ring)} points; must have at least 4 (closed ring).")
                elif ring[0] != ring[-1]:
                    errors.append(f"Polygon ring {ring_idx} is not closed (first and last coordinate must match).")
                for pt in ring:
                    if len(pt) < 2:
                        errors.append("Coordinate pair must contain [lon, lat].")
                        continue
                    lon, lat = pt[0], pt[1]
                    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                        errors.append(f"Coordinate [{lon}, {lat}] outside valid WGS-84 ranges.")
                    all_points.append((lon, lat))
        elif geom_type == "MultiPolygon":
            for poly_idx, poly in enumerate(coords):
                for ring_idx, ring in enumerate(poly):
                    if len(ring) < 4:
                        errors.append(f"MultiPolygon {poly_idx} ring {ring_idx} has {len(ring)} points; must have at least 4.")
                    elif ring[0] != ring[-1]:
                        errors.append(f"MultiPolygon {poly_idx} ring {ring_idx} is not closed.")
                    for pt in ring:
                        if len(pt) < 2:
                            errors.append("Coordinate pair must contain [lon, lat].")
                            continue
                        lon, lat = pt[0], pt[1]
                        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                            errors.append(f"Coordinate [{lon}, {lat}] outside valid WGS-84 ranges.")
                        all_points.append((lon, lat))

        if not all_points or errors:
            return JurisdictionBoundaryValidation(
                valid=False,
                geometry_type=geom_type,
                coordinates_count=len(all_points),
                bounding_box=[-180, -90, 180, 90],
                errors=errors,
                warnings=warnings,
            )

        min_lon = min(p[0] for p in all_points)
        max_lon = max(p[0] for p in all_points)
        min_lat = min(p[1] for p in all_points)
        max_lat = max(p[1] for p in all_points)

        # Check for degenerate boundaries (zero area)
        if abs(max_lon - min_lon) < 1e-6 or abs(max_lat - min_lat) < 1e-6:
            errors.append("Boundary geometry has zero or near-zero surface area (degenerate coordinates).")

        return JurisdictionBoundaryValidation(
            valid=len(errors) == 0,
            geometry_type=geom_type,
            coordinates_count=len(all_points),
            bounding_box=[min_lon, min_lat, max_lon, max_lat],
            errors=errors,
            warnings=warnings,
        )

    def calculate_centroid(self, boundary: Dict[str, Any]) -> Dict[str, Any]:
        """Computes approximate centroid for quick map positioning."""
        coords = boundary.get("coordinates", [])
        geom_type = boundary.get("type", "")
        pts = []
        if geom_type == "Polygon":
            for ring in coords:
                pts.extend(ring)
        elif geom_type == "MultiPolygon":
            for poly in coords:
                for ring in poly:
                    pts.extend(ring)

        if not pts:
            return {"type": "Point", "coordinates": [0.0, 0.0]}

        avg_lon = sum(p[0] for p in pts) / len(pts)
        avg_lat = sum(p[1] for p in pts) / len(pts)
        return {"type": "Point", "coordinates": [round(avg_lon, 6), round(avg_lat, 6)]}

    # -----------------------------------------------------------------------
    # Jurisdiction CRUD
    # -----------------------------------------------------------------------

    async def create_jurisdiction(
        self,
        req: JurisdictionCreateRequest,
        actor_id: str,
        actor_role: str,
    ) -> JurisdictionResponse:
        coll = self._get_jurisdictions_collection()
        org_coll = self._get_orgs_collection()

        # Validate organization exists
        org = await org_coll.find_one({"id": req.organization_id})
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent Organization '{req.organization_id}' not found.",
            )

        # Validate boundary geometry
        val = self.validate_boundary_geometry(req.boundary)
        if not val.valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Geospatial Boundary Validation Failed: {'; '.join(val.errors)}",
            )

        existing = await coll.find_one({"code": req.code.strip().upper()})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Jurisdiction with code '{req.code}' already exists.",
            )

        centroid = self.calculate_centroid(req.boundary)

        jurisdiction = Jurisdiction(
            organization_id=req.organization_id,
            name=req.name.strip(),
            code=req.code.strip().upper(),
            boundary=req.boundary,
            center=centroid,
            status=JurisdictionStatus.ACTIVE,
            cross_jurisdiction_allowed=req.cross_jurisdiction_allowed,
            auto_dispatch_allowed=req.auto_dispatch_allowed,
            overlap_priority=req.overlap_priority,
            configuration=req.configuration,
        )

        doc = jurisdiction.to_dict()
        await coll.insert_one(doc)

        # Update org jurisdiction_ids
        await org_coll.update_one(
            {"id": req.organization_id},
            {"$addToSet": {"jurisdiction_ids": jurisdiction.id}},
        )

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.CREATE,
            resource_type="JURISDICTION",
            resource_id=jurisdiction.id,
            jurisdiction_id=jurisdiction.id,
            after_state=doc,
            change_reason=f"Created jurisdiction {jurisdiction.name} ({jurisdiction.code})",
        )

        return JurisdictionResponse(**doc)

    async def list_jurisdictions(
        self,
        organization_id: Optional[str] = None,
        status_filter: Optional[JurisdictionStatus] = None,
    ) -> List[JurisdictionResponse]:
        coll = self._get_jurisdictions_collection()
        query: Dict[str, Any] = {}
        if organization_id:
            query["organization_id"] = organization_id
        if status_filter:
            query["status"] = status_filter.value if hasattr(status_filter, "value") else str(status_filter)

        cursor = coll.find(query, {"_id": 0}).sort("name", ASCENDING)
        res = []
        async for doc in cursor:
            res.append(JurisdictionResponse(**doc))
        return res

    async def get_jurisdiction(self, jurisdiction_id: str) -> Optional[JurisdictionResponse]:
        coll = self._get_jurisdictions_collection()
        doc = await coll.find_one({"id": jurisdiction_id}, {"_id": 0})
        if not doc:
            return None
        return JurisdictionResponse(**doc)

    async def update_jurisdiction(
        self,
        jurisdiction_id: str,
        req: JurisdictionUpdateRequest,
        actor_id: str,
        actor_role: str,
    ) -> JurisdictionResponse:
        coll = self._get_jurisdictions_collection()
        existing = await coll.find_one({"id": jurisdiction_id}, {"_id": 0})
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Jurisdiction {jurisdiction_id} not found",
            )

        updates: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if req.name is not None:
            updates["name"] = req.name.strip()
        if req.status is not None:
            updates["status"] = req.status.value if hasattr(req.status, "value") else str(req.status)
        if req.cross_jurisdiction_allowed is not None:
            updates["cross_jurisdiction_allowed"] = req.cross_jurisdiction_allowed
        if req.auto_dispatch_allowed is not None:
            updates["auto_dispatch_allowed"] = req.auto_dispatch_allowed
        if req.overlap_priority is not None:
            updates["overlap_priority"] = req.overlap_priority
        if req.configuration is not None:
            updates["configuration"] = req.configuration

        if req.boundary is not None:
            val = self.validate_boundary_geometry(req.boundary)
            if not val.valid:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid updated boundary: {'; '.join(val.errors)}",
                )
            updates["boundary"] = req.boundary
            updates["center"] = self.calculate_centroid(req.boundary)

        await coll.update_one({"id": jurisdiction_id}, {"$set": updates})
        updated = await coll.find_one({"id": jurisdiction_id}, {"_id": 0})

        await audit_service.log_action(
            actor_id=actor_id,
            actor_role=actor_role,
            action=AuditAction.EDIT,
            resource_type="JURISDICTION",
            resource_id=jurisdiction_id,
            jurisdiction_id=jurisdiction_id,
            before_state=existing,
            after_state=updated,
            change_reason="Updated jurisdiction boundary or policy settings",
        )

        return JurisdictionResponse(**updated)

    async def analyze_overlap(self, boundary: Dict[str, Any], exclude_jurisdiction_id: Optional[str] = None) -> OverlapAnalysisResult:
        """
        Analyzes whether a boundary overlaps with existing jurisdictions or zones in the system.
        """
        jur_coll = self._get_jurisdictions_collection()
        zones_coll = get_database()["zones"]

        val = self.validate_boundary_geometry(boundary)
        if not val.valid:
            return OverlapAnalysisResult(
                has_overlap=False,
                overlapping_jurisdictions=[],
                overlapping_zones=[],
                conflicts=val.errors,
            )

        query: Dict[str, Any] = {
            "boundary": {
                "$geoIntersects": {
                    "$geometry": boundary,
                }
            },
            "status": "ACTIVE",
        }
        if exclude_jurisdiction_id:
            query["id"] = {"$ne": exclude_jurisdiction_id}

        overlapping_jurisdictions = []
        try:
            cursor = jur_coll.find(query, {"_id": 0, "id": 1, "name": 1, "code": 1, "overlap_priority": 1, "cross_jurisdiction_allowed": 1})
            async for doc in cursor:
                overlapping_jurisdictions.append(doc)
        except Exception as e:
            print(f"⚠️ Geo overlap query note: {e}")

        # Check overlapping zones
        overlapping_zones = []
        try:
            cursor_z = zones_coll.find({
                "boundary": {
                    "$geoIntersects": {
                        "$geometry": boundary,
                    }
                }
            }, {"_id": 0, "id": 1, "name": 1, "zone_type": 1, "risk_level": 1})
            async for doc in cursor_z:
                overlapping_zones.append(doc)
        except Exception as e:
            print(f"⚠️ Zone overlap query note: {e}")

        conflicts = []
        if len(overlapping_jurisdictions) > 0:
            for oj in overlapping_jurisdictions:
                if not oj.get("cross_jurisdiction_allowed", False):
                    conflicts.append(
                        f"Overlaps with jurisdiction '{oj.get('name')}' (Priority {oj.get('overlap_priority', 10)}) which forbids cross-jurisdiction operations."
                    )

        return OverlapAnalysisResult(
            has_overlap=len(overlapping_jurisdictions) > 0 or len(overlapping_zones) > 0,
            overlapping_jurisdictions=overlapping_jurisdictions,
            overlapping_zones=overlapping_zones,
            conflicts=conflicts,
        )

    # -----------------------------------------------------------------------
    # Seed Initial Default Organizations & Jurisdictions (Development/Base)
    # -----------------------------------------------------------------------

    async def seed_defaults(self) -> int:
        """Seeds initial default authority organizations and jurisdictions if database is empty."""
        coll_org = self._get_orgs_collection()
        coll_jur = self._get_jurisdictions_collection()

        count = await coll_org.count_documents({})
        if count > 0:
            return 0

        # NYC Metropolitan Safety & Tourism Police Command
        org1 = Organization(
            id="org_metro_safety_01",
            name="Metropolitan Tourist Safety & Emergency Command",
            code="TOURSAFE-METRO-01",
            type=OrganizationType.MUNICIPAL_SAFETY,
            jurisdiction_ids=["jur_central_tourist_01", "jur_waterfront_dist_01"],
            status=OrganizationStatus.ACTIVE,
            contact_email="command@toursafe.gov.internal",
            contact_phone="+1-800-555-SAFE",
            address="100 Government Center Plaza, Suite 400",
            metadata={"department": "Public Safety & Tourism Oversight", "region": "Metro Central"},
        )
        await coll_org.insert_one(org1.to_dict())

        # Seed Jurisdiction 1 (Central Tourist District)
        jur1_boundary = {
            "type": "Polygon",
            "coordinates": [[
                [-74.0150, 40.7050],
                [-73.9750, 40.7050],
                [-73.9750, 40.7650],
                [-74.0150, 40.7650],
                [-74.0150, 40.7050],
            ]]
        }
        jur1 = Jurisdiction(
            id="jur_central_tourist_01",
            organization_id=org1.id,
            name="Central Tourist & Historic District",
            code="JUR-METRO-CENTRAL",
            boundary=jur1_boundary,
            center={"type": "Point", "coordinates": [-73.9950, 40.7350]},
            status=JurisdictionStatus.ACTIVE,
            cross_jurisdiction_allowed=True,
            auto_dispatch_allowed=True,
            overlap_priority=20,
            configuration={"dispatch_cooldown_seconds": 60, "priority_band": "CRITICAL"},
        )
        await coll_jur.insert_one(jur1.to_dict())

        # Seed Jurisdiction 2 (Waterfront Harbor District)
        jur2_boundary = {
            "type": "Polygon",
            "coordinates": [[
                [-74.0300, 40.6900],
                [-74.0000, 40.6900],
                [-74.0000, 40.7200],
                [-74.0300, 40.7200],
                [-74.0300, 40.6900],
            ]]
        }
        jur2 = Jurisdiction(
            id="jur_waterfront_dist_01",
            organization_id=org1.id,
            name="Waterfront & Harbor Tourist District",
            code="JUR-METRO-WATERFRONT",
            boundary=jur2_boundary,
            center={"type": "Point", "coordinates": [-74.0150, 40.7050]},
            status=JurisdictionStatus.ACTIVE,
            cross_jurisdiction_allowed=True,
            auto_dispatch_allowed=True,
            overlap_priority=15,
            configuration={"water_rescue_enabled": True},
        )
        await coll_jur.insert_one(jur2.to_dict())

        return 2


jurisdiction_service = JurisdictionService()
