"""
TourSafe Response Analytics & Escalation Intelligence Service (Prompt 26)

Analyzes emergency response operational performance, responder workload,
SLA breakdowns (time to acknowledge, dispatch, accept, arrive, resolve),
detailed escalation levels and root causes, and capability-based demand.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

from ...core import database as db_core
from ...schemas.analytics import (
    AnalyticsFilterParams,
    DataFreshnessMeta,
    EscalationAnalyticsResponse,
    EscalationLevelCount,
    EscalationReasonBreakdown,
    IncidentDurationMetrics,
    ResponderAnalyticsResponse,
    TimeGranularity,
)
from .aggregation_engine import (
    compute_duration_percentiles,
    normalize_time_range,
)

logger = logging.getLogger("toursafe.analytics.response")


class ResponseAnalyticsService:
    """
    Computes SLA performance percentiles, responder operational statistics, and escalation breakdowns.
    """

    def _get_db(self):
        return db_core.get_database()

    def _build_tenant_query(self, base_query: Dict[str, Any], jurisdiction_id: Optional[str] = None) -> Dict[str, Any]:
        q = dict(base_query)
        if jurisdiction_id:
            q["jurisdiction_id"] = jurisdiction_id
        return q

    # -----------------------------------------------------------------------
    # 1. Responder Operational Statistics & Workload
    # -----------------------------------------------------------------------
    async def get_responder_analytics(
        self,
        tenant_id: str,
        params: AnalyticsFilterParams,
        jurisdiction_id: Optional[str] = None,
    ) -> ResponderAnalyticsResponse:
        db = self._get_db()
        effective_jurisdiction = params.jurisdiction_id or jurisdiction_id
        start_iso, end_iso = normalize_time_range(
            start_time=params.start_time,
            end_time=params.end_time,
            granularity=params.granularity,
            time_window=params.time_window,
            tz_str=params.timezone or "UTC",
        )

        resp_query = self._build_tenant_query({}, effective_jurisdiction)
        if params.responder_id:
            resp_query["responder_id"] = params.responder_id
        if params.unit_id:
            resp_query["unit_id"] = params.unit_id

        resp_col = getattr(db, "responder_profiles", getattr(db, "responders", None))
        assign_col = getattr(db, "responder_assignments", getattr(db, "incident_assignments", None))

        total_responders = await resp_col.count_documents(resp_query) if resp_col is not None else 0
        active_responders = await resp_col.count_documents({**resp_query, "status": {"$in": ["ACTIVE", "AVAILABLE", "ASSIGNED"]}}) if resp_col is not None else 0
        available_responders = await resp_col.count_documents({**resp_query, "$or": [{"status": "AVAILABLE"}, {"status": "ACTIVE", "is_available": True}]}) if resp_col is not None else 0
        assigned_responders = await resp_col.count_documents({**resp_query, "$or": [{"status": "ASSIGNED"}, {"status": "ACTIVE", "is_available": False}]}) if resp_col is not None else 0
        offline_responders = max(0, total_responders - active_responders)

        # Assignments in period
        assign_query = self._build_tenant_query({}, effective_jurisdiction)
        if params.responder_id:
            assign_query["responder_id"] = params.responder_id
        if params.unit_id:
            assign_query["unit_id"] = params.unit_id

        cursor = assign_col.find(assign_query) if assign_col is not None else MockAsyncCursor([])
        assignments = []
        async for doc in cursor:
            assignments.append(doc)

        total_assignments = len(assignments)
        accepted = sum(1 for a in assignments if a.get("status") in ("ACCEPTED", "EN_ROUTE", "ON_SCENE", "COMPLETED", "RESOLVED"))
        completed = sum(1 for a in assignments if a.get("status") in ("COMPLETED", "RESOLVED"))
        rejected = sum(1 for a in assignments if a.get("status") in ("REJECTED", "DECLINED"))
        timed_out = sum(1 for a in assignments if a.get("status") in ("TIMED_OUT", "TIMEOUT"))

        acceptance_rate = round(accepted / max(1, total_assignments), 3) if total_assignments > 0 else 0.0
        rejection_rate = round(rejected / max(1, total_assignments), 3) if total_assignments > 0 else 0.0
        utilization_rate = round(assigned_responders / max(1, active_responders), 3) if active_responders > 0 else 0.0

        # Duration metrics
        resp_times = []
        arr_times = []
        res_times = []
        capability_demand: Dict[str, int] = {
            "MEDICAL": 0,
            "SECURITY": 0,
            "SEARCH_RESCUE": 0,
            "SPECIALIST": 0,
            "GENERAL": 0,
        }

        for a in assignments:
            as_str = a.get("assigned_at") or a.get("created_at")
            ac_str = a.get("accepted_at")
            ar_str = a.get("arrived_at")
            cp_str = a.get("completed_at") or a.get("resolved_at")
            req_cap = a.get("required_capability") or a.get("responder_type") or "GENERAL"
            if req_cap in capability_demand:
                capability_demand[req_cap] += 1
            else:
                capability_demand["GENERAL"] += 1

            if as_str and ac_str:
                try:
                    dt_as = datetime.fromisoformat(as_str.replace("Z", "+00:00"))
                    dt_ac = datetime.fromisoformat(ac_str.replace("Z", "+00:00"))
                    resp_times.append(max(0.0, (dt_ac - dt_as).total_seconds()))
                except Exception:
                    pass

            if as_str and ar_str:
                try:
                    dt_as = datetime.fromisoformat(as_str.replace("Z", "+00:00"))
                    dt_ar = datetime.fromisoformat(ar_str.replace("Z", "+00:00"))
                    arr_times.append(max(0.0, (dt_ar - dt_as).total_seconds()))
                except Exception:
                    pass

            if as_str and cp_str:
                try:
                    dt_as = datetime.fromisoformat(as_str.replace("Z", "+00:00"))
                    dt_cp = datetime.fromisoformat(cp_str.replace("Z", "+00:00"))
                    res_times.append(max(0.0, (dt_cp - dt_as).total_seconds()))
                except Exception:
                    pass

        resp_metrics = compute_duration_percentiles(resp_times)
        arr_metrics = compute_duration_percentiles(arr_times)
        res_metrics = compute_duration_percentiles(res_times)

        # Unit performance
        unit_perf_map: Dict[str, Dict[str, Any]] = {}
        for a in assignments:
            u_id = a.get("unit_id", "UNASSIGNED_UNIT")
            if u_id not in unit_perf_map:
                unit_perf_map[u_id] = {"unit_id": u_id, "assignments_count": 0, "completed_count": 0}
            unit_perf_map[u_id]["assignments_count"] += 1
            if a.get("status") in ("COMPLETED", "RESOLVED"):
                unit_perf_map[u_id]["completed_count"] += 1

        unit_performance = list(unit_perf_map.values())

        return ResponderAnalyticsResponse(
            total_responders=total_responders,
            active_responders=active_responders,
            available_responders=available_responders,
            assigned_responders=assigned_responders,
            offline_responders=offline_responders,
            total_assignments=total_assignments,
            accepted_assignments=accepted,
            completed_assignments=completed,
            rejected_assignments=rejected,
            timeout_assignments=timed_out,
            rejection_rate=rejection_rate,
            acceptance_rate=acceptance_rate,
            utilization_rate=utilization_rate,
            p50_response_time_seconds=resp_metrics.p50_seconds,
            median_response_time_seconds=resp_metrics.median_seconds,
            p75_response_time_seconds=resp_metrics.p75_seconds,
            p90_response_time_seconds=resp_metrics.p90_seconds,
            p95_response_time_seconds=resp_metrics.p95_seconds,
            p50_arrival_time_seconds=arr_metrics.p50_seconds,
            p90_arrival_time_seconds=arr_metrics.p90_seconds,
            p50_resolution_time_seconds=res_metrics.p50_seconds,
            p90_resolution_time_seconds=res_metrics.p90_seconds,
            assignments_by_responder_type={},
            capability_demand=capability_demand,
            unit_performance=unit_performance,
            freshness=DataFreshnessMeta(
                data_range_start=start_iso,
                data_range_end=end_iso,
                sample_size=total_assignments,
            ),
        )

    # -----------------------------------------------------------------------
    # 2. Escalation Analytics
    # -----------------------------------------------------------------------
    async def get_escalation_analytics(
        self,
        tenant_id: str,
        params: AnalyticsFilterParams,
        jurisdiction_id: Optional[str] = None,
    ) -> EscalationAnalyticsResponse:
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
        cursor = db.incidents.find(query)

        total_eligible = 0
        escalated_count = 0
        level_map: Dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
        reason_map: Dict[str, int] = {
            "NO_ACKNOWLEDGEMENT": 0,
            "NO_RESPONDER_AVAILABLE": 0,
            "SLA_TIMEOUT": 0,
            "SEVERITY_UPGRADE": 0,
            "POLICY_TRIGGER": 0,
            "MANUAL_OVERRIDE": 0,
        }
        time_to_escalations: List[float] = []
        resolved_post_escalation = 0

        async for inc in cursor:
            total_eligible += 1
            lvl = int(inc.get("escalation_level") or 0)
            if lvl in level_map:
                level_map[lvl] += 1
            else:
                level_map[lvl] = 1

            if lvl > 0 or inc.get("status") == "ESCALATED":
                escalated_count += 1
                r = inc.get("escalation_reason") or "SLA_TIMEOUT"
                if r in reason_map:
                    reason_map[r] += 1
                else:
                    reason_map["POLICY_TRIGGER"] += 1

                st_str = inc.get("started_at")
                esc_str = inc.get("escalated_at")
                if st_str and esc_str:
                    try:
                        dt_s = datetime.fromisoformat(st_str.replace("Z", "+00:00"))
                        dt_e = datetime.fromisoformat(esc_str.replace("Z", "+00:00"))
                        time_to_escalations.append(max(0.0, (dt_e - dt_s).total_seconds()))
                    except Exception:
                        pass

                if inc.get("status") in ("RESOLVED", "CLOSED"):
                    resolved_post_escalation += 1

        levels_list = [
            EscalationLevelCount(level=0, level_name="Level 0: Initial Dispatch", count=level_map.get(0, 0)),
            EscalationLevelCount(level=1, level_name="Level 1: Supervisor Escalation", count=level_map.get(1, 0)),
            EscalationLevelCount(level=2, level_name="Level 2: Multi-Agency Dispatch", count=level_map.get(2, 0)),
            EscalationLevelCount(level=3, level_name="Level 3: Regional Command", count=level_map.get(3, 0)),
        ]

        reasons_list = [
            EscalationReasonBreakdown(
                reason=k,
                count=v,
                percentage=round(v / max(1, escalated_count) * 100.0, 1) if escalated_count > 0 else 0.0,
            )
            for k, v in reason_map.items()
        ]

        esc_duration_metrics = compute_duration_percentiles(time_to_escalations)
        esc_rate = round(escalated_count / max(1, total_eligible), 3) if total_eligible > 0 else 0.0
        res_post_rate = round(resolved_post_escalation / max(1, escalated_count), 3) if escalated_count > 0 else 0.0

        return EscalationAnalyticsResponse(
            total_eligible_incidents=total_eligible,
            total_escalated_incidents=escalated_count,
            escalation_rate=esc_rate,
            levels=levels_list,
            reasons=reasons_list,
            time_to_escalation=esc_duration_metrics,
            resolution_post_escalation_rate=res_post_rate,
            freshness=DataFreshnessMeta(
                data_range_start=start_iso,
                data_range_end=end_iso,
                sample_size=total_eligible,
            ),
        )


response_analytics_service = ResponseAnalyticsService()
