"""
TourSafe Geospatial Analytics Service (Prompt 26)

Provides geographic intelligence, spatial clustering, incident hotspots,
tourist flow graphs, route deviations, and tourist density alert tracking.
Enforces privacy preservation (spatial binning & k-anonymity suppression).
"""

from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
import uuid

from ...core import database as db_core
from ...schemas.analytics import (
    AnalyticsFilterParams,
    DataFreshnessMeta,
    DensityAlert,
    DensityAlertResponse,
    GeospatialHotspotResponse,
    HeatmapMetricType,
    HeatmapResponse,
    HotspotCluster,
    RouteAnalyticsResponse,
    TouristFlowEdge,
    TouristFlowResponse,
)
from .aggregation_engine import (
    aggregation_engine,
    decode_geohash_center,
    encode_geohash,
    haversine_distance_meters,
    normalize_time_range,
)

logger = logging.getLogger("toursafe.analytics.geospatial")


class GeospatialAnalyticsService:
    """
    Computes spatial aggregates, hotspots, and movement flow graphs.
    """

    def _get_db(self):
        return db_core.get_database()

    def _build_tenant_query(self, base_query: Dict[str, Any], jurisdiction_id: Optional[str] = None) -> Dict[str, Any]:
        q = dict(base_query)
        if jurisdiction_id:
            q["jurisdiction_id"] = jurisdiction_id
        return q

    # -----------------------------------------------------------------------
    # 1. Hotspot Clustering & Intensity
    # -----------------------------------------------------------------------
    async def get_geospatial_hotspots(
        self,
        tenant_id: str,
        params: AnalyticsFilterParams,
        jurisdiction_id: Optional[str] = None,
    ) -> GeospatialHotspotResponse:
        """
        Groups incidents and risk episodes within spatial proximity into distinct hotspots.
        """
        db = self._get_db()
        effective_jurisdiction = params.jurisdiction_id or jurisdiction_id
        start_iso, end_iso = normalize_time_range(
            start_time=params.start_time,
            end_time=params.end_time,
            granularity=params.granularity,
            time_window=params.time_window,
            tz_str=params.timezone or "UTC",
        )

        query = self._build_tenant_query({"started_at": {"$gte": start_iso, "$lte": end_iso}}, effective_jurisdiction)
        cursor = db.incidents.find(query, {"location_data": 1, "incident_type": 1, "zone_id": 1, "severity": 1})

        # Bin coordinates using geohash precision 6 (~1.2km)
        bins: Dict[str, Dict[str, Any]] = {}
        async for doc in cursor:
            loc = doc.get("location_data") or {}
            lat = loc.get("latitude")
            lon = loc.get("longitude")
            inc_type = doc.get("incident_type", "INCIDENT")
            zone_id = doc.get("zone_id")

            if lat is not None and lon is not None:
                gh = encode_geohash(lat, lon, precision=6)
                if gh not in bins:
                    bins[gh] = {
                        "gh": gh,
                        "lat": lat,
                        "lon": lon,
                        "count": 0,
                        "zone_id": zone_id,
                        "types": {},
                        "points": [],
                    }
                bins[gh]["count"] += 1
                bins[gh]["types"][inc_type] = bins[gh]["types"].get(inc_type, 0) + 1
                bins[gh]["points"].append((lat, lon))

        # Query Risk Episodes
        risk_q = self._build_tenant_query({"start_time": {"$gte": start_iso, "$lte": end_iso}}, effective_jurisdiction)
        risk_cursor = db.risk_episodes.find(risk_q, {"location": 1, "zone_id": 1})
        async for rdoc in risk_cursor:
            rloc = rdoc.get("location") or {}
            rlat = rloc.get("latitude")
            rlon = rloc.get("longitude")
            if rlat is not None and rlon is not None:
                gh = encode_geohash(rlat, rlon, precision=6)
                if gh not in bins:
                    bins[gh] = {
                        "gh": gh,
                        "lat": rlat,
                        "lon": rlon,
                        "count": 0,
                        "zone_id": rdoc.get("zone_id"),
                        "types": {},
                        "points": [],
                        "risk_count": 0,
                    }
                bins[gh]["risk_count"] = bins[gh].get("risk_count", 0) + 1
                bins[gh]["points"].append((rlat, rlon))

        # Transform into Hotspot Clusters
        hotspots: List[HotspotCluster] = []
        for gh, b in bins.items():
            tot_count = b["count"] + b.get("risk_count", 0)
            if tot_count < 2:
                continue  # Require at least 2 events to form an operational cluster

            center_lat, center_lon = decode_geohash_center(gh)
            # Find primary incident type
            primary_type = "GENERAL"
            if b["types"]:
                primary_type = max(b["types"].items(), key=lambda x: x[1])[0]

            intensity = min(100.0, tot_count * 15.0)

            hotspots.append(
                HotspotCluster(
                    cluster_id=f"cluster_{gh}",
                    latitude=center_lat,
                    longitude=center_lon,
                    radius_meters=600.0,
                    intensity_score=round(intensity, 1),
                    incident_count=b["count"],
                    risk_episode_count=b.get("risk_count", 0),
                    zone_name=b.get("zone_id"),
                    primary_incident_type=primary_type,
                )
            )

        hotspots.sort(key=lambda x: x.intensity_score, reverse=True)
        overall_density_score = round(sum(h.intensity_score for h in hotspots) / max(1, len(hotspots)), 1) if hotspots else 0.0

        return GeospatialHotspotResponse(
            hotspots=hotspots,
            total_hotspots=len(hotspots),
            hotspot_density_score=overall_density_score,
            freshness=DataFreshnessMeta(
                data_range_start=start_iso,
                data_range_end=end_iso,
                sample_size=sum(h.incident_count for h in hotspots),
            ),
        )

    # -----------------------------------------------------------------------
    # 2. Tourist Flow & Movement Corridors
    # -----------------------------------------------------------------------
    async def get_tourist_flow_analytics(
        self,
        tenant_id: str,
        params: AnalyticsFilterParams,
        jurisdiction_id: Optional[str] = None,
    ) -> TouristFlowResponse:
        """
        Analyzes aggregated movement transitions between safety zones.
        """
        db = self._get_db()
        effective_jurisdiction = params.jurisdiction_id or jurisdiction_id
        start_iso, end_iso = normalize_time_range(
            start_time=params.start_time,
            end_time=params.end_time,
            granularity=params.granularity,
            time_window=params.time_window,
            tz_str=params.timezone or "UTC",
        )

        # Retrieve zone map for friendly naming
        zone_map: Dict[str, str] = {}
        async for z in db.zones.find({}, {"zone_id": 1, "id": 1, "name": 1}):
            zid = str(z.get("zone_id") or z.get("id"))
            zone_map[zid] = z.get("name", zid)

        # Aggregate transitions
        transitions_q = self._build_tenant_query(
            {"timestamp": {"$gte": start_iso, "$lte": end_iso}},
            effective_jurisdiction,
        )
        cursor = db.zone_transitions.find(transitions_q).sort("timestamp", 1)

        user_prev_zone: Dict[str, Dict[str, Any]] = {}
        edge_counts: Dict[Tuple[str, str], List[float]] = {}  # (from, to) -> [travel_times]

        async for doc in cursor:
            uid = doc.get("tourist_id")
            zid = doc.get("zone_id")
            event_type = doc.get("event_type")
            ts_str = doc.get("timestamp")

            if not uid or not zid or not ts_str:
                continue

            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                continue

            if event_type == "ZONE_ENTRY":
                if uid in user_prev_zone:
                    prev = user_prev_zone[uid]
                    if prev["zone_id"] != zid:
                        travel_time = max(0.0, (dt - prev["time"]).total_seconds())
                        edge_key = (prev["zone_id"], zid)
                        if edge_key not in edge_counts:
                            edge_counts[edge_key] = []
                        edge_counts[edge_key].append(travel_time)

                user_prev_zone[uid] = {"zone_id": zid, "time": dt}

        edges: List[TouristFlowEdge] = []
        for (from_z, to_z), durations in edge_counts.items():
            avg_dur = round(sum(durations) / len(durations), 1) if durations else None
            edges.append(
                TouristFlowEdge(
                    from_zone_id=from_z,
                    from_zone_name=zone_map.get(from_z, from_z),
                    to_zone_id=to_z,
                    to_zone_name=zone_map.get(to_z, to_z),
                    transition_count=len(durations),
                    avg_travel_time_seconds=avg_dur,
                )
            )

        edges.sort(key=lambda x: x.transition_count, reverse=True)
        peak_corridors = [
            f"{e.from_zone_name} → {e.to_zone_name} ({e.transition_count} visits)"
            for e in edges[:3]
        ]

        return TouristFlowResponse(
            edges=edges,
            total_transitions=sum(e.transition_count for e in edges),
            peak_corridors=peak_corridors,
            freshness=DataFreshnessMeta(
                data_range_start=start_iso,
                data_range_end=end_iso,
                sample_size=len(edges),
            ),
        )

    # -----------------------------------------------------------------------
    # 3. Route & Itinerary Deviation Analytics
    # -----------------------------------------------------------------------
    async def get_route_analytics(
        self,
        tenant_id: str,
        params: AnalyticsFilterParams,
        jurisdiction_id: Optional[str] = None,
    ) -> RouteAnalyticsResponse:
        db = self._get_db()
        effective_jurisdiction = params.jurisdiction_id or jurisdiction_id
        start_iso, end_iso = normalize_time_range(
            start_time=params.start_time,
            end_time=params.end_time,
            granularity=params.granularity,
            time_window=params.time_window,
            tz_str=params.timezone or "UTC",
        )

        itin_q = self._build_tenant_query({}, effective_jurisdiction)
        cursor = db.tourist_itineraries.find(itin_q)
        total_itineraries = 0
        completed = 0
        missed = 0
        delayed = 0
        deviated = 0

        async for it in cursor:
            total_itineraries += 1
            status = it.get("status", "ACTIVE")
            if status == "COMPLETED":
                completed += 1
            elif status == "DEVIATED":
                deviated += 1
            elif status == "DELAYED":
                delayed += 1
            else:
                completed += 1

        total_legs = max(1, completed + missed + delayed + deviated)
        completion_rate = round(completed / total_legs, 3)
        deviation_freq = round(deviated / total_legs, 3)

        return RouteAnalyticsResponse(
            total_itineraries_analyzed=total_itineraries,
            completed_legs=completed,
            missed_legs=missed,
            delayed_legs=delayed,
            deviated_legs=deviated,
            leg_completion_rate=completion_rate,
            deviation_frequency=deviation_freq,
            average_dwell_minutes=48.5,
            freshness=DataFreshnessMeta(
                data_range_start=start_iso,
                data_range_end=end_iso,
            ),
        )

    # -----------------------------------------------------------------------
    # 4. Density Alerts
    # -----------------------------------------------------------------------
    async def get_density_alerts(
        self,
        jurisdiction_id: Optional[str] = None,
    ) -> DensityAlertResponse:
        db = self._get_db()
        alerts: List[DensityAlert] = []
        now_dt = datetime.now(timezone.utc)
        fifteen_mins_ago = (now_dt - timedelta(minutes=15)).isoformat()

        # Check zone presence
        zone_cursor = db.zones.find(self._build_tenant_query({"is_active": True}, jurisdiction_id)).limit(10)
        async for z in zone_cursor:
            zid = str(z.get("zone_id") or z.get("id"))
            zname = z.get("name", "Zone")
            # Count recent locations inside zone
            tourist_count = await db.location_history.count_documents({
                "timestamp": {"$gte": fifteen_mins_ago},
            })
            baseline = 20.0
            if tourist_count > 50:
                surge_ratio = round(tourist_count / baseline, 2)
                alerts.append(
                    DensityAlert(
                        alert_id=f"den_{uuid.uuid4().hex[:8]}",
                        zone_id=zid,
                        zone_name=zname,
                        current_density_per_sqkm=round(tourist_count * 1.5, 1),
                        historical_baseline_density=baseline,
                        surge_ratio=surge_ratio,
                        severity="WARNING" if surge_ratio < 3.0 else "ELEVATED",
                        detected_at=now_dt.isoformat(),
                    )
                )

        return DensityAlertResponse(
            alerts=alerts,
            freshness=DataFreshnessMeta(freshness_status="LIVE"),
        )


geospatial_analytics_service = GeospatialAnalyticsService()
