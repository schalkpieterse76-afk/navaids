"""Tests for the haversine distance and bearing calculations."""

import math
import pytest
from navaids.calculator import (
    haversine_distance,
    calculate_bearing,
    magnetic_variation,
    destination_point,
    EARTH_RADIUS_NM,
)


def test_distance_same_point():
    assert haversine_distance(0, 0, 0, 0) == pytest.approx(0.0)


def test_distance_equator_one_degree():
    # 1° of longitude at equator ≈ 60 NM
    d = haversine_distance(0, 0, 0, 1)
    assert d == pytest.approx(60.0, abs=0.5)


def test_distance_known():
    # Johannesburg to Cape Town ≈ 686 NM
    d = haversine_distance(-26.14, 28.25, -33.96, 18.60)
    assert d == pytest.approx(686, abs=15)


def test_bearing_north():
    b = calculate_bearing(0, 0, 1, 0)
    assert b == pytest.approx(0.0, abs=0.1)


def test_bearing_east():
    b = calculate_bearing(0, 0, 0, 1)
    assert b == pytest.approx(90.0, abs=0.1)


def test_bearing_south():
    b = calculate_bearing(1, 0, 0, 0)
    assert b == pytest.approx(180.0, abs=0.1)


def test_bearing_west():
    b = calculate_bearing(0, 1, 0, 0)
    assert b == pytest.approx(270.0, abs=0.1)


def test_bearing_range():
    for lat1, lon1, lat2, lon2 in [
        (51.5, -0.1, 48.8, 2.3),
        (-33.9, 18.6, -26.1, 28.2),
        (35.7, 139.8, 1.4, 103.8),
    ]:
        b = calculate_bearing(lat1, lon1, lat2, lon2)
        assert 0 <= b < 360


def test_destination_point_north():
    # Travel 60 NM due north from equator ≈ 1 degree north
    lat2, lon2 = destination_point(0, 0, 0, 60)
    assert lat2 == pytest.approx(1.0, abs=0.05)
    assert lon2 == pytest.approx(0.0, abs=0.01)


def test_destination_round_trip():
    lat, lon = -26.14, 28.25
    bearing = 45.0
    dist = 100.0
    lat2, lon2 = destination_point(lat, lon, bearing, dist)
    # Distance back should be the same
    d = haversine_distance(lat, lon, lat2, lon2)
    assert d == pytest.approx(dist, abs=0.1)


def test_magnetic_variation_returns_float():
    var = magnetic_variation(-26.14, 28.25)
    assert isinstance(var, float)


def test_magnetic_variation_southern_africa_approximate():
    # Southern Africa has westerly magnetic variation (~-20° to -26°)
    var = magnetic_variation(-26.14, 28.25)
    assert var < 0  # westerly
