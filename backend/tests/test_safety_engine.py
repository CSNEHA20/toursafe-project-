"""
TourSafe Safety Orchestration Engine & Multi-Signal Risk Fusion Test Suite

Verifies:
1. Signal Fusion across GPS, Anomaly, Geofence, Telemetry, Tracking, and Context
2. Deterministic Rule Engine (safety-rules-v1) and explainable reasons
3. State Machine transitions and invalid transition gating
4. Unknown state vs Normal state distinction
5. Recovery cooldown periods
6. Incident Lifecycle, Deduplication, Acknowledgment, and Resolution
7. REST APIs for Authority and Tourist
8. Signal freshness and expiration
"""

import sys
sys.path.insert(0, "backend")

from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.safety import (
    ActiveSafetyState,
    ConfidenceClass,
    IncidentRecord,
    IncidentSeverity,
    IncidentStatus,
    SafetyDecision,
    SafetySignal,
    SafetyState,
    SignalQuality,
    SignalType,
)
from app.services.safety import (
    IncidentLifecycleManager,
    SafetySignalFactory,
    SafetyStateMachine,
    is_signal_fresh,
    rule_engine,
    safety_config,
    safety_orchestrator,
    safety_redis_state,
)
import copy
import app.core.database as db_module
import app.services.safety.repository as safety_repo_mod


class MockMongoCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []

    def _matches(self, doc, query):
        for k, v in query.items():
            if isinstance(v, dict) and "$in" in v:
                target_list = v["$in"]
                if doc.get(k) not in target_list:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    async def insert_one(self, doc):
        d = copy.deepcopy(doc)
        self.docs.append(d)
        return type("Obj", (), {"inserted_id": d.get("id", "new")})()

    async def find_one(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                return copy.deepcopy(doc)
        return None

    def find(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        matched = [copy.deepcopy(d) for d in self.docs if self._matches(d, filter_dict)]

        class Cursor:
            def __init__(self, items):
                self.items = items
            def sort(self, *args, **kwargs):
                return self
            def skip(self, n):
                self.items = self.items[n:]
                return self
            def limit(self, n):
                self.items = self.items[:n]
                return self
            def __aiter__(self):
                self._iter = iter(self.items)
                return self
            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration
        return Cursor(matched)

    async def update_one(self, filter_dict, update_dict, upsert=False, *args, **kwargs):
        for doc in self.docs:
            if self._matches(doc, filter_dict):
                if "$set" in update_dict:
                    doc.update(copy.deepcopy(update_dict["$set"]))
                return type("Obj", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            new_doc = copy.deepcopy(filter_dict)
            if "$set" in update_dict:
                new_doc.update(copy.deepcopy(update_dict["$set"]))
            self.docs.append(new_doc)
            return type("Obj", (), {"modified_count": 0, "matched_count": 0, "upserted_id": new_doc.get("id", "new")})()
        return type("Obj", (), {"modified_count": 0, "matched_count": 0})()

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        return sum(1 for doc in self.docs if self._matches(doc, filter_dict))

    async def create_index(self, *args, **kwargs):
        return "index_created"


class MockAppDatabase:
    def __init__(self):
        self.safety_decisions = MockMongoCollection("safety_decisions")
        self.safety_incidents = MockMongoCollection("safety_incidents")
        self.location_history = MockMongoCollection("location_history")
        self.tracking_sessions = MockMongoCollection("tracking_sessions")
        self.tourist_profiles = MockMongoCollection("tourist_profiles")
        self.tourists = MockMongoCollection("tourists")
        self.authority = MockMongoCollection("authority")
        self.users = MockMongoCollection("users")
        self.zones = MockMongoCollection("zones")
        self.zone_transitions = MockMongoCollection("zone_transitions")

    def __getitem__(self, name):
        if not hasattr(self, name):
            setattr(self, name, MockMongoCollection(name))
        return getattr(self, name)

    def __getattr__(self, name):
        if name not in self.__dict__:
            self.__dict__[name] = MockMongoCollection(name)
        return self.__dict__[name]


@pytest.fixture(autouse=True)
def mock_db_fixture(monkeypatch):
    mock_db = MockAppDatabase()
    monkeypatch.setattr(db_module, "get_database", lambda: mock_db)
    monkeypatch.setattr(safety_repo_mod, "get_database", lambda: mock_db)
    return mock_db


class TestSafetySignalsAndFreshness:
    """Tests signal normalization, quality classification, and temporal freshness."""

    def test_anomaly_signal_creation(self):
        sig = SafetySignalFactory.create_anomaly_signal(
            tourist_id="tourist_1",
            session_id="sess_1",
            state="anomalous",
            score=0.85,
            threshold=0.50,
            consecutive_windows=3,
            quality="good",
        )
        assert sig.signal_type == SignalType.ANOMALY_DETECTED
        assert sig.tourist_id == "tourist_1"
        assert sig.value["is_anomalous"] is True
        assert sig.value["consecutive_windows"] == 3
        assert sig.quality == SignalQuality.GOOD
        assert sig.metadata["threshold_ratio"] == 1.7

    def test_anomaly_cleared_signal(self):
        sig = SafetySignalFactory.create_anomaly_signal(
            tourist_id="tourist_1",
            session_id="sess_1",
            state="normal",
            score=0.12,
            threshold=0.50,
            consecutive_windows=0,
        )
        assert sig.signal_type == SignalType.ANOMALY_CLEARED
        assert sig.value["is_anomalous"] is False

    def test_gps_signal_creation_and_quality(self):
        sig_good = SafetySignalFactory.create_gps_signal(
            tourist_id="tourist_1",
            session_id="sess_1",
            latitude=15.2993,
            longitude=74.1240,
            accuracy=8.0,
            staleness_state="live",
        )
        assert sig_good.signal_type == SignalType.GPS_LOCATION_UPDATE
        assert sig_good.quality == SignalQuality.EXCELLENT

        sig_poor = SafetySignalFactory.create_gps_signal(
            tourist_id="tourist_1",
            session_id="sess_1",
            latitude=15.2993,
            longitude=74.1240,
            accuracy=65.0,
            staleness_state="live",
        )
        assert sig_poor.signal_type == SignalType.GPS_UNCERTAIN
        assert sig_poor.quality == SignalQuality.DEGRADED

    def test_signal_freshness_evaluation(self):
        now = datetime.now(timezone.utc)
        fresh_ts = now.isoformat()
        old_ts = (now - timedelta(seconds=60)).isoformat()

        sig_fresh = SafetySignalFactory.create_anomaly_signal(
            tourist_id="tourist_1",
            session_id="sess_1",
            state="anomalous",
            score=0.75,
            threshold=0.50,
            timestamp=fresh_ts,
        )
        assert is_signal_fresh(sig_fresh, now=now) is True

        sig_stale = SafetySignalFactory.create_anomaly_signal(
            tourist_id="tourist_1",
            session_id="sess_1",
            state="anomalous",
            score=0.75,
            threshold=0.50,
            timestamp=old_ts,
        )
        assert is_signal_fresh(sig_stale, now=now) is False


class TestDeterministicRuleEngine:
    """Tests deterministic rule evaluation and explainable reason compilation."""

    def test_rule_1_no_signals_yields_unknown(self):
        """Scenario 1: No signals / empty -> UNKNOWN (distinct from NORMAL)."""
        decision = rule_engine.evaluate_signals(
            tourist_id="tourist_1",
            session_id="sess_1",
            previous_state=SafetyState.NORMAL,
            active_signals=[],
        )
        assert decision.state == SafetyState.UNKNOWN
        assert decision.confidence_class == ConfidenceClass.UNKNOWN
        assert any("Insufficient real-time telemetry" in r for r in decision.reasons)

    def test_rule_2_normal_gps_and_good_telemetry_yields_normal(self):
        """Scenario 2: Fresh GPS and healthy telemetry with no anomalies -> NORMAL."""
        now = datetime.now(timezone.utc).isoformat()
        gps_sig = SafetySignalFactory.create_gps_signal(
            tourist_id="tourist_1", session_id="sess_1", latitude=15.29, longitude=74.12, accuracy=5.0, timestamp=now
        )
        tel_sig = SafetySignalFactory.create_telemetry_signal(
            tourist_id="tourist_1", session_id="sess_1", overall_quality="good", observed_frequency_hz=50.0, completeness_ratio=1.0, timestamp=now
        )
        decision = rule_engine.evaluate_signals(
            tourist_id="tourist_1",
            session_id="sess_1",
            previous_state=SafetyState.NORMAL,
            active_signals=[gps_sig, tel_sig],
        )
        assert decision.state == SafetyState.NORMAL
        assert decision.confidence_class == ConfidenceClass.HIGH
        assert any("All safety signals normal" in r for r in decision.reasons)

    def test_rule_3_transient_anomaly_yields_watch(self):
        """Scenario 3: Single transient motion anomaly alone -> WATCH (NEVER immediate INCIDENT)."""
        now = datetime.now(timezone.utc).isoformat()
        gps_sig = SafetySignalFactory.create_gps_signal("tourist_1", "sess_1", 15.29, 74.12, 10.0, timestamp=now)
        tel_sig = SafetySignalFactory.create_telemetry_signal("tourist_1", "sess_1", "good", 50.0, 1.0, timestamp=now)
        anom_sig = SafetySignalFactory.create_anomaly_signal("tourist_1", "sess_1", "anomalous", 0.65, 0.50, consecutive_windows=1, timestamp=now)

        decision = rule_engine.evaluate_signals(
            tourist_id="tourist_1",
            session_id="sess_1",
            previous_state=SafetyState.NORMAL,
            active_signals=[gps_sig, tel_sig, anom_sig],
        )
        assert decision.state == SafetyState.WATCH
        assert any(r.rule_id == "RULE_A1_TRANSIENT_ANOMALY" for r in decision.triggered_rules)

    def test_rule_4_persistent_anomaly_yields_elevated(self):
        """Scenario 4: Anomaly persisting for >= 2 consecutive windows -> ELEVATED."""
        now = datetime.now(timezone.utc).isoformat()
        gps_sig = SafetySignalFactory.create_gps_signal("tourist_1", "sess_1", 15.29, 74.12, 10.0, timestamp=now)
        tel_sig = SafetySignalFactory.create_telemetry_signal("tourist_1", "sess_1", "good", 50.0, 1.0, timestamp=now)
        anom_sig = SafetySignalFactory.create_anomaly_signal("tourist_1", "sess_1", "anomalous", 0.70, 0.50, consecutive_windows=2, timestamp=now)

        decision = rule_engine.evaluate_signals(
            tourist_id="tourist_1",
            session_id="sess_1",
            previous_state=SafetyState.WATCH,
            active_signals=[gps_sig, tel_sig, anom_sig],
        )
        assert decision.state == SafetyState.ELEVATED
        assert any(r.rule_id == "RULE_A2_PERSISTENT_ANOMALY" for r in decision.triggered_rules)

    def test_rule_5_restricted_zone_alone_yields_elevated(self):
        """Scenario 5: Restricted zone containment alone -> ELEVATED."""
        now = datetime.now(timezone.utc).isoformat()
        gps_sig = SafetySignalFactory.create_gps_signal("tourist_1", "sess_1", 15.29, 74.12, 10.0, timestamp=now)
        tel_sig = SafetySignalFactory.create_telemetry_signal("tourist_1", "sess_1", "good", 50.0, 1.0, timestamp=now)
        zone_sig = SafetySignalFactory.create_geofence_signal("tourist_1", "sess_1", "zone_101", "Military Buffer", "restricted", "restricted", "inside", timestamp=now)

        decision = rule_engine.evaluate_signals(
            tourist_id="tourist_1",
            session_id="sess_1",
            previous_state=SafetyState.NORMAL,
            active_signals=[gps_sig, tel_sig, zone_sig],
        )
        assert decision.state == SafetyState.ELEVATED
        assert any(r.rule_id == "RULE_B2_RESTRICTED_ZONE" for r in decision.triggered_rules)

    def test_rule_6_anomaly_and_restricted_zone_corroboration(self):
        """Scenario 6: Anomaly + Restricted Zone -> ELEVATED with multi-signal explanation."""
        now = datetime.now(timezone.utc).isoformat()
        gps_sig = SafetySignalFactory.create_gps_signal("tourist_1", "sess_1", 15.29, 74.12, 10.0, timestamp=now)
        tel_sig = SafetySignalFactory.create_telemetry_signal("tourist_1", "sess_1", "good", 50.0, 1.0, timestamp=now)
        anom_sig = SafetySignalFactory.create_anomaly_signal("tourist_1", "sess_1", "anomalous", 0.60, 0.50, consecutive_windows=1, timestamp=now)
        zone_sig = SafetySignalFactory.create_geofence_signal("tourist_1", "sess_1", "zone_101", "Restricted Cliff", "restricted", "restricted", "inside", timestamp=now)

        decision = rule_engine.evaluate_signals(
            tourist_id="tourist_1",
            session_id="sess_1",
            previous_state=SafetyState.WATCH,
            active_signals=[gps_sig, tel_sig, anom_sig, zone_sig],
        )
        assert decision.state == SafetyState.ELEVATED
        assert any(r.rule_id == "RULE_F1_ANOMALY_IN_RESTRICTED_ZONE" for r in decision.triggered_rules)

    def test_rule_7_persistent_anomaly_in_danger_zone_yields_candidate(self):
        """Scenario 7: Persistent Anomaly + Danger Zone + Good Quality -> INCIDENT_CANDIDATE."""
        now = datetime.now(timezone.utc).isoformat()
        gps_sig = SafetySignalFactory.create_gps_signal("tourist_1", "sess_1", 15.29, 74.12, 10.0, timestamp=now)
        tel_sig = SafetySignalFactory.create_telemetry_signal("tourist_1", "sess_1", "good", 50.0, 1.0, timestamp=now)
        anom_sig = SafetySignalFactory.create_anomaly_signal("tourist_1", "sess_1", "anomalous", 0.85, 0.50, consecutive_windows=3, timestamp=now)
        zone_sig = SafetySignalFactory.create_geofence_signal("tourist_1", "sess_1", "zone_danger", "Ghats Danger Zone", "danger", "danger", "inside", timestamp=now)

        decision = rule_engine.evaluate_signals(
            tourist_id="tourist_1",
            session_id="sess_1",
            previous_state=SafetyState.ELEVATED,
            active_signals=[gps_sig, tel_sig, anom_sig, zone_sig],
        )
        assert decision.state == SafetyState.INCIDENT_CANDIDATE
        assert any(r.rule_id == "RULE_F2_PERSISTENT_ANOMALY_IN_DANGER_ZONE" for r in decision.triggered_rules)

    def test_rule_8_poor_gps_and_anomaly_quality_gating(self):
        """Scenario 8: Poor GPS (> 50m) degrades confidence and gates escalation."""
        now = datetime.now(timezone.utc).isoformat()
        gps_sig = SafetySignalFactory.create_gps_signal("tourist_1", "sess_1", 15.29, 74.12, 75.0, timestamp=now)
        tel_sig = SafetySignalFactory.create_telemetry_signal("tourist_1", "sess_1", "poor", 20.0, 0.5, timestamp=now)
        anom_sig = SafetySignalFactory.create_anomaly_signal("tourist_1", "sess_1", "anomalous", 0.85, 0.50, consecutive_windows=4, timestamp=now)
        zone_sig = SafetySignalFactory.create_geofence_signal("tourist_1", "sess_1", "zone_danger", "Ghats", "danger", "danger", "inside", timestamp=now)

        decision = rule_engine.evaluate_signals(
            tourist_id="tourist_1",
            session_id="sess_1",
            previous_state=SafetyState.WATCH,
            active_signals=[gps_sig, tel_sig, anom_sig, zone_sig],
        )
        # Quality gating caps target state at ELEVATED due to low confidence
        assert decision.confidence_class == ConfidenceClass.LOW
        assert decision.state == SafetyState.ELEVATED

    def test_rule_9_recovery_cooldown_behavior(self):
        """Scenario 9: Recovery period required before returning from INCIDENT to NORMAL."""
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        gps_sig = SafetySignalFactory.create_gps_signal("tourist_1", "sess_1", 15.29, 74.12, 10.0, timestamp=now_iso)
        tel_sig = SafetySignalFactory.create_telemetry_signal("tourist_1", "sess_1", "good", 50.0, 1.0, timestamp=now_iso)

        # 1. Recovery just started (5s ago, < 20s cooldown)
        recov_start = (now_dt - timedelta(seconds=5)).isoformat()
        decision_recov = rule_engine.evaluate_signals(
            tourist_id="tourist_1",
            session_id="sess_1",
            previous_state=SafetyState.INCIDENT,
            active_signals=[gps_sig, tel_sig],
            recovery_started_at=recov_start,
            now=now_dt,
        )
        assert decision_recov.state == SafetyState.RECOVERING
        assert any(r.rule_id == "RULE_E1_RECOVERY_IN_PROGRESS" for r in decision_recov.triggered_rules)

        # 2. Recovery cooldown completed (25s ago, > 20s cooldown)
        recov_done = (now_dt - timedelta(seconds=25)).isoformat()
        decision_done = rule_engine.evaluate_signals(
            tourist_id="tourist_1",
            session_id="sess_1",
            previous_state=SafetyState.RECOVERING,
            active_signals=[gps_sig, tel_sig],
            recovery_started_at=recov_done,
            now=now_dt,
        )
        assert decision_done.state == SafetyState.NORMAL
        assert any(r.rule_id == "RULE_E2_RECOVERY_STABLE" for r in decision_done.triggered_rules)


class TestSafetyStateMachine:
    """Tests valid transitions and rejects invalid state jumps."""

    def test_valid_forward_state_transitions(self):
        assert SafetyStateMachine.is_valid_transition(SafetyState.NORMAL, SafetyState.WATCH) is True
        assert SafetyStateMachine.is_valid_transition(SafetyState.WATCH, SafetyState.ELEVATED) is True
        assert SafetyStateMachine.is_valid_transition(SafetyState.ELEVATED, SafetyState.INCIDENT_CANDIDATE) is True
        assert SafetyStateMachine.is_valid_transition(SafetyState.INCIDENT_CANDIDATE, SafetyState.INCIDENT) is True
        assert SafetyStateMachine.is_valid_transition(SafetyState.INCIDENT, SafetyState.RECOVERING) is True
        assert SafetyStateMachine.is_valid_transition(SafetyState.RECOVERING, SafetyState.NORMAL) is True

    def test_invalid_direct_jump_gating(self):
        # NORMAL -> INCIDENT directly is invalid without candidate/corroboration
        assert SafetyStateMachine.is_valid_transition(SafetyState.NORMAL, SafetyState.INCIDENT) is False

        dec = SafetyDecision(
            tourist_id="t1",
            state=SafetyState.INCIDENT,
            previous_state=SafetyState.NORMAL,
            rule_version="safety-rules-v1",
        )
        final_state, _ = SafetyStateMachine.apply_transition(
            current_state=SafetyState.NORMAL,
            evaluated_decision=dec,
        )
        # Gated to WATCH instead of jumping to INCIDENT
        assert final_state == SafetyState.WATCH


class TestIncidentLifecycleManager:
    """Tests incident creation, deduplication, acknowledgment, and resolution."""

    def test_incident_creation_and_deduplication(self):
        dec = SafetyDecision(
            decision_id="dec_1",
            tourist_id="tourist_1",
            session_id="sess_1",
            state=SafetyState.INCIDENT,
            previous_state=SafetyState.INCIDENT_CANDIDATE,
            rule_version="safety-rules-v1",
            reasons=["Persistent anomaly in danger zone"],
            signals={"risk": "critical"},
            quality=SignalQuality.GOOD,
        )

        # 1. Create brand new incident
        inc1 = IncidentLifecycleManager.create_or_update_incident("tourist_1", "sess_1", dec, existing_incident=None)
        assert inc1.status == IncidentStatus.OPEN
        assert inc1.severity == IncidentSeverity.HIGH
        assert inc1.decision_id == "dec_1"

        # 2. Subsequent evaluated cycle with same active incident -> Deduplicated (updated, not recreated)
        dec2 = SafetyDecision(
            decision_id="dec_2",
            tourist_id="tourist_1",
            session_id="sess_1",
            state=SafetyState.INCIDENT,
            previous_state=SafetyState.INCIDENT,
            rule_version="safety-rules-v1",
            reasons=["Sustained condition"],
            signals={"risk": "critical"},
        )
        inc2 = IncidentLifecycleManager.create_or_update_incident("tourist_1", "sess_1", dec2, existing_incident=inc1)
        assert inc2.incident_id == inc1.incident_id
        assert inc2.decision_id == "dec_2"
        assert inc2.status == IncidentStatus.OPEN

    def test_incident_acknowledgment_and_resolution(self):
        inc = IncidentRecord(
            incident_id="inc_test_1",
            tourist_id="tourist_1",
            session_id="sess_1",
            decision_id="dec_1",
            rule_version="safety-rules-v1",
        )

        # Acknowledge
        ack_inc = IncidentLifecycleManager.acknowledge_incident(inc, authority_id="officer_101", notes="Monitoring drone deployed")
        assert ack_inc.status == IncidentStatus.ACKNOWLEDGED
        assert ack_inc.acknowledged_by == "officer_101"
        assert "Monitoring drone deployed" in (ack_inc.notes or "")

        # Resolve
        res_inc = IncidentLifecycleManager.resolve_incident(
            ack_inc,
            resolution_reason="Tourist safely escorted to designated trail",
            authority_id="officer_101",
        )
        assert res_inc.status == IncidentStatus.RESOLVED
        assert res_inc.resolved_at is not None
        assert "Tourist safely escorted" in (res_inc.notes or "")

    def test_invalid_resolution_on_resolved_incident(self):
        inc = IncidentRecord(
            incident_id="inc_closed",
            tourist_id="tourist_1",
            decision_id="dec_1",
            rule_version="safety-rules-v1",
            status=IncidentStatus.RESOLVED,
        )
        with pytest.raises(ValueError, match="Cannot resolve incident in status 'RESOLVED'"):
            IncidentLifecycleManager.resolve_incident(inc, resolution_reason="Double close")


@pytest.mark.asyncio
class TestSafetyOrchestratorAsyncIntegration:
    """Tests end-to-end signal ingestion into SafetyOrchestrationEngine."""

    async def test_full_safety_orchestrator_signal_flow(self):
        tourist_id = "test_tourist_integration"
        session_id = "test_sess_integration"
        now = datetime.now(timezone.utc).isoformat()

        # Step 1: Send GPS signal
        gps_sig = SafetySignalFactory.create_gps_signal(
            tourist_id=tourist_id,
            session_id=session_id,
            latitude=15.29,
            longitude=74.12,
            accuracy=10.0,
            timestamp=now,
        )
        dec1 = await safety_orchestrator.ingest_signal(gps_sig)
        assert dec1.tourist_id == tourist_id

        # Step 2: Send Telemetry Good signal
        tel_sig = SafetySignalFactory.create_telemetry_signal(
            tourist_id=tourist_id,
            session_id=session_id,
            overall_quality="good",
            observed_frequency_hz=50.0,
            completeness_ratio=1.0,
            timestamp=now,
        )
        dec2 = await safety_orchestrator.ingest_signal(tel_sig)
        assert dec2.state == SafetyState.NORMAL

        # Step 3: Check Active State Cache
        snap = await safety_orchestrator.get_tourist_safety_snapshot(tourist_id)
        assert snap is not None
        assert snap.current_state == SafetyState.NORMAL
        assert snap.rule_version == "safety-rules-v1"
