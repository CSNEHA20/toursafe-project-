"""
TourSafe - Geospatial Geometry Engine

Implements RFC 7946 GeoJSON containment, distance, and boundary calculations:
- Ray casting / Jordan curve point-in-polygon with holes support
- MultiPolygon containment support
- WGS84 geodesic distance (Haversine) and point-to-segment perpendicular distance in meters
- Explicit boundary detection (tolerance <= 1.0 meter)
- Bounding-box pre-filtering for computational efficiency
- Strict [longitude, latitude] coordinate enforcement
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from .types import ContainmentResult, ContainmentStatus, MembershipConfidence

# Earth mean radius in meters (WGS84)
EARTH_RADIUS_METERS = 6371008.8
EPSILON_DEGREES = 1e-9
BOUNDARY_TOLERANCE_METERS = 1.0  # Points within 1.0m of an edge are classified as BOUNDARY


def geodesic_distance_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Computes Great-Circle distance between two [lon, lat] points on WGS84 sphere in meters.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def point_to_segment_distance_meters(
    p_lon: float, p_lat: float,
    a_lon: float, a_lat: float,
    b_lon: float, b_lat: float
) -> float:
    """
    Computes shortest distance in meters from point P to line segment AB.
    Uses equirectangular planar projection centered at average latitude.
    """
    lat_rad = math.radians((a_lat + b_lat + p_lat) / 3.0)
    cos_lat = math.cos(lat_rad)
    m_per_deg_lat = (math.pi / 180.0) * EARTH_RADIUS_METERS
    m_per_deg_lon = m_per_deg_lat * cos_lat

    # Convert to metric coordinates relative to A (origin = 0,0)
    px = (p_lon - a_lon) * m_per_deg_lon
    py = (p_lat - a_lat) * m_per_deg_lat
    bx = (b_lon - a_lon) * m_per_deg_lon
    by = (b_lat - a_lat) * m_per_deg_lat

    seg_len_sq = bx * bx + by * by

    if seg_len_sq <= 1e-12:
        # Segment is a single point A == B
        return math.sqrt(px * px + py * py)

    # Project P onto line segment AB with parameter t
    t = (px * bx + py * by) / seg_len_sq
    t_clamped = max(0.0, min(1.0, t))

    closest_x = t_clamped * bx
    closest_y = t_clamped * by

    dx = px - closest_x
    dy = py - closest_y
    return math.sqrt(dx * dx + dy * dy)


def point_in_linear_ring(p_lon: float, p_lat: float, ring: List[List[float]]) -> Tuple[bool, bool]:
    """
    Ray-casting algorithm to test whether point (p_lon, p_lat) is inside a closed linear ring.
    Returns:
        (is_inside, is_on_boundary)
    """
    n = len(ring)
    if n < 4:
        return False, False

    inside = False
    is_on_boundary = False

    for i in range(n - 1):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[i + 1][0], ring[i + 1][1]

        # Check vertex coincidence
        if abs(p_lon - x1) < EPSILON_DEGREES and abs(p_lat - y1) < EPSILON_DEGREES:
            return True, True

        # Check if point lies on segment
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)

        if min_x - EPSILON_DEGREES <= p_lon <= max_x + EPSILON_DEGREES and \
           min_y - EPSILON_DEGREES <= p_lat <= max_y + EPSILON_DEGREES:
            dist = point_to_segment_distance_meters(p_lon, p_lat, x1, y1, x2, y2)
            if dist <= BOUNDARY_TOLERANCE_METERS:
                is_on_boundary = True

        # Ray casting test: ray extending to the right (+x)
        # Does the edge cross the horizontal ray at y = p_lat?
        if ((y1 > p_lat) != (y2 > p_lat)):
            if abs(y2 - y1) > EPSILON_DEGREES:
                x_intersect = x1 + (p_lat - y1) * (x2 - x1) / (y2 - y1)
                if abs(p_lon - x_intersect) < EPSILON_DEGREES:
                    is_on_boundary = True
                elif p_lon < x_intersect:
                    inside = not inside

    return inside, is_on_boundary


def point_in_polygon(p_lon: float, p_lat: float, polygon_coords: List[List[List[float]]]) -> Tuple[bool, bool]:
    """
    Evaluates containment for a GeoJSON Polygon with outer ring and optional interior hole rings.
    - Outer ring: polygon_coords[0] (point must be inside)
    - Hole rings: polygon_coords[1:] (point must NOT be inside holes)
    Returns:
        (is_contained, is_on_boundary)
    """
    if not polygon_coords or len(polygon_coords) == 0:
        return False, False

    outer_ring = polygon_coords[0]
    inside_outer, boundary_outer = point_in_linear_ring(p_lon, p_lat, outer_ring)

    if boundary_outer:
        return True, True

    if not inside_outer:
        return False, False

    # Check holes
    for hole_idx in range(1, len(polygon_coords)):
        hole_ring = polygon_coords[hole_idx]
        inside_hole, boundary_hole = point_in_linear_ring(p_lon, p_lat, hole_ring)
        if boundary_hole:
            return True, True
        if inside_hole:
            # Point is inside a hole -> NOT inside polygon
            return False, False

    return True, False


def point_in_multipolygon(p_lon: float, p_lat: float, multipoly_coords: List[List[List[List[float]]]]) -> Tuple[bool, bool]:
    """
    Evaluates containment for a GeoJSON MultiPolygon (list of Polygons).
    Returns (True, on_boundary) if inside any member polygon.
    """
    any_boundary = False
    for poly_coords in multipoly_coords:
        inside, on_boundary = point_in_polygon(p_lon, p_lat, poly_coords)
        if on_boundary:
            any_boundary = True
        if inside:
            return True, on_boundary

    return False, any_boundary


def distance_to_geometry_boundary_meters(p_lon: float, p_lat: float, boundary: Dict[str, Any]) -> float:
    """
    Calculates the minimum geodesic distance in meters from point P to any edge of the zone boundary.
    """
    geom_type = boundary.get("type", "Polygon")
    coords = boundary.get("coordinates", [])
    min_dist = float("inf")

    if geom_type == "Polygon":
        for ring in coords:
            n = len(ring)
            for i in range(n - 1):
                d = point_to_segment_distance_meters(
                    p_lon, p_lat,
                    ring[i][0], ring[i][1],
                    ring[i + 1][0], ring[i + 1][1]
                )
                if d < min_dist:
                    min_dist = d
    elif geom_type == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                n = len(ring)
                for i in range(n - 1):
                    d = point_to_segment_distance_meters(
                        p_lon, p_lat,
                        ring[i][0], ring[i][1],
                        ring[i + 1][0], ring[i + 1][1]
                    )
                    if d < min_dist:
                        min_dist = d

    return min_dist if min_dist != float("inf") else 0.0


def bounding_box_for_geometry(boundary: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """
    Calculates bounding box (min_lon, min_lat, max_lon, max_lat) for GeoJSON Polygon/MultiPolygon.
    """
    geom_type = boundary.get("type", "Polygon")
    coords = boundary.get("coordinates", [])
    lons: List[float] = []
    lats: List[float] = []

    if geom_type == "Polygon":
        for ring in coords:
            for pt in ring:
                lons.append(pt[0])
                lats.append(pt[1])
    elif geom_type == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                for pt in ring:
                    lons.append(pt[0])
                    lats.append(pt[1])

    if not lons or not lats:
        return 0.0, 0.0, 0.0, 0.0

    return min(lons), min(lats), max(lons), max(lats)


def is_point_in_bounding_box(
    p_lon: float, p_lat: float,
    bbox: Tuple[float, float, float, float],
    buffer_meters: float = 0.0
) -> bool:
    """
    Fast O(1) bounding box check with optional buffer margin in meters.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    if buffer_meters > 0:
        lat_rad = math.radians(p_lat)
        deg_lat_buf = buffer_meters / ((math.pi / 180.0) * EARTH_RADIUS_METERS)
        deg_lon_buf = deg_lat_buf / max(0.01, math.cos(lat_rad))
        min_lon -= deg_lon_buf
        max_lon += deg_lon_buf
        min_lat -= deg_lat_buf
        max_lat += deg_lat_buf

    return min_lon <= p_lon <= max_lon and min_lat <= p_lat <= max_lat


def evaluate_point_containment(
    latitude: float,
    longitude: float,
    accuracy_meters: Optional[float],
    boundary_geojson: Dict[str, Any],
) -> ContainmentResult:
    """
    Comprehensive containment evaluation of a GPS sample against a GeoJSON zone boundary:
    1. Bounding box pre-check
    2. Precise Ray-Casting / Hole Point-in-Polygon containment
    3. Geodesic distance to boundary in meters
    4. GPS accuracy uncertainty modeling
    5. Confidence calculation
    """
    acc = float(accuracy_meters) if accuracy_meters is not None and accuracy_meters > 0 else 10.0
    p_lon = float(longitude)
    p_lat = float(latitude)

    geom_type = boundary_geojson.get("type", "Polygon")
    coords = boundary_geojson.get("coordinates", [])

    # 1. Exact Point-in-Polygon check
    if geom_type == "Polygon":
        is_inside, on_boundary = point_in_polygon(p_lon, p_lat, coords)
    elif geom_type == "MultiPolygon":
        is_inside, on_boundary = point_in_multipolygon(p_lon, p_lat, coords)
    else:
        is_inside, on_boundary = False, False

    # 2. Geodesic Distance to Boundary
    dist_to_boundary = distance_to_geometry_boundary_meters(p_lon, p_lat, boundary_geojson)

    # 3. Boundary classification
    if on_boundary or dist_to_boundary <= BOUNDARY_TOLERANCE_METERS:
        is_boundary = True
        containment_status = ContainmentStatus.BOUNDARY
    elif is_inside:
        is_boundary = False
        containment_status = ContainmentStatus.INSIDE
    else:
        is_boundary = False
        containment_status = ContainmentStatus.OUTSIDE

    # 4. Confidence Score Calculation:
    # Based on ratio of distance to boundary vs GPS accuracy uncertainty radius
    # If accuracy circle is small relative to boundary distance, confidence is high (1.0).
    # If accuracy circle overlaps boundary (accuracy > dist), confidence diminishes.
    if is_boundary:
        confidence_score = 0.5
        confidence_level = MembershipConfidence.UNCERTAIN
    else:
        # Ratio of margin to uncertainty radius
        ratio = dist_to_boundary / max(1.0, acc)
        if ratio >= 2.0 and acc <= 25.0:
            confidence_score = min(1.0, 0.8 + 0.1 * ratio)
            confidence_level = MembershipConfidence.HIGH
        elif ratio >= 1.0 and acc <= 40.0:
            confidence_score = min(0.85, 0.6 + 0.25 * ratio)
            confidence_level = MembershipConfidence.MEDIUM
        elif ratio >= 0.5:
            confidence_score = max(0.3, min(0.6, 0.4 + 0.2 * ratio))
            confidence_level = MembershipConfidence.LOW
        else:
            # Accuracy circle clearly overlaps boundary
            confidence_score = max(0.1, min(0.4, 0.2 + 0.2 * ratio))
            confidence_level = MembershipConfidence.UNCERTAIN
            if not is_boundary and acc > 50.0:
                containment_status = ContainmentStatus.UNCERTAIN

    return ContainmentResult(
        is_contained=is_inside,
        is_boundary=is_boundary,
        distance_to_boundary_meters=round(dist_to_boundary, 2),
        accuracy_meters=round(acc, 2),
        confidence_score=round(confidence_score, 3),
        confidence_level=confidence_level,
        containment_status=containment_status,
    )
