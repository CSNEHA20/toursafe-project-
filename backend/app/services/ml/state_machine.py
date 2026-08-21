"""
TourSafe Anomaly State Machine with Temporal Persistence & Hysteresis.
Prevents single-window false alarms and threshold oscillation by tracking:
- NORMAL -> CANDIDATE -> ANOMALOUS -> RECOVERING -> NORMAL
- Separate anomaly threshold and recovery threshold (hysteresis deadband)
- Configurable consecutive window persistence filters.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Dict, Optional, Tuple
from ...schemas.ml import AnomalyState

logger = logging.getLogger("toursafe.ml.state_machine")


@dataclass
class TouristAnomalyState:
    tourist_id: str
    session_id: str
    current_state: AnomalyState = AnomalyState.NORMAL
    consecutive_elevated_count: int = 0
    consecutive_normal_count: int = 0
    last_score: float = 0.0
    peak_score: float = 0.0
    episode_id: Optional[str] = None
    episode_started_at: Optional[str] = None
    window_count_in_episode: int = 0
    last_updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AnomalyStateMachine:
    """
    Session-aware state machine with temporal persistence and hysteresis gating.
    """

    def __init__(
        self,
        persistence_count: int = 2,
        recovery_count: int = 2,
    ):
        self.persistence_count = persistence_count
        self.recovery_count = recovery_count
        self._states: Dict[str, TouristAnomalyState] = {}

    def get_or_create_state(self, tourist_id: str, session_id: str) -> TouristAnomalyState:
        key = f"{tourist_id}:{session_id}"
        if key not in self._states:
            self._states[key] = TouristAnomalyState(
                tourist_id=tourist_id,
                session_id=session_id,
            )
        return self._states[key]

    def evaluate_window(
        self,
        tourist_id: str,
        session_id: str,
        anomaly_score: float,
        anomaly_threshold: float,
        recovery_threshold: float,
    ) -> Tuple[AnomalyState, AnomalyState, bool, bool]:
        """
        Evaluates a window score and transitions state according to persistence and hysteresis.

        Returns
        -------
        Tuple of:
        - previous_state: AnomalyState
        - new_state: AnomalyState
        - became_anomalous: bool (True when transitioning to ANOMALOUS for the first time in episode)
        - became_cleared: bool (True when transitioning back to NORMAL from ANOMALOUS/RECOVERING)
        """
        state_obj = self.get_or_create_state(tourist_id, session_id)
        prev_state = state_obj.current_state
        state_obj.last_score = anomaly_score
        state_obj.last_updated_at = datetime.now(timezone.utc).isoformat()

        became_anomalous = False
        became_cleared = False

        is_elevated = anomaly_score >= anomaly_threshold
        is_normal = anomaly_score < recovery_threshold
        # Note: If recovery_threshold <= anomaly_score < anomaly_threshold, it's in the hysteresis band

        if is_elevated:
            state_obj.consecutive_elevated_count += 1
            state_obj.consecutive_normal_count = 0

            if prev_state == AnomalyState.NORMAL:
                if state_obj.consecutive_elevated_count >= self.persistence_count:
                    state_obj.current_state = AnomalyState.ANOMALOUS
                    became_anomalous = True
                else:
                    state_obj.current_state = AnomalyState.CANDIDATE

            elif prev_state == AnomalyState.CANDIDATE:
                if state_obj.consecutive_elevated_count >= self.persistence_count:
                    state_obj.current_state = AnomalyState.ANOMALOUS
                    became_anomalous = True

            elif prev_state == AnomalyState.RECOVERING:
                # Interrupted recovery; snap back to ANOMALOUS
                state_obj.current_state = AnomalyState.ANOMALOUS

            elif prev_state == AnomalyState.ANOMALOUS:
                # Remains ANOMALOUS
                pass

        elif is_normal:
            state_obj.consecutive_normal_count += 1
            state_obj.consecutive_elevated_count = 0

            if prev_state == AnomalyState.CANDIDATE:
                # Elevated score did not persist; revert to NORMAL
                state_obj.current_state = AnomalyState.NORMAL

            elif prev_state == AnomalyState.ANOMALOUS:
                if state_obj.consecutive_normal_count >= self.recovery_count:
                    state_obj.current_state = AnomalyState.NORMAL
                    became_cleared = True
                else:
                    state_obj.current_state = AnomalyState.RECOVERING

            elif prev_state == AnomalyState.RECOVERING:
                if state_obj.consecutive_normal_count >= self.recovery_count:
                    state_obj.current_state = AnomalyState.NORMAL
                    became_cleared = True

            elif prev_state == AnomalyState.NORMAL:
                # Remains NORMAL
                pass

        else:
            # Score is in hysteresis deadband [recovery_threshold, anomaly_threshold)
            # Maintain current state and don't increment elevation or recovery counters
            pass

        return prev_state, state_obj.current_state, became_anomalous, became_cleared

    def clear_session(self, tourist_id: str, session_id: str):
        key = f"{tourist_id}:{session_id}"
        self._states.pop(key, None)


anomaly_state_machine = AnomalyStateMachine(persistence_count=2, recovery_count=2)
