"""
TourSafe Central Metrics Registry & Observability Collector.
Provides real-time tracking of Golden Signals (Latency, Traffic, Errors, Saturation),
subsystem-specific telemetry, Prometheus export, and structured metrics query APIs.
"""

import math
import os
import time
from collections import deque
from typing import Any, Dict, List, Optional
import psutil


class SlidingWindowLatency:
    """Sliding window latency estimator with p50, p95, p99 percentiles."""

    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.samples: deque = deque(maxlen=max_samples)

    def record(self, latency_ms: float):
        if latency_ms >= 0:
            self.samples.append(latency_ms)

    def get_percentiles(self) -> Dict[str, float]:
        if not self.samples:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "avg": 0.0, "count": 0}
        
        sorted_samples = sorted(self.samples)
        n = len(sorted_samples)
        
        def pct(p: float) -> float:
            idx = max(0, min(n - 1, int(math.ceil(p * n)) - 1))
            return round(sorted_samples[idx], 2)

        return {
            "p50": pct(0.50),
            "p90": pct(0.90),
            "p95": pct(0.95),
            "p99": pct(0.99),
            "avg": round(sum(sorted_samples) / n, 2),
            "count": n,
        }

    def clear(self):
        self.samples.clear()


class GoldenSignals:
    """Core SRE Golden Signals tracker."""

    def __init__(self):
        self.requests_total: int = 0
        self.requests_2xx: int = 0
        self.requests_4xx: int = 0
        self.requests_5xx: int = 0
        self.dependency_errors: int = 0
        self.latency_tracker = SlidingWindowLatency(max_samples=2000)

    def record_request(self, status_code: int, duration_ms: float):
        self.requests_total += 1
        if 200 <= status_code < 400:
            self.requests_2xx += 1
        elif 400 <= status_code < 500:
            self.requests_4xx += 1
        elif status_code >= 500:
            self.requests_5xx += 1
        self.latency_tracker.record(duration_ms)

    def record_dependency_error(self):
        self.dependency_errors += 1

    def get_summary(self) -> Dict[str, Any]:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        cpu_pct = process.cpu_percent(interval=None)

        return {
            "traffic": {
                "total_requests": self.requests_total,
                "requests_2xx": self.requests_2xx,
                "requests_4xx": self.requests_4xx,
                "requests_5xx": self.requests_5xx,
            },
            "latency_ms": self.latency_tracker.get_percentiles(),
            "errors": {
                "error_rate_5xx": round((self.requests_5xx / max(1, self.requests_total)) * 100, 3),
                "client_error_rate_4xx": round((self.requests_4xx / max(1, self.requests_total)) * 100, 3),
                "dependency_errors": self.dependency_errors,
            },
            "saturation": {
                "cpu_percent": round(cpu_pct, 1),
                "memory_rss_mb": round(mem_info.rss / (1024 * 1024), 2),
                "memory_vms_mb": round(mem_info.vms / (1024 * 1024), 2),
                "system_memory_percent": psutil.virtual_memory().percent,
            },
        }


class SubsystemMetrics:
    """Specialized metrics for TourSafe safety subsystems."""

    def __init__(self):
        # Database
        self.db_queries_total: int = 0
        self.db_slow_queries: int = 0  # > 100ms
        self.db_errors: int = 0
        self.db_latency = SlidingWindowLatency(max_samples=1000)

        # Redis
        self.redis_commands_total: int = 0
        self.redis_errors: int = 0
        self.redis_latency = SlidingWindowLatency(max_samples=1000)

        # Queues & Workers
        self.queue_depth: int = 0
        self.queue_processed_total: int = 0
        self.queue_retries_total: int = 0
        self.queue_dead_letter_total: int = 0
        self.queue_oldest_age_sec: float = 0.0

        # Realtime WebSocket
        self.websocket_active_connections: int = 0
        self.websocket_total_connections: int = 0
        self.websocket_reconnects: int = 0
        self.websocket_dropped_frames: int = 0
        self.websocket_latency = SlidingWindowLatency(max_samples=1000)

        # Telemetry Pipeline
        self.telemetry_packets_ingested: int = 0
        self.telemetry_packets_dropped: int = 0
        self.telemetry_sequence_gaps: int = 0
        self.telemetry_offline_backlog: int = 0
        self.telemetry_latency = SlidingWindowLatency(max_samples=1000)

        # SOS & Incident Operations
        self.sos_signals_received: int = 0
        self.sos_processing_failures: int = 0
        self.sos_latency = SlidingWindowLatency(max_samples=500)
        self.incidents_created_total: int = 0
        self.incidents_acknowledged_total: int = 0
        self.incidents_dispatched_total: int = 0
        self.incident_ack_latency = SlidingWindowLatency(max_samples=500)

        # ML & AI Copilot
        self.ml_inferences_total: int = 0
        self.ml_inference_failures: int = 0
        self.ml_latency = SlidingWindowLatency(max_samples=1000)
        self.ai_requests_total: int = 0
        self.ai_timeouts: int = 0
        self.ai_fallbacks: int = 0
        self.ai_latency = SlidingWindowLatency(max_samples=500)

        # Notifications & Integrations
        self.notifications_sent_total: int = 0
        self.notifications_failed_total: int = 0
        self.notifications_fallback_used: int = 0
        self.integration_calls_total: int = 0
        self.integration_circuit_trips: int = 0

    def record_db(self, latency_ms: float, is_error: bool = False):
        self.db_queries_total += 1
        if is_error:
            self.db_errors += 1
        if latency_ms > 100.0:
            self.db_slow_queries += 1
        self.db_latency.record(latency_ms)

    def record_redis(self, latency_ms: float, is_error: bool = False):
        self.redis_commands_total += 1
        if is_error:
            self.redis_errors += 1
        self.redis_latency.record(latency_ms)

    def record_telemetry(self, latency_ms: float, dropped: bool = False, gap: bool = False):
        if dropped:
            self.telemetry_packets_dropped += 1
        else:
            self.telemetry_packets_ingested += 1
            self.telemetry_latency.record(latency_ms)
        if gap:
            self.telemetry_sequence_gaps += 1

    def record_sos(self, latency_ms: float, success: bool = True):
        self.sos_signals_received += 1
        if not success:
            self.sos_processing_failures += 1
        self.sos_latency.record(latency_ms)

    def record_ml(self, latency_ms: float, success: bool = True):
        self.ml_inferences_total += 1
        if not success:
            self.ml_inference_failures += 1
        self.ml_latency.record(latency_ms)

    def record_ai(self, latency_ms: float, is_timeout: bool = False, is_fallback: bool = False):
        self.ai_requests_total += 1
        if is_timeout:
            self.ai_timeouts += 1
        if is_fallback:
            self.ai_fallbacks += 1
        self.ai_latency.record(latency_ms)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "database": {
                "queries_total": self.db_queries_total,
                "slow_queries": self.db_slow_queries,
                "errors": self.db_errors,
                "latency_ms": self.db_latency.get_percentiles(),
            },
            "redis": {
                "commands_total": self.redis_commands_total,
                "errors": self.redis_errors,
                "latency_ms": self.redis_latency.get_percentiles(),
            },
            "queues": {
                "depth": self.queue_depth,
                "processed_total": self.queue_processed_total,
                "retries_total": self.queue_retries_total,
                "dead_letter_total": self.queue_dead_letter_total,
                "oldest_age_sec": self.queue_oldest_age_sec,
            },
            "realtime": {
                "active_connections": self.websocket_active_connections,
                "total_connections": self.websocket_total_connections,
                "reconnects": self.websocket_reconnects,
                "dropped_frames": self.websocket_dropped_frames,
                "latency_ms": self.websocket_latency.get_percentiles(),
            },
            "telemetry": {
                "packets_ingested": self.telemetry_packets_ingested,
                "packets_dropped": self.telemetry_packets_dropped,
                "sequence_gaps": self.telemetry_sequence_gaps,
                "offline_backlog": self.telemetry_offline_backlog,
                "latency_ms": self.telemetry_latency.get_percentiles(),
            },
            "incident_operations": {
                "sos_signals_received": self.sos_signals_received,
                "sos_processing_failures": self.sos_processing_failures,
                "sos_latency_ms": self.sos_latency.get_percentiles(),
                "incidents_created_total": self.incidents_created_total,
                "incidents_acknowledged_total": self.incidents_acknowledged_total,
                "incidents_dispatched_total": self.incidents_dispatched_total,
                "ack_latency_ms": self.incident_ack_latency.get_percentiles(),
            },
            "ml_and_ai": {
                "ml_inferences_total": self.ml_inferences_total,
                "ml_inference_failures": self.ml_inference_failures,
                "ml_latency_ms": self.ml_latency.get_percentiles(),
                "ai_requests_total": self.ai_requests_total,
                "ai_timeouts": self.ai_timeouts,
                "ai_fallbacks": self.ai_fallbacks,
                "ai_latency_ms": self.ai_latency.get_percentiles(),
            },
            "notifications_and_integrations": {
                "notifications_sent_total": self.notifications_sent_total,
                "notifications_failed_total": self.notifications_failed_total,
                "notifications_fallback_used": self.notifications_fallback_used,
                "integration_calls_total": self.integration_calls_total,
                "integration_circuit_trips": self.integration_circuit_trips,
            },
        }


class MetricsCollector:
    """Singleton centralized metrics collector."""

    def __init__(self):
        self.start_time = time.time()
        self.golden = GoldenSignals()
        self.subsystems = SubsystemMetrics()

    def get_uptime_seconds(self) -> float:
        return round(time.time() - self.start_time, 2)

    def get_all_metrics(self) -> Dict[str, Any]:
        return {
            "uptime_seconds": self.get_uptime_seconds(),
            "timestamp": time.time(),
            "golden_signals": self.golden.get_summary(),
            "subsystems": self.subsystems.get_summary(),
        }

    def export_prometheus(self) -> str:
        """Export metrics in standard Prometheus text format."""
        all_m = self.get_all_metrics()
        golden = all_m["golden_signals"]
        sub = all_m["subsystems"]
        
        lines = [
            "# HELP toursafe_uptime_seconds Total runtime of the TourSafe application instance in seconds",
            "# TYPE toursafe_uptime_seconds counter",
            f"toursafe_uptime_seconds {all_m['uptime_seconds']}",
            "",
            "# HELP toursafe_http_requests_total Total HTTP requests served",
            "# TYPE toursafe_http_requests_total counter",
            f'toursafe_http_requests_total{{status="2xx"}} {golden["traffic"]["requests_2xx"]}',
            f'toursafe_http_requests_total{{status="4xx"}} {golden["traffic"]["requests_4xx"]}',
            f'toursafe_http_requests_total{{status="5xx"}} {golden["traffic"]["requests_5xx"]}',
            "",
            "# HELP toursafe_http_request_duration_ms HTTP request latency percentiles in ms",
            "# TYPE toursafe_http_request_duration_ms gauge",
            f'toursafe_http_request_duration_ms{{quantile="0.50"}} {golden["latency_ms"]["p50"]}',
            f'toursafe_http_request_duration_ms{{quantile="0.95"}} {golden["latency_ms"]["p95"]}',
            f'toursafe_http_request_duration_ms{{quantile="0.99"}} {golden["latency_ms"]["p99"]}',
            "",
            "# HELP toursafe_system_cpu_percent Process CPU utilization percentage",
            "# TYPE toursafe_system_cpu_percent gauge",
            f"toursafe_system_cpu_percent {golden['saturation']['cpu_percent']}",
            "",
            "# HELP toursafe_system_memory_rss_mb Process Resident Set Size memory in MB",
            "# TYPE toursafe_system_memory_rss_mb gauge",
            f"toursafe_system_memory_rss_mb {golden['saturation']['memory_rss_mb']}",
            "",
            "# HELP toursafe_sos_signals_total Total SOS emergency signals received",
            "# TYPE toursafe_sos_signals_total counter",
            f"toursafe_sos_signals_total {sub['incident_operations']['sos_signals_received']}",
            f"toursafe_sos_failures_total {sub['incident_operations']['sos_processing_failures']}",
            "",
            "# HELP toursafe_telemetry_packets_total Ingested telemetry count",
            "# TYPE toursafe_telemetry_packets_total counter",
            f"toursafe_telemetry_packets_total {sub['telemetry']['packets_ingested']}",
            f"toursafe_telemetry_dropped_total {sub['telemetry']['packets_dropped']}",
            "",
            "# HELP toursafe_queue_dead_letter_total Dead letter queue size",
            "# TYPE toursafe_queue_dead_letter_total gauge",
            f"toursafe_queue_dead_letter_total {sub['queues']['dead_letter_total']}",
            "",
            "# HELP toursafe_db_slow_queries_total Queries taking > 100ms",
            "# TYPE toursafe_db_slow_queries_total counter",
            f"toursafe_db_slow_queries_total {sub['database']['slow_queries']}",
        ]
        return "\n".join(lines) + "\n"

    def reset_for_tests(self):
        """Reset internal metrics for test suite isolation."""
        self.golden = GoldenSignals()
        self.subsystems = SubsystemMetrics()
        self.start_time = time.time()


metrics_collector = MetricsCollector()
