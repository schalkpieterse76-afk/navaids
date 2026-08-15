"""Tests for Navaid and NavaidType data structures."""

import json
import pytest
from navaids.navaid import Navaid, NavaidType


def make_vor() -> Navaid:
    return Navaid(
        ident="BCN",
        name="Barcelona VOR/DME",
        navaid_type=NavaidType.VORDME,
        latitude=41.2971,
        longitude=2.1024,
        elevation=21,
        frequency=114.1,
        magnetic_variation=-0.4,
        range_nm=200,
        country="Spain",
        icao_region="LE",
    )


def test_navaid_creation():
    n = make_vor()
    assert n.ident == "BCN"
    assert n.navaid_type == NavaidType.VORDME
    assert n.latitude == pytest.approx(41.2971)
    assert n.longitude == pytest.approx(2.1024)
    assert n.frequency == pytest.approx(114.1)


def test_navaid_type_enum():
    assert NavaidType("VOR") == NavaidType.VOR
    assert NavaidType("NDB") == NavaidType.NDB
    assert NavaidType("ILS") == NavaidType.ILS
    assert NavaidType("DME") == NavaidType.DME
    assert NavaidType("VOR/DME") == NavaidType.VORDME


def test_navaid_to_dict():
    n = make_vor()
    d = n.to_dict()
    assert d["ident"] == "BCN"
    assert d["navaid_type"] == "VOR/DME"
    assert d["latitude"] == pytest.approx(41.2971)


def test_navaid_round_trip_dict():
    n = make_vor()
    d = n.to_dict()
    n2 = Navaid.from_dict(d)
    assert n2.ident == n.ident
    assert n2.navaid_type == n.navaid_type
    assert n2.latitude == pytest.approx(n.latitude)
    assert n2.frequency == pytest.approx(n.frequency)


def test_navaid_round_trip_json():
    n = make_vor()
    s = n.to_json()
    n2 = Navaid.from_json(s)
    assert n2.ident == n.ident
    assert n2.navaid_type == n.navaid_type


def test_navaid_str():
    n = make_vor()
    s = str(n)
    assert "BCN" in s
    assert "VOR/DME" in s


def test_navaid_ils_fields():
    ils = Navaid(
        ident="ILIS",
        name="Test ILS",
        navaid_type=NavaidType.ILS,
        latitude=51.4,
        longitude=-0.46,
        frequency=110.9,
        runway="27L",
        ils_category="III",
        course=271.0,
        glide_slope=3.0,
    )
    assert ils.runway == "27L"
    assert ils.ils_category == "III"
    assert ils.course == pytest.approx(271.0)
    assert ils.glide_slope == pytest.approx(3.0)
    d = ils.to_dict()
    ils2 = Navaid.from_dict(d)
    assert ils2.runway == "27L"
    assert ils2.course == pytest.approx(271.0)
