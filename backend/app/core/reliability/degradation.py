"""
TourSafe Graceful Degradation & Priority Model.
Enforces load-shedding and service isolation during resource exhaustion or outage.
"""

from enum import Enum
from typing import Dict, Any, Optional, Set
from fastapi import HTTPException, status
from .logging import get_structured_logger

logger = get_structured_logger("toursafe.degradation")


class SystemMode(str, Enum):
    FULL = "FULL"                      # All subsystems active
    DEGRADED = "DEGRADED"              # Auxiliary services may failover/cache, non-critical slowdowns permitted
    CRITICAL_ONLY = "CRITICAL_ONLY"    # AI, heavy analytics & non-essential batch jobs shed to preserve SOS & Dispatch
    OFFLINE = "OFFLINE"                # Read-only or local cache fallback


class ServicePriority(str, Enum):
    CRITICAL = "CRITICAL"          # SOS, Incident creation, responder dispatch, telemetry, safety state
    HIGH = "HIGH"                  # Geofencing, realtime maps, urgent notifications
    NORMAL = "NORMAL"              # KYC verification, device health, itineraries
    NON_CRITICAL = "NON_CRITICAL"  # AI Copilot, forecasting, heatmaps, non-vital analytics


class DegradationManager:
    """Manages system degradation mode and service prioritization."""

    def __init__(self):
        self._current_mode: SystemMode = SystemMode.FULL
        self._mode_reason: str = "System operating within normal parameters"
        self._disabled_subsystems: Set[str] = set()

    @property
    def current_mode(self) -> SystemMode:
        return self._current_mode

    @property
    def reason(self) -> str:
        return self._mode_reason

    def set_mode(self, mode: SystemMode, reason: str, actor_id: Optional[str] = None):
        """Set degradation mode manually or automatically."""
        old_mode = self._current_mode
        self._current_mode = mode
        self._mode_reason = reason

        if mode == SystemMode.CRITICAL_ONLY:
            self._disabled_subsystems = {"ai_copilot", "analytics_forecast", "heatmaps", "external_weather"}
        elif mode == SystemMode.DEGRADED:
            self._disabled_subsystems = {"analytics_forecast"}
        elif mode == SystemMode.FULL:
            self._disabled_subsystems.clear()

        logger.info(
            f"System degradation mode changed from {old_mode} to {mode}: {reason}",
            extra={"event": "DEGRADATION_MODE_CHANGE", "extra_data": {"old_mode": old_mode, "new_mode": mode, "actor": actor_id or "system"}}
        )

    def is_service_allowed(self, priority: ServicePriority, subsystem_name: Optional[str] = None) -> bool:
        """Check if an operation of given priority or subsystem is permitted in the current mode."""
        if subsystem_name and subsystem_name in self._disabled_subsystems:
            return False

        if self._current_mode == SystemMode.FULL:
            return True
        elif self._current_mode == SystemMode.DEGRADED:
            # All except explicitly disabled
            return True
        elif self._current_mode == SystemMode.CRITICAL_ONLY:
            return priority in (ServicePriority.CRITICAL, ServicePriority.HIGH)
        elif self._current_mode == SystemMode.OFFLINE:
            return False
        return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "mode": self._current_mode.value,
            "reason": self._mode_reason,
            "disabled_subsystems": list(self._disabled_subsystems),
            "priority_enforcement": {
                ServicePriority.CRITICAL.value: self.is_service_allowed(ServicePriority.CRITICAL),
                ServicePriority.HIGH.value: self.is_service_allowed(ServicePriority.HIGH),
                ServicePriority.NORMAL.value: self.is_service_allowed(ServicePriority.NORMAL),
                ServicePriority.NON_CRITICAL.value: self.is_service_allowed(ServicePriority.NON_CRITICAL),
            }
        }


degradation_manager = DegradationManager()


def require_priority_allowance(priority: ServicePriority, subsystem_name: Optional[str] = None):
    """Dependency / guard ensuring request is allowed under current system degradation mode."""
    if not degradation_manager.is_service_allowed(priority, subsystem_name):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "SERVICE_DEGRADED_LOAD_SHEDDING",
                "message": f"Subsystem '{subsystem_name or priority.value}' is temporarily shed due to {degradation_manager.current_mode.value} mode.",
                "current_mode": degradation_manager.current_mode.value,
                "reason": degradation_manager.reason,
            }
        )


class ServicePriorityRegistry:
    """Registry documenting the priority tier and rationale of all platform services."""

    SERVICES = {
        "sos_ingestion": (ServicePriority.CRITICAL, "Immediate life-safety alarm processing"),
        "incident_lifecycle": (ServicePriority.CRITICAL, "Creation, assignment, escalation, closure of emergencies"),
        "responder_dispatch": (ServicePriority.CRITICAL, "Tasking and routing field responders to emergencies"),
        "telemetry_ingestion": (ServicePriority.CRITICAL, "Live GPS and IMU stream for tourist safety monitoring"),
        "critical_notifications": (ServicePriority.CRITICAL, "Dispatch alerts and emergency broadcast delivery"),
        "geofence_engine": (ServicePriority.HIGH, "Zone breach and high-risk area transit alerts"),
        "realtime_map": (ServicePriority.HIGH, "Live location visualization for command centers"),
        "kyc_verification": (ServicePriority.NORMAL, "Digital identity verification and pass validation"),
        "device_health": (ServicePriority.NORMAL, "Battery, connectivity, and hardware state tracking"),
        "ai_copilot": (ServicePriority.NON_CRITICAL, "Generative AI assistance, automated summary suggestions"),
        "analytics_forecast": (ServicePriority.NON_CRITICAL, "Predictive risk forecasts and historical trend aggregation"),
        "heatmap_generation": (ServicePriority.NON_CRITICAL, "Visual aggregate density heatmaps"),
    }
