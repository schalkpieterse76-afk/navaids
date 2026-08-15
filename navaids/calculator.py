"""Great-circle distance, bearing and magnetic variation calculations."""

from __future__ import annotations

import math
from typing import Tuple


EARTH_RADIUS_NM = 3440.065  # nautical miles


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in nautical miles between two points.

    Parameters
    ----------
    lat1, lon1 : float
        Latitude and longitude of the first point in decimal degrees.
    lat2, lon2 : float
        Latitude and longitude of the second point in decimal degrees.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_NM * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the initial true bearing (degrees) from point 1 to point 2.

    Parameters
    ----------
    lat1, lon1 : float
        Latitude and longitude of the origin in decimal degrees.
    lat2, lon2 : float
        Latitude and longitude of the destination in decimal degrees.

    Returns
    -------
    float
        Bearing in degrees [0, 360).
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)

    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def magnetic_variation(latitude: float, longitude: float, year: float = 2025.0) -> float:
    """Return an approximate magnetic variation in degrees (positive = East).

    This uses a simplified dipole model and is suitable for rough estimates only.
    For precise values use the World Magnetic Model (WMM).

    Parameters
    ----------
    latitude, longitude : float
        Position in decimal degrees.
    year : float
        Decimal year (e.g. 2025.5 for mid-2025).
    """
    # Simplified model based on IGRF approximation
    # Geomagnetic pole (approximately 80.7°N, -72.7°W in 2025)
    pole_lat = math.radians(80.7)
    pole_lon = math.radians(-72.7)

    lat_r = math.radians(latitude)
    lon_r = math.radians(longitude)

    # Geocentric latitude of the geomagnetic north pole
    sin_psi = (
        math.sin(lat_r) * math.sin(pole_lat)
        + math.cos(lat_r) * math.cos(pole_lat) * math.cos(lon_r - pole_lon)
    )
    psi = math.acos(max(-1.0, min(1.0, sin_psi)))

    # Magnetic declination approximation
    sin_dec = math.cos(pole_lat) * math.sin(lon_r - pole_lon) / math.sin(psi) if math.sin(psi) > 1e-6 else 0.0
    sin_dec = max(-1.0, min(1.0, sin_dec))
    variation = -math.degrees(math.asin(sin_dec))  # positive East

    # Secular variation: roughly +0.05°/year drift (crude)
    variation += (year - 2025.0) * 0.05
    return round(variation, 1)


def destination_point(lat: float, lon: float, bearing: float, distance_nm: float) -> Tuple[float, float]:
    """Return the destination point given start point, bearing (degrees True), and distance (NM).

    Parameters
    ----------
    lat, lon : float
        Starting position in decimal degrees.
    bearing : float
        True bearing in degrees.
    distance_nm : float
        Distance in nautical miles.

    Returns
    -------
    tuple of (lat, lon) in decimal degrees.
    """
    angular_dist = distance_nm / EARTH_RADIUS_NM
    bearing_r = math.radians(bearing)
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)

    lat2 = math.asin(
        math.sin(lat_r) * math.cos(angular_dist)
        + math.cos(lat_r) * math.sin(angular_dist) * math.cos(bearing_r)
    )
    lon2 = lon_r + math.atan2(
        math.sin(bearing_r) * math.sin(angular_dist) * math.cos(lat_r),
        math.cos(angular_dist) - math.sin(lat_r) * math.sin(lat2),
    )
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180
