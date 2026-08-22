"""
TourSafe Analytical Aggregation Engine

Implements high-performance, deterministic MongoDB aggregation pipelines and
statistical processors for canonical operational datasets.
Provides time-bucketing, percentile calculation, noise-filtered GPS path geometry,
spatial grid clustering with privacy suppression, and operational KPI calculations.
"""

from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from ...core import database as db_core
from ...schemas.analytics import (
    DataFreshnessMeta,
    HeatmapCell,
    HeatmapMetricType,
    HeatmapResponse,
    IncidentDurationMetrics,
    QualityStatus,
    TimeGranularity,
    TimeSeriesPoint,
)

logger = logging.getLogger("toursafe.analytics.aggregation")

# Maximum allowed query window (in days) to prevent memory exhaustion
MAX_HOURLY_WINDOW_DAYS = 30
MAX_DAILY_WINDOW_DAYS = 90
MAX_MONTHLY_WINDOW_DAYS = 365

# Privacy suppression threshold for geographic heatmap cells
MIN_HEATMAP_SAMPLE_K = 3

# GPS Filtering thresholds
GPS_MAX_VALID_ACCURACY_METERS = 100.0
GPS_MAX_PLAUSIBLE_SPEED_MPS = 70.0  # ~252 km/h (covers high-speed trains/cars, filters jumps)
GPS_MIN_MOVEMENT_METERS = 2.0


# ---------------------------------------------------------------------------
# Geohash Encoding Utility (Pure Python, Zero External Dependency)
# ---------------------------------------------------------------------------
_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_BASE32_MAP = {c: i for i, c in enumerate(_BASE32)}


def encode_geohash(latitude: float, longitude: float, precision: int = 6) -> str:
    """
    Encodes (latitude, longitude) into standard Base32 geohash string.
    Precision 5: ~4.9km x 4.9km cell
    Precision 6: ~1.2km x 0.6km cell
    """
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    geohash = []
    bits = [16, 8, 4, 2, 1]
    bit = 0
    ch = 0
    is_even = True

    while len(geohash) < precision:
        if is_even:
            mid = (lon_interval[0] + lon_interval[1]) / 2.0
            if longitude > mid:
                ch |= bits[bit]
                lon_interval[0] = mid
            else:
                lon_interval[1] = mid
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2.0
            if latitude > mid:
                ch |= bits[bit]
                lat_interval[0] = mid
            else:
                lat_interval[1] = mid

        is_even = not is_even
        if bit < 4:
            bit += 1
        else:
            geohash.append(_BASE32[ch])
            bit = 0
            ch = 0

    return "".join(geohash)


def decode_geohash_center(geohash: str) -> Tuple[float, float]:
    """
    Decodes a geohash string to the center (latitude, longitude) coordinates.
    """
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    is_even = True

    for c in geohash:
        cd = _BASE32_MAP.get(c, 0)
        for mask in [16, 8, 4, 2, 1]:
            if is_even:
                if cd & mask:
                    lon_interval[0] = (lon_interval[0] + lon_interval[1]) / 2.0
                else:
                    lon_interval[1] = (lon_interval[0] + lon_interval[1]) / 2.0
            else:
                if cd & mask:
                    lat_interval[0] = (lat_interval[0] + lat_interval[1]) / 2.0
                else:
                    lat_interval[1] = (lat_interval[0] + lat_interval[1]) / 2.0
            is_even = not is_even

    center_lat = (lat_interval[0] + lat_interval[1]) / 2.0
    center_lon = (lon_interval[0] + lon_interval[1]) / 2.0
    return round(center_lat, 6), round(center_lon, 6)


# ---------------------------------------------------------------------------
# Time Normalization and Statistical Helpers
# ---------------------------------------------------------------------------

def normalize_time_range(
    start_time: Optional[str],
    end_time: Optional[str],
    granularity: TimeGranularity = TimeGranularity.DAY,
) -> Tuple[str, str]:
    """
    Validates and bounds time ranges against maximum query span limits.
    Defaults to last 24 hours if unprovided.
    """
    now = datetime.now(timezone.utc)
    if not end_time:
        end_dt = now
    else:
        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except Exception:
            end_dt = now

    if not start_time:
        if granularity == TimeGranularity.HOUR:
            start_dt = end_dt - timedelta(hours=24)
        elif granularity == TimeGranularity.MONTH:
            start_dt = end_dt - timedelta(days=180)
        else:
            start_dt = end_dt - timedelta(days=7)
    else:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except Exception:
            start_dt = end_dt - timedelta(days=7)

    # Ensure start <= end
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    # Enforce max limits
    span_days = (end_dt - start_dt).total_seconds() / 86400.0
    max_days = (
        MAX_HOURLY_WINDOW_DAYS if granularity == TimeGranularity.HOUR
        else (MAX_MONTHLY_WINDOW_DAYS if granularity == TimeGranularity.MONTH else MAX_DAILY_WINDOW_DAYS)
    )
    if span_days > max_days:
        start_dt = end_dt - timedelta(days=max_days)

    return start_dt.isoformat(), end_dt.isoformat()


def compute_duration_percentiles(durations: List[float]) -> IncidentDurationMetrics:
    """
    Computes count, mean, min, max, P50, P90, and P95 from duration seconds.
    """
    if not durations:
        return IncidentDurationMetrics(count=0)

    sorted_d = sorted(durations)
    n = len(sorted_d)

    def _get_percentile(p: float) -> float:
        k = (n - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_d[int(k)]
        d0 = sorted_d[int(f)] * (c - k)
        d1 = sorted_d[int(c)] * (k - f)
        return d0 + d1

    return IncidentDurationMetrics(
        count=n,
        p50_seconds=round(_get_percentile(50.0), 2),
        p90_seconds=round(_get_percentile(90.0), 2),
        p95_seconds=round(_get_percentile(95.0), 2),
        mean_seconds=round(sum(sorted_d) / n, 2),
        min_seconds=round(sorted_d[0], 2),
        max_seconds=round(sorted_d[-1], 2),
    )


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates great-circle distance between two GPS coordinates in meters.
    """
    R = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


# ---------------------------------------------------------------------------
# MongoDB Aggregation Pipelines Engine
# ---------------------------------------------------------------------------

class AggregationEngine:
    """
    Central aggregation engine executing performant queries across canonical collections.
    """

    def _get_db(self):
        return db_core.get_database()

    def _format_time_bucket_key(self, dt: datetime, granularity: TimeGranularity) -> str:
        if granularity == TimeGranularity.HOUR:
            return dt.strftime("%Y-%m-%dT%H:00:00Z")
        elif granularity == TimeGranularity.MONTH:
            return dt.strftime("%Y-%m-01T00:00:00Z")
        elif granularity == TimeGranularity.WEEK:
            start_of_week = dt - timedelta(days=dt.weekday())
            return start_of_week.strftime("%Y-%m-%dT00:00:00Z")
        else:
            return dt.strftime("%Y-%m-%dT00:00:00Z")

    async def calculate_travel_distance_km(
        self,
        tourist_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Tuple[float, int, List[float], int]:
        """
        Calculates cumulative distance from ordered GPS points with noise and jump rejection.
        Returns: (distance_km, valid_points_count, accuracies, tracking_gaps_count)
        """
        db = self._get_db()
        query: Dict[str, Any] = {"tourist_id": tourist_id}
        if session_id:
            query["session_id"] = session_id

        if start_time or end_time:
            t_filter: Dict[str, Any] = {}
            if start_time:
                t_filter["$gte"] = start_time
            if end_time:
                t_filter["$lte"] = end_time
            query["timestamp"] = t_filter

        cursor = db.location_history.find(query).sort("timestamp", 1)
        raw_points = []
        async for doc in cursor:
            raw_points.append(doc)

        if not raw_points:
            return 0.0, 0, [], 0

        # Sort explicitly in memory to guarantee chronological order
        points = []
        for p in raw_points:
            ts_str = p.get("timestamp")
            lat = p.get("latitude")
            lon = p.get("longitude")
            acc = p.get("accuracy")
            if ts_str and lat is not None and lon is not None:
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    points.append({"dt": dt, "lat": lat, "lon": lon, "acc": acc or 10.0})
                except Exception:
                    continue

        points.sort(key=lambda x: x["dt"])
        if len(points) < 2:
            return 0.0, len(points), [p["acc"] for p in points], 0

        total_meters = 0.0
        valid_points_count = 1
        accuracies = [points[0]["acc"]]
        tracking_gaps_count = 0

        prev = points[0]
        for curr in points[1:]:
            # Accuracy filter
            if curr["acc"] > GPS_MAX_VALID_ACCURACY_METERS:
                continue

            accuracies.append(curr["acc"])
            time_delta_sec = max(0.001, (curr["dt"] - prev["dt"]).total_seconds())

            # Detect tracking gap (> 5 minutes without location)
            if time_delta_sec > 300.0:
                tracking_gaps_count += 1

            dist_m = haversine_distance_meters(prev["lat"], prev["lon"], curr["lat"], curr["lon"])

            # Jump and noise filtering:
            # - If distance is smaller than GPS noise floor (2m), skip distance increment
            # - If speed exceeds plausible threshold (70 m/s ~ 252 km/h), treat as GPS jump and do not sum
            if dist_m >= GPS_MIN_MOVEMENT_METERS:
                speed_mps = dist_m / time_delta_sec
                if speed_mps <= GPS_MAX_PLAUSIBLE_SPEED_MPS:
                    total_meters += dist_m
                    valid_points_count += 1
                    prev = curr
                else:
                    logger.debug("Rejected GPS jump: %0.1fm in %0.1fs (%0.1f m/s)", dist_m, time_delta_sec, speed_mps)
            else:
                # Stationary sample
                valid_points_count += 1
                prev = curr

        return round(total_meters / 1000.0, 3), valid_points_count, accuracies, tracking_gaps_count

    async def aggregate_spatial_heatmap(
        self,
        metric_type: HeatmapMetricType,
        start_time: str,
        end_time: str,
        precision: int = 5,  # ~4.9km cells
    ) -> HeatmapResponse:
        """
        Aggregates operational events into spatial geohash grid cells with k-anonymity privacy suppression.
        """
        db = self._get_db()
        cell_data: Dict[str, Dict[str, Any]] = {}  # geohash -> {count, tourists: set(), lat, lon}

        if metric_type in (HeatmapMetricType.TOURIST_DENSITY, HeatmapMetricType.RESPONSE_ACTIVITY):
            col = db.location_history if metric_type == HeatmapMetricType.TOURIST_DENSITY else db.responder_locations
            query = {"timestamp": {"$gte": start_time, "$lte": end_time}}
            cursor = col.find(query, {"latitude": 1, "longitude": 1, "tourist_id": 1, "responder_id": 1})
            async for doc in cursor:
                lat = doc.get("latitude")
                lon = doc.get("longitude")
                uid = doc.get("tourist_id") or doc.get("responder_id") or "unknown"
                if lat is not None and lon is not None:
                    gh = encode_geohash(lat, lon, precision)
                    if gh not in cell_data:
                        cell_data[gh] = {"count": 0, "entities": set(), "lat": lat, "lon": lon}
                    cell_data[gh]["count"] += 1
                    cell_data[gh]["entities"].add(uid)

        elif metric_type == HeatmapMetricType.INCIDENTS:
            query = {"started_at": {"$gte": start_time, "$lte": end_time}}
            cursor = db.incidents.find(query, {"location_data": 1, "tourist_id": 1})
            async for doc in cursor:
                loc = doc.get("location_data") or {}
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                uid = doc.get("tourist_id") or "unknown"
                if lat is not None and lon is not None:
                    gh = encode_geohash(lat, lon, precision)
                    if gh not in cell_data:
                        cell_data[gh] = {"count": 0, "entities": set(), "lat": lat, "lon": lon}
                    cell_data[gh]["count"] += 1
                    cell_data[gh]["entities"].add(uid)

        elif metric_type == HeatmapMetricType.SOS_EVENTS:
            query = {"timestamp": {"$gte": start_time, "$lte": end_time}}
            cursor = db.sos_events.find(query, {"location": 1, "tourist_id": 1})
            async for doc in cursor:
                loc = doc.get("location") or {}
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                uid = doc.get("tourist_id") or "unknown"
                if lat is not None and lon is not None:
                    gh = encode_geohash(lat, lon, precision)
                    if gh not in cell_data:
                        cell_data[gh] = {"count": 0, "entities": set(), "lat": lat, "lon": lon}
                    cell_data[gh]["count"] += 1
                    cell_data[gh]["entities"].add(uid)

        elif metric_type == HeatmapMetricType.ANOMALIES:
            query = {"started_at": {"$gte": start_time, "$lte": end_time}}
            cursor = db.anomaly_events.find(query, {"last_location": 1, "tourist_id": 1})
            async for doc in cursor:
                loc = doc.get("last_location") or {}
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                uid = doc.get("tourist_id") or "unknown"
                if lat is not None and lon is not None:
                    gh = encode_geohash(lat, lon, precision)
                    if gh not in cell_data:
                        cell_data[gh] = {"count": 0, "entities": set(), "lat": lat, "lon": lon}
                    cell_data[gh]["count"] += 1
                    cell_data[gh]["entities"].add(uid)

        # Build response with privacy suppression
        cells: List[HeatmapCell] = []
        suppressed_count = 0
        for gh, val in cell_data.items():
            unique_count = len(val["entities"])
            center_lat, center_lon = decode_geohash_center(gh)
            is_suppressed = unique_count < MIN_HEATMAP_SAMPLE_K
            if is_suppressed:
                suppressed_count += 1

            cells.append(
                HeatmapCell(
                    geohash=gh,
                    latitude=center_lat,
                    longitude=center_lon,
                    weight=float(val["count"]) if not is_suppressed else 0.0,
                    sample_count=val["count"],
                    is_suppressed=is_suppressed,
                )
            )

        cells.sort(key=lambda x: x.weight, reverse=True)
        return HeatmapResponse(
            layer_type=metric_type,
            cells=cells,
            total_cells=len(cells),
            suppressed_cells_count=suppressed_count,
            privacy_threshold_k=MIN_HEATMAP_SAMPLE_K,
            freshness=DataFreshnessMeta(
                data_range_start=start_time,
                data_range_end=end_time,
                sample_size=sum(c.sample_count for c in cells),
            ),
        )


aggregation_engine = AggregationEngine()
