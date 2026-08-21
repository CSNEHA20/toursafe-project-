import logging
from typing import Optional
from ...schemas.telemetry import QualityMetrics, QualityStateEnum

logger = logging.getLogger("toursafe.telemetry.quality")


class TelemetryQualityEvaluator:
    """
    Evaluates empirical data quality across GPS, IMU, synchronization, and network channels.
    Produces an explainable combined quality assessment.
    """

    @staticmethod
    def evaluate_gps_quality(accuracy_meters: Optional[float]) -> QualityStateEnum:
        if accuracy_meters is None:
            return QualityStateEnum.UNAVAILABLE
        if accuracy_meters <= 10.0:
            return QualityStateEnum.EXCELLENT
        elif accuracy_meters <= 25.0:
            return QualityStateEnum.GOOD
        elif accuracy_meters <= 50.0:
            return QualityStateEnum.DEGRADED
        else:
            return QualityStateEnum.POOR

    @staticmethod
    def evaluate_imu_quality(
        observed_frequency_hz: Optional[float],
        target_hz: float = 50.0,
        gap_duration_ms: float = 0.0,
    ) -> QualityStateEnum:
        if observed_frequency_hz is None:
            return QualityStateEnum.GOOD
        if gap_duration_ms > 500.0:
            return QualityStateEnum.POOR
        if gap_duration_ms > 200.0:
            return QualityStateEnum.DEGRADED

        ratio = observed_frequency_hz / max(1.0, target_hz)
        if 0.85 <= ratio <= 1.25:
            return QualityStateEnum.EXCELLENT
        elif 0.65 <= ratio <= 1.45:
            return QualityStateEnum.GOOD
        elif 0.40 <= ratio:
            return QualityStateEnum.DEGRADED
        else:
            return QualityStateEnum.POOR

    @staticmethod
    def evaluate_sync_quality(delta_ms: float) -> QualityStateEnum:
        abs_delta = abs(delta_ms)
        if abs_delta <= 10.0:
            return QualityStateEnum.EXCELLENT
        elif abs_delta <= 25.0:
            return QualityStateEnum.GOOD
        elif abs_delta <= 60.0:
            return QualityStateEnum.DEGRADED
        else:
            return QualityStateEnum.POOR

    @staticmethod
    def evaluate_network_quality(
        transport_latency_ms: Optional[float],
        out_of_order_ratio: float = 0.0,
    ) -> QualityStateEnum:
        if out_of_order_ratio > 0.3:
            return QualityStateEnum.POOR
        if transport_latency_ms is None:
            return QualityStateEnum.GOOD
        if transport_latency_ms <= 150.0:
            return QualityStateEnum.EXCELLENT
        elif transport_latency_ms <= 400.0:
            return QualityStateEnum.GOOD
        elif transport_latency_ms <= 1200.0:
            return QualityStateEnum.DEGRADED
        else:
            return QualityStateEnum.POOR

    @classmethod
    def calculate_overall_quality(
        cls,
        gps_quality: QualityStateEnum,
        imu_quality: QualityStateEnum,
        sync_quality: QualityStateEnum,
        network_quality: QualityStateEnum,
    ) -> QualityStateEnum:
        order = [
            QualityStateEnum.EXCELLENT,
            QualityStateEnum.GOOD,
            QualityStateEnum.DEGRADED,
            QualityStateEnum.POOR,
            QualityStateEnum.UNAVAILABLE,
        ]

        active_qualities = [imu_quality, sync_quality, network_quality]
        if gps_quality != QualityStateEnum.UNAVAILABLE:
            active_qualities.append(gps_quality)

        worst_idx = max(order.index(q) for q in active_qualities)
        return order[worst_idx]

    @classmethod
    def compute_metrics(
        cls,
        gps_accuracy: Optional[float] = None,
        observed_imu_hz: Optional[float] = None,
        target_hz: float = 50.0,
        sync_delta_ms: float = 0.0,
        transport_latency_ms: Optional[float] = None,
        last_gap_duration_ms: float = 0.0,
        out_of_order_ratio: float = 0.0,
    ) -> QualityMetrics:
        gps_q = cls.evaluate_gps_quality(gps_accuracy)
        imu_q = cls.evaluate_imu_quality(observed_imu_hz, target_hz, last_gap_duration_ms)
        sync_q = cls.evaluate_sync_quality(sync_delta_ms)
        net_q = cls.evaluate_network_quality(transport_latency_ms, out_of_order_ratio)
        overall_q = cls.calculate_overall_quality(gps_q, imu_q, sync_q, net_q)

        return QualityMetrics(
            gps_quality=gps_q,
            imu_quality=imu_q,
            synchronization_quality=sync_q,
            network_quality=net_q,
            overall_quality=overall_q,
            sensor_timestamp_delta_ms=round(sync_delta_ms, 2),
            observed_frequency_hz=round(observed_imu_hz, 2) if observed_imu_hz is not None else None,
            transport_latency_ms=round(transport_latency_ms, 2) if transport_latency_ms is not None else None,
        )


quality_evaluator = TelemetryQualityEvaluator()
