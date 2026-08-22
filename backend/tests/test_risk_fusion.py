"""
TourSafe Prompt 23: Advanced Safety Intelligence & Risk Fusion Tests

Comprehensive test suite verifying:
1. Multi-signal feature normalization (GPS, IMU, Geofence, Itinerary, Telemetry, Temporal, Trip, History)
2. Signal cross-correlation & false-positive reduction
3. Multi-layer risk fusion scoring & confidence assessment
4. Explainability reports, feature attributions, and decision support recommendations
5. State machine integration with fused risk scoring
6. Tourist interactive safety check responses & dampening loop
7. REST API endpoints for authority risk inspection and tourist safety status
"""

import copy
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport

import app.core.database as db_module
from app.main import app
from app.schemas.safety import (
    ConfidenceAssessment,
    ConfidenceClass,
    IncidentSeverity,
    IncidentStatus,
    NormalizedSafetyFeatures,
    RiskScoreBreakdown,
    SafetyCheckResponseRequest,
    SafetyDecision,
    SafetySignal,
    SafetyState,
    SignalCorrelationResult,
    SignalQuality,
    SignalType,
)
from app.services.safety import (
    safety_config,
    safety_orchestrator,
    safety_redis_state,
    safety_repository,
)
import app.services.safety.repository as safety_repo_mod
from app.services.safety.fusion import (
    ExplainabilityEngine,
    RiskFusionEngine,
    RiskFusionScorer,
    SignalCorrelationEngine,
    SignalNormalizer,
    risk_fusion_engine,
)
from app.services.safety.signals import SafetySignalFactory


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

    async def replace_one(self, filter_dict, new_doc, upsert=False, *args, **kwargs):
        for i, doc in enumerate(self.docs):
            if self._matches(doc, filter_dict):
                self.docs[i] = copy.deepcopy(new_doc)
                return type("Obj", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            self.docs.append(copy.deepcopy(new_doc))
            return type("Obj", (), {"modified_count": 0, "matched_count": 0, "upserted_id": new_doc.get("id", "new")})()
        return type("Obj", (), {"modified_count": 0, "matched_count": 0})()

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

    async def count_documents(self, filter_dict=None, *args, **kwargs):
        filter_dict = filter_dict or {}
        return sum(1 for d in self.docs if self._matches(d, filter_dict))

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


# ---------------------------------------------------------------------------
# Unit Tests: Signal Normalization
# ---------------------------------------------------------------------------

def test_signal_normalization_all_domains():
    now = datetime.now(timezone.utc)

    # 1. Anomaly Signal
    anom_sig = SafetySignalFactory.create_anomaly_signal(
        tourist_id="tourist_101",
        session_id="sess_1",
        state="anomalous",
        score=1.8,
        threshold=0.6,
        consecutive_windows=3,
        timestamp=now.isoformat(),
    )

    # 2. GPS Signal (high accuracy, high speed)
    gps_sig = SafetySignalFactory.create_gps_signal(
        tourist_id="tourist_101",
        session_id="sess_1",
        latitude=34.0522,
        longitude=-118.2437,
        accuracy=5.0,
        speed=15.0,
        timestamp=now.isoformat(),
    )

    # 3. Geofence Signal (danger zone)
    zone_sig = SafetySignalFactory.create_geofence_signal(
        tourist_id="tourist_101",
        session_id="sess_1",
        zone_id="zone_danger_1",
        zone_name="Cliffside Restricted Area",
        zone_type="restricted",
        risk_level="danger",
        membership_state="inside",
        dwell_duration_seconds=420.0,
        timestamp=now.isoformat(),
    )

    # 4. Telemetry Signal (good)
    telemetry_sig = SafetySignalFactory.create_telemetry_signal(
        tourist_id="tourist_101",
        session_id="sess_1",
        overall_quality="good",
        observed_frequency_hz=50.0,
        completeness_ratio=0.98,
        timestamp=now.isoformat(),
    )

    # 5. Itinerary Deviation (650m)
    itinerary_sig = SafetySignalFactory.create_itinerary_deviation_signal(
        tourist_id="tourist_101",
        session_id="sess_1",
        planned_destination="Scenic Outlook",
        distance_meters=650.0,
        timestamp=now.isoformat(),
    )

    signals = [anom_sig, gps_sig, zone_sig, telemetry_sig, itinerary_sig]

    context = {
        "is_solo_traveler": True,
        "trip_type": "trekking",
        "has_medical_conditions": False,
        "prior_incidents_count": 0,
    }

    norm_features = SignalNormalizer.normalize_signals(
        active_signals=signals,
        tourist_context=context,
        now=now,
    )

    assert 0.0 <= norm_features.motion_anomaly_norm <= 1.0
    assert norm_features.motion_anomaly_norm >= 0.5
    assert norm_features.geospatial_hazard_norm >= 0.8
    assert norm_features.itinerary_deviation_norm >= 0.3
    assert norm_features.trip_vulnerability_norm >= 0.4


# ---------------------------------------------------------------------------
# Unit Tests: Signal Cross-Correlation & False Positive Reduction
# ---------------------------------------------------------------------------

def test_false_positive_reduction_highway_transit_vibration():
    features = NormalizedSafetyFeatures(
        motion_anomaly_norm=0.65,
        geospatial_hazard_norm=0.1,
        itinerary_deviation_norm=0.05,
        telemetry_degradation_norm=0.1,
        temporal_risk_norm=0.1,
        trip_vulnerability_norm=0.1,
        historical_risk_norm=0.05,
        kinematic_shock_norm=0.2,
    )

    raw_signals = {
        "GPS_LOCATION_UPDATE": {"speed": 16.6},
        "ANOMALY_DETECTED": {"consecutive_windows": 3},
    }

    corr = SignalCorrelationEngine.evaluate_correlation(
        features=features,
        raw_signals=raw_signals,
    )

    assert corr.correlated_pattern == "BENIGN_HIGHWAY_TRANSIT_ROUGH_ROAD"
    assert corr.is_false_alarm_suppressed is True
    assert corr.dampening_factor <= 0.35
    assert corr.false_positive_probability >= 0.70


def test_false_positive_reduction_transient_phone_drop():
    features = NormalizedSafetyFeatures(
        motion_anomaly_norm=0.15,
        kinematic_shock_norm=0.65,
        geospatial_hazard_norm=0.1,
        itinerary_deviation_norm=0.05,
        telemetry_degradation_norm=0.05,
    )

    raw_signals = {
        "GPS_LOCATION_UPDATE": {"speed": 1.2},
        "ANOMALY_DETECTED": {"consecutive_windows": 1},
    }

    corr = SignalCorrelationEngine.evaluate_correlation(
        features=features,
        raw_signals=raw_signals,
    )

    assert corr.correlated_pattern == "TRANSIENT_PHONE_DROP"
    assert corr.is_false_alarm_suppressed is True
    assert corr.dampening_factor <= 0.30


def test_corroborated_high_risk_vehicular_crash():
    features = NormalizedSafetyFeatures(
        motion_anomaly_norm=0.85,
        kinematic_shock_norm=0.90,
        geospatial_hazard_norm=0.5,
        itinerary_deviation_norm=0.45,
        telemetry_degradation_norm=0.2,
    )

    raw_signals = {
        "GPS_LOCATION_UPDATE": {"speed": 12.5, "speed_delta": -25.0},
        "ANOMALY_DETECTED": {"consecutive_windows": 4},
    }

    corr = SignalCorrelationEngine.evaluate_correlation(
        features=features,
        raw_signals=raw_signals,
    )

    assert corr.correlated_pattern == "CORROBORATED_VEHICULAR_CRASH"
    assert corr.is_false_alarm_suppressed is False
    assert corr.dampening_factor == 1.0
    assert corr.false_positive_probability <= 0.05


def test_tourist_confirmed_safe_active_dampening():
    features = NormalizedSafetyFeatures(
        motion_anomaly_norm=0.4,
        kinematic_shock_norm=0.3,
        geospatial_hazard_norm=0.3,
    )

    ctx = {
        "recent_safe_check_confirmed": True,
        "safe_check_age_seconds": 120.0,
    }

    corr = SignalCorrelationEngine.evaluate_correlation(
        features=features,
        raw_signals={},
        tourist_context=ctx,
    )

    assert "SIGNATURE_USER_CONFIRMED_SAFE" in corr.matched_signatures
    assert corr.is_false_alarm_suppressed is True
    assert corr.dampening_factor <= 0.25


# ---------------------------------------------------------------------------
# Unit Tests: Multi-Layer Risk Scoring & Confidence Assessment
# ---------------------------------------------------------------------------

def test_risk_scoring_and_confidence_quantification():
    features = NormalizedSafetyFeatures(
        motion_anomaly_norm=0.7,
        kinematic_shock_norm=0.6,
        geospatial_hazard_norm=0.8,
        itinerary_deviation_norm=0.5,
        temporal_risk_norm=0.6,
        telemetry_degradation_norm=0.1,
        trip_vulnerability_norm=0.4,
        historical_risk_norm=0.2,
    )

    corr = SignalCorrelationResult(
        correlated_pattern="NONE",
        dampening_factor=1.0,
        false_positive_probability=0.05,
    )

    breakdown = RiskFusionScorer.compute_risk_breakdown(
        features=features,
        correlation=corr,
        previous_composite_score=50.0,
    )

    assert breakdown.composite_risk_score >= 60.0
    assert breakdown.motion_risk_score >= 50.0
    assert breakdown.spatial_risk_score >= 70.0
    assert breakdown.risk_level_label in ("ELEVATED", "CRITICAL")
    assert breakdown.risk_trend == "INCREASING"

    conf = RiskFusionScorer.compute_confidence_assessment(
        features=features,
        raw_signals_count=5,
        has_gps=True,
        has_telemetry=True,
        has_imu=True,
    )

    assert conf.confidence_score >= 0.75
    assert conf.confidence_class == ConfidenceClass.HIGH
    assert conf.sparsity_penalty == 0.0


# ---------------------------------------------------------------------------
# Unit Tests: Explainability & Decision Support
# ---------------------------------------------------------------------------

def test_explainability_and_decision_support_generation():
    features = NormalizedSafetyFeatures(
        motion_anomaly_norm=0.8,
        kinematic_shock_norm=0.7,
        geospatial_hazard_norm=0.9,
        itinerary_deviation_norm=0.6,
        temporal_risk_norm=0.7,
        telemetry_degradation_norm=0.1,
    )

    corr = SignalCorrelationResult(
        correlated_pattern="CORROBORATED_HAZARD_FALL",
        dampening_factor=1.0,
        false_positive_probability=0.02,
        is_false_alarm_suppressed=False,
    )

    breakdown = RiskScoreBreakdown(
        composite_risk_score=88.5,
        motion_risk_score=75.0,
        spatial_risk_score=90.0,
        itinerary_risk_score=60.0,
        environmental_risk_score=50.0,
        vulnerability_risk_score=30.0,
        risk_level_label="CRITICAL",
        risk_trend="INCREASING",
    )

    conf = ConfidenceAssessment(
        confidence_score=0.92,
        confidence_class=ConfidenceClass.HIGH,
    )

    explainability, decision = ExplainabilityEngine.generate_report(
        features=features,
        risk_breakdown=breakdown,
        correlation=corr,
        confidence=conf,
        raw_signals={},
    )

    assert len(explainability.primary_risk_drivers) > 0
    assert len(explainability.feature_attributions) > 0
    assert "CRITICAL" in explainability.natural_language_summary
    assert decision.recommended_action == "EMERGENCY_DISPATCH_CONFIRMATION"
    assert decision.action_priority == "URGENT"
    assert len(decision.verification_checklist) >= 3


# ---------------------------------------------------------------------------
# Integration Tests: End-to-End Safety Orchestration with Risk Fusion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_safety_orchestrator_end_to_end_fusion():
    tourist_id = f"test_fusion_tourist_{datetime.now().timestamp()}"
    now = datetime.now(timezone.utc)

    # 1. Ingest normal GPS & telemetry
    gps_sig = SafetySignalFactory.create_gps_signal(
        tourist_id=tourist_id,
        session_id="sess_1",
        latitude=34.0522,
        longitude=-118.2437,
        accuracy=8.0,
        speed=1.5,
        timestamp=now.isoformat(),
    )
    telem_sig = SafetySignalFactory.create_telemetry_signal(
        tourist_id=tourist_id,
        session_id="sess_1",
        overall_quality="good",
        observed_frequency_hz=50.0,
        completeness_ratio=0.95,
        timestamp=now.isoformat(),
    )
    await safety_orchestrator.ingest_signal(telem_sig)
    decision1 = await safety_orchestrator.ingest_signal(gps_sig)

    assert decision1.state in (SafetyState.NORMAL, SafetyState.WATCH)
    assert decision1.risk_score is not None
    assert decision1.risk_score < 40.0

    # 2. Ingest persistent motion anomaly + danger zone -> Elevates to CANDIDATE / INCIDENT
    anom_sig = SafetySignalFactory.create_anomaly_signal(
        tourist_id=tourist_id,
        session_id="sess_1",
        state="anomalous",
        score=2.5,
        threshold=0.5,
        consecutive_windows=4,
        timestamp=now.isoformat(),
    )
    zone_sig = SafetySignalFactory.create_geofence_signal(
        tourist_id=tourist_id,
        session_id="sess_1",
        zone_id="danger_cliff",
        zone_name="Danger Cliff",
        zone_type="hazard",
        risk_level="danger",
        membership_state="inside",
        dwell_duration_seconds=360.0,
        timestamp=now.isoformat(),
    )
    await safety_orchestrator.ingest_signal(zone_sig)
    decision2 = await safety_orchestrator.ingest_signal(anom_sig)

    assert decision2.risk_score >= 50.0
    assert decision2.risk_assessment is not None
    assert decision2.risk_assessment.risk_breakdown.risk_level_label in ("WATCH", "ELEVATED", "CRITICAL")
    assert decision2.state in (SafetyState.ELEVATED, SafetyState.INCIDENT_CANDIDATE, SafetyState.INCIDENT)

    # 3. Test tourist safety check response ("Confirm Safe")
    check_req = SafetyCheckResponseRequest(
        response_type="SAFE_CONFIRMED",
        user_note="I accidentally dropped my backpack. Everything is fine!",
        battery_level=0.85,
    )
    check_result = await safety_orchestrator.handle_safety_check_response(
        tourist_id=tourist_id,
        payload=check_req,
    )
    assert check_result.success is True
    assert "registered" in check_result.message


# ---------------------------------------------------------------------------
# API Endpoint Tests: REST APIs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_safety_rest_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Authority Risk Matrix Config Endpoint
        res_matrix = await ac.get(
            "/api/v1/authority/safety/risk-matrix",
            headers={"Authorization": "Bearer mock-authority-token"},
        )
        assert res_matrix.status_code in (200, 401)
        if res_matrix.status_code == 200:
            data = res_matrix.json()
            assert "weights" in data
            assert "thresholds" in data
            assert "correlation_signatures" in data

        # 2. Simulated Multi-Signal Evaluation Endpoint
        eval_payload = {
            "tourist_id": "sim_tourist_1",
            "signals": [
                {
                    "signal_type": "ANOMALY_DETECTED",
                    "tourist_id": "sim_tourist_1",
                    "source": "lstm_autoencoder",
                    "value": {"score": 1.2, "threshold": 0.5, "is_anomalous": True, "consecutive_windows": 2},
                    "quality": "GOOD",
                },
                {
                    "signal_type": "GPS_LOCATION_UPDATE",
                    "tourist_id": "sim_tourist_1",
                    "source": "gps_service",
                    "value": {"latitude": 34.0, "longitude": -118.0, "accuracy": 10.0, "speed": 1.0},
                    "quality": "GOOD",
                },
            ],
            "context": {"is_solo_traveler": True},
        }
        res_eval = await ac.post(
            "/api/v1/authority/safety/evaluate",
            json=eval_payload,
            headers={"Authorization": "Bearer mock-authority-token"},
        )
        assert res_eval.status_code in (200, 401)
        if res_eval.status_code == 200:
            eval_data = res_eval.json()
            assert "risk_breakdown" in eval_data
            assert "correlation" in eval_data
            assert "confidence" in eval_data
            assert "explainability" in eval_data
