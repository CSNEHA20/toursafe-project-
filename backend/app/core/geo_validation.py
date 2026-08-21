"""
TourSafe - GeoJSON Geometry Validation Module

Validates RFC 7946 compliant GeoJSON geometry:
- Coordinates order: [longitude, latitude]
- Longitude range: [-180.0, 180.0]
- Latitude range: [-90.0, 90.0]
- Point structure: [lon, lat]
- Polygon structure: Array of LinearRings (minimum 4 coordinates, first == last)
- MultiPolygon structure: Array of Polygons
"""

from typing import Any, Dict, List, Tuple, Union


class GeoValidationError(ValueError):
    """Raised when GeoJSON geometry fails RFC 7946 validation."""
    pass


def validate_coordinate_pair(coord: Any, path: str = "coordinate") -> Tuple[float, float]:
    """Validate a single [longitude, latitude] coordinate pair."""
    if not isinstance(coord, (list, tuple)):
        raise GeoValidationError(f"{path}: coordinate must be a list or tuple of [longitude, latitude], got {type(coord).__name__}")
    
    if len(coord) < 2 or len(coord) > 3:
        raise GeoValidationError(f"{path}: coordinate pair must have 2 elements [longitude, latitude] (optional altitude ignored), got {len(coord)} elements")
    
    lon, lat = coord[0], coord[1]
    
    if not isinstance(lon, (int, float)) or isinstance(lon, bool):
        raise GeoValidationError(f"{path}: longitude must be a number, got {type(lon).__name__}")
    if not isinstance(lat, (int, float)) or isinstance(lat, bool):
        raise GeoValidationError(f"{path}: latitude must be a number, got {type(lat).__name__}")
    
    lon_f = float(lon)
    lat_f = float(lat)
    
    if lon_f < -180.0 or lon_f > 180.0:
        raise GeoValidationError(f"{path}: longitude {lon_f} out of range [-180.0, 180.0]")
    if lat_f < -90.0 or lat_f > 90.0:
        raise GeoValidationError(f"{path}: latitude {lat_f} out of range [-90.0, 90.0]")
    
    return lon_f, lat_f


def validate_point_geometry(geom: Dict[str, Any], path: str = "geometry") -> Dict[str, Any]:
    """Validate a GeoJSON Point object."""
    if not isinstance(geom, dict):
        raise GeoValidationError(f"{path}: Point geometry must be a dictionary")
    
    geom_type = geom.get("type")
    if geom_type != "Point":
        raise GeoValidationError(f"{path}: expected type 'Point', got '{geom_type}'")
    
    coords = geom.get("coordinates")
    if coords is None:
        raise GeoValidationError(f"{path}: missing 'coordinates' in Point geometry")
    
    lon, lat = validate_coordinate_pair(coords, path=f"{path}.coordinates")
    return {"type": "Point", "coordinates": [lon, lat]}


def validate_linear_ring(ring: Any, path: str = "ring") -> List[List[float]]:
    """Validate a GeoJSON LinearRing for a polygon."""
    if not isinstance(ring, (list, tuple)):
        raise GeoValidationError(f"{path}: linear ring must be a list of coordinate pairs")
    
    if len(ring) < 4:
        raise GeoValidationError(f"{path}: linear ring must have at least 4 coordinate positions (got {len(ring)})")
    
    validated_coords: List[List[float]] = []
    for idx, pt in enumerate(ring):
        lon, lat = validate_coordinate_pair(pt, path=f"{path}[{idx}]")
        validated_coords.append([lon, lat])
    
    # Check closure (first coordinate equals last coordinate)
    first_pt = validated_coords[0]
    last_pt = validated_coords[-1]
    
    # Check for strict or epsilon equality
    if abs(first_pt[0] - last_pt[0]) > 1e-9 or abs(first_pt[1] - last_pt[1]) > 1e-9:
        raise GeoValidationError(
            f"{path}: linear ring must be closed (first coordinate {first_pt} must match last coordinate {last_pt})"
        )
    
    return validated_coords


def validate_polygon_geometry(geom: Dict[str, Any], path: str = "geometry") -> Dict[str, Any]:
    """Validate a GeoJSON Polygon object."""
    if not isinstance(geom, dict):
        raise GeoValidationError(f"{path}: Polygon geometry must be a dictionary")
    
    geom_type = geom.get("type")
    if geom_type != "Polygon":
        raise GeoValidationError(f"{path}: expected type 'Polygon', got '{geom_type}'")
    
    coords = geom.get("coordinates")
    if not isinstance(coords, (list, tuple)) or len(coords) == 0:
        raise GeoValidationError(f"{path}: Polygon coordinates must be a non-empty list of linear rings")
    
    validated_rings: List[List[List[float]]] = []
    for ring_idx, ring in enumerate(coords):
        valid_ring = validate_linear_ring(ring, path=f"{path}.coordinates[{ring_idx}]")
        validated_rings.append(valid_ring)
    
    return {"type": "Polygon", "coordinates": validated_rings}


def validate_multipolygon_geometry(geom: Dict[str, Any], path: str = "geometry") -> Dict[str, Any]:
    """Validate a GeoJSON MultiPolygon object."""
    if not isinstance(geom, dict):
        raise GeoValidationError(f"{path}: MultiPolygon geometry must be a dictionary")
    
    geom_type = geom.get("type")
    if geom_type != "MultiPolygon":
        raise GeoValidationError(f"{path}: expected type 'MultiPolygon', got '{geom_type}'")
    
    coords = geom.get("coordinates")
    if not isinstance(coords, (list, tuple)) or len(coords) == 0:
        raise GeoValidationError(f"{path}: MultiPolygon coordinates must be a non-empty list of polygons")
    
    validated_polys: List[List[List[List[float]]]] = []
    for poly_idx, poly in enumerate(coords):
        if not isinstance(poly, (list, tuple)) or len(poly) == 0:
            raise GeoValidationError(f"{path}.coordinates[{poly_idx}]: polygon in MultiPolygon must be a non-empty list of rings")
        
        poly_rings: List[List[List[float]]] = []
        for ring_idx, ring in enumerate(poly):
            valid_ring = validate_linear_ring(ring, path=f"{path}.coordinates[{poly_idx}][{ring_idx}]")
            poly_rings.append(valid_ring)
        validated_polys.append(poly_rings)
    
    return {"type": "MultiPolygon", "coordinates": validated_polys}


def validate_zone_geometry(geom: Dict[str, Any], path: str = "boundary") -> Dict[str, Any]:
    """Validate either Polygon or MultiPolygon geometry for zone boundaries."""
    if not isinstance(geom, dict):
        raise GeoValidationError(f"{path}: geometry must be a dictionary")
    
    geom_type = geom.get("type")
    if geom_type == "Polygon":
        return validate_polygon_geometry(geom, path=path)
    elif geom_type == "MultiPolygon":
        return validate_multipolygon_geometry(geom, path=path)
    else:
        raise GeoValidationError(f"{path}: unsupported geometry type '{geom_type}'. Zone boundary must be 'Polygon' or 'MultiPolygon'")


def compute_polygon_center(geom: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a representative center point [longitude, latitude]
    from a Polygon or MultiPolygon geometry using bounding box midpoint.
    """
    geom_type = geom.get("type")
    coords = geom.get("coordinates", [])
    
    lons: List[float] = []
    lats: List[float] = []
    
    if geom_type == "Polygon" and coords:
        for ring in coords:
            for pt in ring:
                lons.append(pt[0])
                lats.append(pt[1])
    elif geom_type == "MultiPolygon" and coords:
        for poly in coords:
            for ring in poly:
                for pt in ring:
                    lons.append(pt[0])
                    lats.append(pt[1])
    
    if not lons or not lats:
        return {"type": "Point", "coordinates": [0.0, 0.0]}
    
    center_lon = round((min(lons) + max(lons)) / 2.0, 6)
    center_lat = round((min(lats) + max(lats)) / 2.0, 6)
    
    return {"type": "Point", "coordinates": [center_lon, center_lat]}
