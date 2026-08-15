# navaids

A complete Python program for managing and querying aviation **navigational aids (navaids)** — VOR, NDB, ILS, DME, VORTAC, TACAN and more.

## Features

- **Navaid data model** — typed dataclass for every navaid category with all standard fields (frequency, magnetic variation, service volume, ILS course/glide-slope, etc.)
- **In-memory database** — add, remove and query navaids by ident, name, type or country
- **Geospatial queries** — find the *N* nearest navaids to any position, or all navaids within a given range
- **Great-circle calculations** — haversine distance, initial bearing, and destination-point computation (all in nautical miles)
- **Magnetic variation** — simplified dipole model for quick estimates
- **JSON persistence** — save/load a navaid database to/from a JSON file
- **Built-in sample data** — representative world-wide navaids pre-loaded for immediate use
- **CLI tool** — `navaids` command with sub-commands for listing, searching, nearest lookup and calculations

## Installation

```bash
pip install .
```

## CLI Usage

```bash
# List all sample navaids
navaids list

# List only VOR/DMEs
navaids list --type VOR/DME

# Search by ident or partial name
navaids search BCN
navaids search "Cape Town"

# Find 5 nearest navaids to Johannesburg
navaids nearest -26.14 28.25 --count 5

# Find navaids within 200 NM of London, VOR only
navaids nearest 51.48 -0.46 --range 200 --type VOR

# Distance and bearing between two points
navaids distance 51.48 -0.46 48.85 2.35

# Destination given start, bearing, distance
navaids destination -26.14 28.25 225 150

# Magnetic variation
navaids magvar -26.14 28.25

# Use a custom database file
navaids list --db my_navaids.json
navaids nearest 0 0 --db my_navaids.json
```

## Python API

```python
from navaids import Navaid, NavaidType, NavaidDatabase
from navaids import haversine_distance, calculate_bearing

# Create navaids
vor = Navaid(
    ident="BCN",
    name="Barcelona VOR/DME",
    navaid_type=NavaidType.VORDME,
    latitude=41.2971,
    longitude=2.1024,
    frequency=114.1,
    country="Spain",
)

# Build a database
db = NavaidDatabase()
db.add(vor)

# Or load the built-in sample data
db = NavaidDatabase.load_sample()

# Query
results = db.find_by_ident("BCN")
vors = db.find_by_type(NavaidType.VOR)
nearby = db.nearest(-26.14, 28.25, count=10)
in_range = db.within_range(-26.14, 28.25, range_nm=200)

# Save / load
db.save("my_navaids.json")
db2 = NavaidDatabase.load("my_navaids.json")

# Calculations
dist_nm = haversine_distance(51.48, -0.46, 48.85, 2.35)
bearing  = calculate_bearing(51.48, -0.46, 48.85, 2.35)
```

## Navaid Types

| Type | Description |
|------|-------------|
| VOR | VHF Omni-directional Range |
| NDB | Non-Directional Beacon |
| ILS | Instrument Landing System |
| DME | Distance Measuring Equipment |
| VOR/DME | Combined VOR and DME |
| VORTAC | Combined VOR and TACAN |
| TACAN | Tactical Air Navigation |
| LOC | Localizer (ILS component) |
| GP | Glide Path (ILS component) |
| MARKER | Marker Beacon |
| GPS | GPS Waypoint |

## Running Tests

```bash
pip install pytest
pytest tests/
```
