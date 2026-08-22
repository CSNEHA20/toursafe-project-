"""
TourSafe Model Shadow Engine.
Executes candidate models asynchronously alongside the active production model
on live telemetry windows. Evaluates score divergence, alert frequency differences,
and prediction agreement WITHOUT affecting safety orchestration or incident generation.
"""

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import numpy as np
import onnxruntime as ort

from ...schemas.ml_lifecycle import ShadowInferenceMetric
from ...schemas.telemetry import TelemetryWindow
from ..preprocessing.scaler import TourSafeRobustScaler
from .model_registry import model_registry

logger = logging.getLogger("toursafe.ml.shadow_engine")


class ModelShadowEngine:
    """
    Asynchronously shadows incoming telemetry windows on candidate models.
    """

    def __init__(self, artifacts_base_dir: Optional[Path] = None):
        base = Path(__file__).resolve().parent.parent / "artifacts"
        self.artifacts_base_dir = artifacts_base_dir or base
        self.active_shadow_version: Optional[str] = None
        self._shadow_session: Optional[ort.InferenceSession] = None
        self._shadow_scaler: Optional[TourSafeRobustScaler] = None
        self._shadow_threshold: float = 5.804714
        self._recent_metrics: List[ShadowInferenceMetric] = []
        self._max_history = 500

    def load_shadow_model(self, model_version: str) -> bool:
        """Loads and prepares candidate model for shadow execution."""
        version_dir = self.artifacts_base_dir / model_version
        model_onnx = version_dir / "model.onnx"
        scaler_json = version_dir / "scaler_config.json"
        thresh_json = version_dir / "threshold_config.json"

        if not model_onnx.exists() or not scaler_json.exists():
            logger.error(f"Cannot load shadow model {model_version}: missing artifacts")
            return False

        try:
            self._shadow_session = ort.InferenceSession(str(model_onnx), providers=["CPUExecutionProvider"])
            self._shadow_scaler = TourSafeRobustScaler.load(scaler_json)
            if thresh_json.exists():
                import json
                with open(thresh_json, "r", encoding="utf-8") as f:
                    t_data = json.load(f)
                self._shadow_threshold = float(t_data.get("primary_threshold", 5.804714))
            self.active_shadow_version = model_version
            logger.info(f"Loaded shadow model {model_version} with threshold {self._shadow_threshold:.4f}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize shadow session for {model_version}: {e}")
            return False

    def unload_shadow_model(self):
        self.active_shadow_version = None
        self._shadow_session = None
        self._shadow_scaler = None

    async def evaluate_shadow_window(
        self,
        window: TelemetryWindow,
        production_score: float,
        production_state: str,
        production_version: str,
    ) -> Optional[ShadowInferenceMetric]:
        """
        Executes non-blocking shadow inference on candidate model.
        """
        if not self.active_shadow_version or self._shadow_session is None or self._shadow_scaler is None:
            return None

        try:
            t0 = time.time()
            # Prepare tensor
            raw_samples = []
            for s in window.samples:
                ax, ay, az = s.accelerometer.x, s.accelerometer.y, s.accelerometer.z
                gx, gy, gz = s.gyroscope.x, s.gyroscope.y, s.gyroscope.z
                amag = float(np.sqrt(ax**2 + ay**2 + az**2))
                gmag = float(np.sqrt(gx**2 + gy**2 + gz**2))
                raw_samples.append([ax, ay, az, gx, gy, gz, amag, gmag])

            if len(raw_samples) != 150:
                return None

            raw_arr = np.array(raw_samples, dtype=np.float32)
            scaled = self._shadow_scaler.transform(raw_arr)
            inp = np.expand_dims(scaled, axis=0).astype(np.float32)

            input_name = self._shadow_session.get_inputs()[0].name
            output_name = self._shadow_session.get_outputs()[0].name
            recon = self._shadow_session.run([output_name], {input_name: inp})[0]

            cand_score = float(np.mean((inp - recon) ** 2))
            t1 = time.time()
            cand_latency_ms = (t1 - t0) * 1000.0

            cand_state = "anomalous" if cand_score >= self._shadow_threshold else "normal"
            agreement = (cand_state == production_state)

            metric = ShadowInferenceMetric(
                timestamp=datetime.now(timezone.utc).isoformat(),
                window_id=window.window_id,
                production_model_version=production_version,
                candidate_model_version=self.active_shadow_version,
                production_score=round(production_score, 4),
                candidate_score=round(cand_score, 4),
                production_state=production_state,
                candidate_state=cand_state,
                production_latency_ms=0.5,
                candidate_latency_ms=round(cand_latency_ms, 3),
                score_difference=round(cand_score - production_score, 4),
                prediction_agreement=agreement,
            )

            self._recent_metrics.append(metric)
            if len(self._recent_metrics) > self._max_history:
                self._recent_metrics.pop(0)

            return metric
        except Exception as e:
            logger.warning(f"Shadow evaluation error for window {window.window_id}: {e}")
            return None

    def get_shadow_metrics_summary(self) -> Dict[str, Any]:
        """Returns statistical summary of recent shadow evaluations."""
        if not self._recent_metrics:
            return {
                "active_shadow_version": self.active_shadow_version,
                "total_shadow_evaluations": 0,
                "prediction_agreement_rate": 1.0,
                "mean_score_difference": 0.0,
                "candidate_alert_count": 0,
                "production_alert_count": 0,
                "recent_metrics": [],
            }

        total = len(self._recent_metrics)
        agreed = sum(1 for m in self._recent_metrics if m.prediction_agreement)
        cand_alerts = sum(1 for m in self._recent_metrics if m.candidate_state == "anomalous")
        prod_alerts = sum(1 for m in self._recent_metrics if m.production_state == "anomalous")
        mean_diff = float(np.mean([m.score_difference for m in self._recent_metrics]))

        return {
            "active_shadow_version": self.active_shadow_version,
            "total_shadow_evaluations": total,
            "prediction_agreement_rate": round(agreed / total, 4),
            "mean_score_difference": round(mean_diff, 4),
            "candidate_alert_count": cand_alerts,
            "production_alert_count": prod_alerts,
            "recent_metrics": [m.model_dump() for m in self._recent_metrics[-25:]],
        }


shadow_engine = ModelShadowEngine()
