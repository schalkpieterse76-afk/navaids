"""Navaid in-memory database with persistence and query capabilities."""

from __future__ import annotations

import json
import os
from typing import Iterable, Iterator, List, Optional

from .navaid import Navaid, NavaidType
from .calculator import haversine_distance


class NavaidDatabase:
    """An in-memory store of :class:`Navaid` objects with search and persistence."""

    def __init__(self) -> None:
        self._navaids: List[Navaid] = []

    # ------------------------------------------------------------------
    # Basic collection operations
    # ------------------------------------------------------------------

    def add(self, navaid: Navaid) -> None:
        """Add a navaid to the database."""
        if not isinstance(navaid, Navaid):
            raise TypeError(f"Expected Navaid, got {type(navaid).__name__}")
        self._navaids.append(navaid)

    def remove(self, ident: str) -> int:
        """Remove all navaids with the given identifier.

        Returns the number of records removed.
        """
        before = len(self._navaids)
        self._navaids = [n for n in self._navaids if n.ident.upper() != ident.upper()]
        return before - len(self._navaids)

    def clear(self) -> None:
        """Remove all navaids from the database."""
        self._navaids.clear()

    def __len__(self) -> int:
        return len(self._navaids)

    def __iter__(self) -> Iterator[Navaid]:
        return iter(self._navaids)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def find_by_ident(self, ident: str) -> List[Navaid]:
        """Return all navaids with the given identifier (case-insensitive)."""
        upper = ident.upper()
        return [n for n in self._navaids if n.ident.upper() == upper]

    def find_by_name(self, name: str) -> List[Navaid]:
        """Return navaids whose name contains *name* (case-insensitive substring)."""
        lower = name.lower()
        return [n for n in self._navaids if lower in n.name.lower()]

    def find_by_type(self, navaid_type: NavaidType) -> List[Navaid]:
        """Return all navaids of the given type."""
        return [n for n in self._navaids if n.navaid_type == navaid_type]

    def find_by_country(self, country: str) -> List[Navaid]:
        """Return all navaids in a given country (case-insensitive exact match)."""
        lower = country.lower()
        return [n for n in self._navaids if n.country.lower() == lower]

    def nearest(
        self,
        latitude: float,
        longitude: float,
        count: int = 10,
        navaid_type: Optional[NavaidType] = None,
        max_range_nm: Optional[float] = None,
    ) -> List[tuple]:
        """Return the *count* nearest navaids to the given position.

        Parameters
        ----------
        latitude, longitude : float
            Observer position in decimal degrees.
        count : int
            Maximum number of results to return.
        navaid_type : NavaidType, optional
            Filter results to a specific navaid type.
        max_range_nm : float, optional
            Only include navaids within this range (NM).

        Returns
        -------
        list of (distance_nm, Navaid) tuples sorted by ascending distance.
        """
        candidates = self._navaids
        if navaid_type is not None:
            candidates = [n for n in candidates if n.navaid_type == navaid_type]

        distances = [
            (haversine_distance(latitude, longitude, n.latitude, n.longitude), n)
            for n in candidates
        ]
        distances.sort(key=lambda t: t[0])

        if max_range_nm is not None:
            distances = [(d, n) for d, n in distances if d <= max_range_nm]

        return distances[:count]

    def within_range(
        self,
        latitude: float,
        longitude: float,
        range_nm: float,
        navaid_type: Optional[NavaidType] = None,
    ) -> List[tuple]:
        """Return all navaids within *range_nm* nautical miles of the given position."""
        return self.nearest(latitude, longitude, count=len(self._navaids),
                            navaid_type=navaid_type, max_range_nm=range_nm)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {"navaids": [n.to_dict() for n in self._navaids]}

    def save(self, path: str) -> None:
        """Persist the database to a JSON file."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "NavaidDatabase":
        """Load a database from a JSON file created by :meth:`save`."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        db = cls()
        for record in data.get("navaids", []):
            db.add(Navaid.from_dict(record))
        return db

    @classmethod
    def from_dict(cls, data: dict) -> "NavaidDatabase":
        db = cls()
        for record in data.get("navaids", []):
            db.add(Navaid.from_dict(record))
        return db

    @classmethod
    def load_sample(cls) -> "NavaidDatabase":
        """Return a database pre-populated with a representative set of world navaids."""
        db = cls()
        for navaid in _SAMPLE_NAVAIDS:
            db.add(navaid)
        return db


# ---------------------------------------------------------------------------
# Sample data – a representative set of real-world navaids
# ---------------------------------------------------------------------------

_SAMPLE_NAVAIDS: List[Navaid] = [
    # ---------- VORs ----------
    Navaid("BCN", "Barcelona VOR/DME", NavaidType.VORDME,
           41.2971, 2.1024, 21, 114.1, -0.4, 200, "Spain", "LE"),
    Navaid("CPT", "Cape Town VOR/DME", NavaidType.VORDME,
           -33.9648, 18.5954, 151, 114.7, -26.0, 200, "South Africa", "FA"),
    Navaid("JHB", "Johannesburg VOR", NavaidType.VOR,
           -26.1392, 28.2460, 5558, 112.9, -20.0, 130, "South Africa", "FA"),
    Navaid("ORL", "Orlando VOR", NavaidType.VOR,
           28.5453, -81.3329, 105, 112.2, -5.5, 130, "United States", "K"),
    Navaid("DFW", "Dallas/Ft Worth VORTAC", NavaidType.VORTAC,
           32.8998, -97.0403, 603, 117.0, 3.0, 200, "United States", "K"),
    Navaid("LAX", "Los Angeles VOR/DME", NavaidType.VORDME,
           33.9425, -118.4081, 125, 113.6, 12.0, 200, "United States", "K"),
    Navaid("LHR", "London Heathrow VOR/DME", NavaidType.VORDME,
           51.4775, -0.4614, 83, 113.6, -1.0, 200, "United Kingdom", "EG"),
    Navaid("CDG", "Paris CDG VOR/DME", NavaidType.VORDME,
           49.0097, 2.5479, 392, 115.1, -0.5, 200, "France", "LF"),
    Navaid("FRA", "Frankfurt VOR/DME", NavaidType.VORDME,
           50.0333, 8.5706, 364, 114.2, 1.5, 200, "Germany", "ED"),
    Navaid("SYD", "Sydney VOR/DME", NavaidType.VORDME,
           -33.9461, 151.1772, 21, 115.4, 12.5, 200, "Australia", "YS"),
    Navaid("NRT", "Narita VOR/DME", NavaidType.VORDME,
           35.7647, 140.3863, 141, 116.8, -6.5, 200, "Japan", "RJ"),
    Navaid("DXB", "Dubai VOR/DME", NavaidType.VORDME,
           25.2528, 55.3644, 62, 114.5, 2.0, 200, "United Arab Emirates", "OM"),
    Navaid("GRV", "Graaff-Reinet NDB", NavaidType.NDB,
           -32.2353, 24.5401, 2600, 350.0, -24.0, 75, "South Africa", "FA"),
    Navaid("ELS", "East London VOR/DME", NavaidType.VORDME,
           -33.0356, 27.8259, 436, 113.2, -25.0, 130, "South Africa", "FA"),
    Navaid("PLZ", "Port Elizabeth VOR/DME", NavaidType.VORDME,
           -33.9849, 25.6173, 226, 114.7, -25.5, 130, "South Africa", "FA"),
    Navaid("BFN", "Bloemfontein VOR/DME", NavaidType.VORDME,
           -29.1027, 26.3024, 4462, 112.3, -22.0, 130, "South Africa", "FA"),
    Navaid("GRJ", "George VOR/DME", NavaidType.VORDME,
           -34.0056, 22.3789, 648, 115.9, -26.0, 130, "South Africa", "FA"),
    Navaid("KIM", "Kimberley VOR/DME", NavaidType.VORDME,
           -28.8028, 24.7651, 3950, 116.5, -21.5, 130, "South Africa", "FA"),
    Navaid("DURB", "Durban VOR/DME", NavaidType.VORDME,
           -29.9701, 30.9503, 30, 113.6, -23.0, 130, "South Africa", "FA"),
    # ---------- NDBs ----------
    Navaid("MOS", "Moscow Sheremetyevo NDB", NavaidType.NDB,
           55.9736, 37.4125, 630, 591.0, 10.0, 150, "Russia", "UU"),
    Navaid("ORD", "Chicago O'Hare NDB", NavaidType.NDB,
           41.9742, -87.9073, 672, 388.0, -3.0, 75, "United States", "K"),
    Navaid("JFK", "New York Kennedy NDB", NavaidType.NDB,
           40.6413, -73.7781, 13, 260.0, -13.0, 75, "United States", "K"),
    # ---------- ILS ----------
    Navaid("ILHH", "FAJS ILS RWY 03L", NavaidType.ILS,
           -26.1353, 28.2363, 5558, 109.5, -20.0, 18, "South Africa", "FA",
           runway="03L", ils_category="III", course=28.0, glide_slope=3.0),
    Navaid("ILRR", "FAJS ILS RWY 21R", NavaidType.ILS,
           -26.1392, 28.2460, 5558, 110.3, -20.0, 18, "South Africa", "FA",
           runway="21R", ils_category="I", course=208.0, glide_slope=3.0),
    Navaid("ILIS", "EGLL ILS RWY 27L", NavaidType.ILS,
           51.4775, -0.4614, 83, 110.9, -1.0, 18, "United Kingdom", "EG",
           runway="27L", ils_category="III", course=271.0, glide_slope=3.0),
    # ---------- DMEs ----------
    Navaid("DLAB", "Johannesburg Airport DME", NavaidType.DME,
           -26.1317, 28.2256, 5558, 112.9, -20.0, 40, "South Africa", "FA"),
    # ---------- TACAN ----------
    Navaid("TAC1", "Waterkloof TACAN", NavaidType.TACAN,
           -25.8288, 28.2222, 4840, 103.0, -20.0, 195, "South Africa", "FA"),
]
