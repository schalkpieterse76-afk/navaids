"""Command-line interface for the navaids program."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .navaid import NavaidType
from .database import NavaidDatabase
from .calculator import haversine_distance, calculate_bearing, destination_point, magnetic_variation


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="navaids",
        description="Navigational Aids (Navaids) management and query tool.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- list ----
    list_p = subparsers.add_parser("list", help="List navaids in the database.")
    list_p.add_argument("--db", default=None, help="Path to JSON database file.")
    list_p.add_argument("--type", dest="navaid_type", default=None,
                        help="Filter by type (VOR, NDB, ILS, DME, …).")
    list_p.add_argument("--country", default=None, help="Filter by country.")

    # ---- search ----
    search_p = subparsers.add_parser("search", help="Search navaids by ident or name.")
    search_p.add_argument("query", help="Identifier or partial name to search for.")
    search_p.add_argument("--db", default=None, help="Path to JSON database file.")
    search_p.add_argument("--type", dest="navaid_type", default=None,
                          help="Filter by type.")

    # ---- nearest ----
    near_p = subparsers.add_parser("nearest", help="Find navaids nearest to a position.")
    near_p.add_argument("lat", type=float, help="Latitude (decimal degrees, +N/-S).")
    near_p.add_argument("lon", type=float, help="Longitude (decimal degrees, +E/-W).")
    near_p.add_argument("--count", type=int, default=10, help="Number of results (default 10).")
    near_p.add_argument("--range", dest="max_range", type=float, default=None,
                        help="Maximum range in NM.")
    near_p.add_argument("--type", dest="navaid_type", default=None, help="Filter by type.")
    near_p.add_argument("--db", default=None, help="Path to JSON database file.")

    # ---- distance ----
    dist_p = subparsers.add_parser("distance", help="Calculate distance and bearing between two points.")
    dist_p.add_argument("lat1", type=float, help="Origin latitude.")
    dist_p.add_argument("lon1", type=float, help="Origin longitude.")
    dist_p.add_argument("lat2", type=float, help="Destination latitude.")
    dist_p.add_argument("lon2", type=float, help="Destination longitude.")

    # ---- destination ----
    dest_p = subparsers.add_parser("destination",
                                   help="Calculate destination given start, bearing, and distance.")
    dest_p.add_argument("lat", type=float, help="Start latitude.")
    dest_p.add_argument("lon", type=float, help="Start longitude.")
    dest_p.add_argument("bearing", type=float, help="True bearing (degrees).")
    dest_p.add_argument("distance", type=float, help="Distance in nautical miles.")

    # ---- magvar ----
    magvar_p = subparsers.add_parser("magvar", help="Estimate magnetic variation at a position.")
    magvar_p.add_argument("lat", type=float, help="Latitude.")
    magvar_p.add_argument("lon", type=float, help="Longitude.")
    magvar_p.add_argument("--year", type=float, default=2025.0, help="Decimal year (default 2025.0).")

    return parser


def _load_db(path: Optional[str]) -> NavaidDatabase:
    if path:
        return NavaidDatabase.load(path)
    return NavaidDatabase.load_sample()


def _navaid_type_arg(value: Optional[str]) -> Optional[NavaidType]:
    if value is None:
        return None
    normalized = value.upper()
    # Accept "VORDME" as an alias for "VOR/DME"
    if normalized == "VORDME":
        normalized = "VOR/DME"
    try:
        return NavaidType(normalized)
    except ValueError:
        raise ValueError(
            f"Unknown navaid type '{value}'. Valid types: {', '.join(t.value for t in NavaidType)}"
        )


def cmd_list(args: argparse.Namespace) -> None:
    db = _load_db(args.db)
    ntype = _navaid_type_arg(args.navaid_type)

    results = list(db)
    if ntype:
        results = [n for n in results if n.navaid_type == ntype]
    if args.country:
        results = [n for n in results if n.country.lower() == args.country.lower()]

    if not results:
        print("No navaids found.")
        return
    print(f"{'Ident':<6}  {'Type':<8}  {'Name':<30}  {'Lat':>9}  {'Lon':>10}  {'Freq':>10}")
    print("-" * 82)
    for n in results:
        freq = f"{n.frequency}" if n.frequency is not None else ""
        print(f"{n.ident:<6}  {n.navaid_type.value:<8}  {n.name:<30}  "
              f"{n.latitude:+9.4f}  {n.longitude:+10.4f}  {freq:>10}")


def cmd_search(args: argparse.Namespace) -> None:
    db = _load_db(args.db)
    ntype = _navaid_type_arg(args.navaid_type)
    query = args.query.upper()

    by_ident = db.find_by_ident(query)
    by_name = db.find_by_name(args.query)

    seen = set()
    results = []
    for n in by_ident + by_name:
        key = id(n)
        if key not in seen:
            seen.add(key)
            results.append(n)

    if ntype:
        results = [n for n in results if n.navaid_type == ntype]

    if not results:
        print(f"No navaids found matching '{args.query}'.")
        return
    print(f"{'Ident':<6}  {'Type':<8}  {'Name':<30}  {'Lat':>9}  {'Lon':>10}")
    print("-" * 68)
    for n in results:
        print(f"{n.ident:<6}  {n.navaid_type.value:<8}  {n.name:<30}  "
              f"{n.latitude:+9.4f}  {n.longitude:+10.4f}")


def cmd_nearest(args: argparse.Namespace) -> None:
    db = _load_db(args.db)
    ntype = _navaid_type_arg(args.navaid_type)
    results = db.nearest(args.lat, args.lon, count=args.count,
                         navaid_type=ntype, max_range_nm=args.max_range)
    if not results:
        print("No navaids found.")
        return
    print(f"Nearest navaids to {args.lat:+.4f}, {args.lon:+.4f}:\n")
    print(f"{'Dist(NM)':>9}  {'Brg':>5}  {'Ident':<6}  {'Type':<8}  {'Name':<30}")
    print("-" * 72)
    for dist, n in results:
        brg = calculate_bearing(args.lat, args.lon, n.latitude, n.longitude)
        print(f"{dist:9.1f}  {brg:5.1f}  {n.ident:<6}  {n.navaid_type.value:<8}  {n.name:<30}")


def cmd_distance(args: argparse.Namespace) -> None:
    dist = haversine_distance(args.lat1, args.lon1, args.lat2, args.lon2)
    brg = calculate_bearing(args.lat1, args.lon1, args.lat2, args.lon2)
    rbrg = calculate_bearing(args.lat2, args.lon2, args.lat1, args.lon1)
    print(f"Distance : {dist:.2f} NM  ({dist * 1.852:.2f} km)")
    print(f"Bearing  : {brg:.1f}° True  (reciprocal {rbrg:.1f}°)")


def cmd_destination(args: argparse.Namespace) -> None:
    lat2, lon2 = destination_point(args.lat, args.lon, args.bearing, args.distance)
    print(f"Destination: {lat2:+.6f}, {lon2:+.6f}")
    print(f"  Latitude : {lat2:+.6f}°  ({_dd_to_dms(lat2, 'NS')})")
    print(f"  Longitude: {lon2:+.6f}°  ({_dd_to_dms(lon2, 'EW')})")


def cmd_magvar(args: argparse.Namespace) -> None:
    var = magnetic_variation(args.lat, args.lon, args.year)
    direction = "East" if var >= 0 else "West"
    print(f"Magnetic variation at ({args.lat:+.4f}, {args.lon:+.4f}): "
          f"{abs(var):.1f}° {direction}  (year {args.year:.1f})")


def _dd_to_dms(dd: float, pos_neg: str) -> str:
    """Convert decimal degrees to DMS string."""
    hemisphere = pos_neg[0] if dd >= 0 else pos_neg[1]
    dd = abs(dd)
    degrees = int(dd)
    minutes = int((dd - degrees) * 60)
    seconds = (dd - degrees - minutes / 60) * 3600
    return f"{degrees:03d}°{minutes:02d}'{seconds:05.2f}\"{hemisphere}"


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "list": cmd_list,
        "search": cmd_search,
        "nearest": cmd_nearest,
        "distance": cmd_distance,
        "destination": cmd_destination,
        "magvar": cmd_magvar,
    }
    try:
        dispatch[args.command](args)
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
