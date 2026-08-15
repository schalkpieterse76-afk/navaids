"""Navaids - Navigational Aids management and calculation library."""

from .navaid import Navaid, NavaidType
from .database import NavaidDatabase
from .calculator import haversine_distance, calculate_bearing, magnetic_variation

__all__ = [
    "Navaid",
    "NavaidType",
    "NavaidDatabase",
    "haversine_distance",
    "calculate_bearing",
    "magnetic_variation",
]
