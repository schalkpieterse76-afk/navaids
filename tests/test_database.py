"""Tests for NavaidDatabase."""

import json
import os
import tempfile

import pytest

from navaids.navaid import Navaid, NavaidType
from navaids.database import NavaidDatabase


def make_db() -> NavaidDatabase:
    db = NavaidDatabase()
    db.add(Navaid("BCN", "Barcelona VOR/DME", NavaidType.VORDME, 41.30, 2.10, frequency=114.1, country="Spain"))
    db.add(Navaid("LHR", "London Heathrow VOR", NavaidType.VOR, 51.48, -0.46, frequency=113.6, country="UK"))
    db.add(Navaid("ORD", "Chicago NDB", NavaidType.NDB, 41.97, -87.91, frequency=388.0, country="USA"))
    db.add(Navaid("JNB", "Johannesburg VOR", NavaidType.VOR, -26.14, 28.25, frequency=112.9, country="South Africa"))
    return db


def test_add_and_len():
    db = make_db()
    assert len(db) == 4


def test_add_wrong_type():
    db = NavaidDatabase()
    with pytest.raises(TypeError):
        db.add("not a navaid")


def test_remove():
    db = make_db()
    removed = db.remove("BCN")
    assert removed == 1
    assert len(db) == 3
    assert db.find_by_ident("BCN") == []


def test_remove_missing():
    db = make_db()
    assert db.remove("XXXX") == 0


def test_clear():
    db = make_db()
    db.clear()
    assert len(db) == 0


def test_find_by_ident():
    db = make_db()
    results = db.find_by_ident("BCN")
    assert len(results) == 1
    assert results[0].ident == "BCN"


def test_find_by_ident_case_insensitive():
    db = make_db()
    assert db.find_by_ident("bcn") == db.find_by_ident("BCN")


def test_find_by_name():
    db = make_db()
    results = db.find_by_name("Heathrow")
    assert len(results) == 1
    assert results[0].ident == "LHR"


def test_find_by_type():
    db = make_db()
    vors = db.find_by_type(NavaidType.VOR)
    assert len(vors) == 2
    assert all(n.navaid_type == NavaidType.VOR for n in vors)


def test_find_by_country():
    db = make_db()
    results = db.find_by_country("Spain")
    assert len(results) == 1
    assert results[0].ident == "BCN"


def test_nearest():
    db = make_db()
    # From London, LHR should be nearest
    results = db.nearest(51.5, -0.5, count=2)
    assert len(results) == 2
    assert results[0][1].ident == "LHR"
    # Distance should be small
    assert results[0][0] < 5


def test_nearest_with_type_filter():
    db = make_db()
    results = db.nearest(41.9, -87.9, count=5, navaid_type=NavaidType.NDB)
    assert all(r[1].navaid_type == NavaidType.NDB for r in results)


def test_nearest_with_range():
    db = make_db()
    results = db.nearest(51.5, -0.5, count=10, max_range_nm=100)
    assert all(r[0] <= 100 for r in results)


def test_within_range():
    db = make_db()
    results = db.within_range(51.5, -0.5, range_nm=200)
    assert all(r[0] <= 200 for r in results)


def test_iter():
    db = make_db()
    idents = {n.ident for n in db}
    assert "BCN" in idents
    assert "LHR" in idents


def test_save_and_load():
    db = make_db()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        db.save(path)
        db2 = NavaidDatabase.load(path)
        assert len(db2) == len(db)
        assert {n.ident for n in db2} == {n.ident for n in db}
    finally:
        os.unlink(path)


def test_round_trip_dict():
    db = make_db()
    d = db.to_dict()
    db2 = NavaidDatabase.from_dict(d)
    assert len(db2) == len(db)


def test_load_sample():
    db = NavaidDatabase.load_sample()
    assert len(db) > 0
    types = {n.navaid_type for n in db}
    assert NavaidType.VOR in types or NavaidType.VORDME in types
