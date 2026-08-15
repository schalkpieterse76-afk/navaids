"""Navaid data structures."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class NavaidType(str, Enum):
    """Types of navigational aids."""

    VOR = "VOR"          # VHF Omni-directional Range
    NDB = "NDB"          # Non-Directional Beacon
    ILS = "ILS"          # Instrument Landing System
    DME = "DME"          # Distance Measuring Equipment
    VORDME = "VOR/DME"   # Combined VOR and DME
    VORTAC = "VORTAC"    # Combined VOR and TACAN
    TACAN = "TACAN"      # Tactical Air Navigation
    LOC = "LOC"          # Localizer (ILS component)
    GP = "GP"            # Glide Path (ILS component)
    MARKER = "MARKER"    # Marker Beacon (OM/MM/IM)
    GPS = "GPS"          # GPS Waypoint


@dataclass
class Navaid:
    """Represents a single navigational aid."""

    ident: str
    name: str
    navaid_type: NavaidType
    latitude: float
    longitude: float
    elevation: float = 0.0          # feet above MSL
    frequency: Optional[float] = None  # MHz for VOR/ILS/LOC; kHz for NDB
    magnetic_variation: float = 0.0    # degrees East (+) / West (-)
    range_nm: Optional[float] = None   # service volume radius in NM
    country: str = ""
    icao_region: str = ""
    dme_bias: float = 0.0              # DME antenna offset (NM)
    remarks: str = ""

    # ILS-specific fields
    runway: str = ""                   # e.g. "27L"
    ils_category: str = ""             # I / II / III
    course: Optional[float] = None    # localizer course (degrees True)
    glide_slope: Optional[float] = None  # glide slope angle (degrees)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["navaid_type"] = self.navaid_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Navaid":
        d = dict(d)
        d["navaid_type"] = NavaidType(d["navaid_type"])
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, s: str) -> "Navaid":
        return cls.from_dict(json.loads(s))

    def __str__(self) -> str:
        freq_str = ""
        if self.frequency is not None:
            unit = "kHz" if self.navaid_type == NavaidType.NDB else "MHz"
            freq_str = f"  {self.frequency} {unit}"
        return (
            f"{self.ident:6s} {self.navaid_type.value:8s} {self.name:<30s}"
            f"  {self.latitude:+09.4f}  {self.longitude:+010.4f}"
            f"{freq_str}"
        )
