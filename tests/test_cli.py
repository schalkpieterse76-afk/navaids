"""Tests for the CLI interface."""

import json
import os
import tempfile

import pytest

from navaids.cli import main
from navaids.navaid import Navaid, NavaidType
from navaids.database import NavaidDatabase


def _make_db_file() -> str:
    """Write a small test database to a temp file and return the path."""
    db = NavaidDatabase()
    db.add(Navaid("BCN", "Barcelona VOR/DME", NavaidType.VORDME, 41.30, 2.10, frequency=114.1, country="Spain"))
    db.add(Navaid("LHR", "London Heathrow VOR", NavaidType.VOR, 51.48, -0.46, frequency=113.6, country="UK"))
    db.add(Navaid("ORD", "Chicago NDB", NavaidType.NDB, 41.97, -87.91, frequency=388.0, country="USA"))
    f = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    db.save(f.name)
    f.close()
    return f.name


@pytest.fixture(scope="module")
def db_path():
    path = _make_db_file()
    yield path
    os.unlink(path)


def test_list_command(capsys, db_path):
    rc = main(["list", "--db", db_path])
    assert rc == 0
    out = capsys.readouterr().out
    assert "BCN" in out
    assert "LHR" in out


def test_list_filter_type(capsys, db_path):
    rc = main(["list", "--db", db_path, "--type", "NDB"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ORD" in out
    assert "BCN" not in out


def test_list_filter_country(capsys, db_path):
    rc = main(["list", "--db", db_path, "--country", "Spain"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "BCN" in out
    assert "LHR" not in out


def test_search_by_ident(capsys, db_path):
    rc = main(["search", "BCN", "--db", db_path])
    assert rc == 0
    out = capsys.readouterr().out
    assert "BCN" in out


def test_search_by_name(capsys, db_path):
    rc = main(["search", "Heathrow", "--db", db_path])
    assert rc == 0
    out = capsys.readouterr().out
    assert "LHR" in out


def test_search_no_results(capsys, db_path):
    rc = main(["search", "ZZZZZ", "--db", db_path])
    assert rc == 0
    out = capsys.readouterr().out
    assert "No navaids" in out


def test_nearest_command(capsys, db_path):
    rc = main(["nearest", "51.5", "-0.5", "--db", db_path, "--count", "3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "LHR" in out


def test_nearest_with_range(capsys, db_path):
    rc = main(["nearest", "51.5", "-0.5", "--db", db_path, "--range", "100"])
    assert rc == 0


def test_distance_command(capsys):
    rc = main(["distance", "51.5", "-0.1", "48.8", "2.3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "NM" in out
    assert "Bearing" in out


def test_destination_command(capsys):
    rc = main(["destination", "0", "0", "90", "60"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Destination" in out


def test_magvar_command(capsys):
    rc = main(["magvar", "-26.14", "28.25"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "variation" in out.lower()


def test_invalid_db_path(capsys):
    rc = main(["list", "--db", "/nonexistent/path.json"])
    assert rc == 1


def test_invalid_navaid_type(capsys, db_path):
    rc = main(["list", "--db", db_path, "--type", "UNKNOWN"])
    assert rc == 1
