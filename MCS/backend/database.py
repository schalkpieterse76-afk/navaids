"""Database initialisation and SAAF base seeding for MCS."""

import os
from models import db, Base, CVORSystem

SAAF_BASES = [
    {"name": "AFB Waterkloof",      "icao": "FAWK", "latitude": -25.8300, "longitude": 28.2200},
    {"name": "AFB Hoedspruit",      "icao": "FAHS", "latitude": -24.3700, "longitude": 31.0500},
    {"name": "AFB Louis Trichardt", "icao": "FALT", "latitude": -23.1600, "longitude": 29.8600},
    {"name": "AFB Makhado",         "icao": "FALM", "latitude": -23.1600, "longitude": 29.9100},
    {"name": "AFB Overberg",        "icao": "FAOB", "latitude": -34.5500, "longitude": 20.5000},
    {"name": "AFB Langebaanweg",    "icao": "FALA", "latitude": -32.9700, "longitude": 18.1600},
    {"name": "AFB Bredasdorp",      "icao": "FABE", "latitude": -34.5900, "longitude": 20.0400},
    {"name": "AFB Ysterplaat",      "icao": "FAYP", "latitude": -33.9000, "longitude": 18.4980},
    {"name": "AFB Swartkop",        "icao": "FASK", "latitude": -25.8090, "longitude": 28.1640},
    {"name": "AFB Bloemspruit",     "icao": "FABL", "latitude": -29.0920, "longitude": 26.3020},
]


def init_db(app):
    """Create tables and seed SAAF bases if the database is empty."""
    with app.app_context():
        db.create_all()
        _seed_bases()


def _seed_bases():
    """Insert SAAF bases if they do not already exist."""
    if Base.query.count() > 0:
        return
    for data in SAAF_BASES:
        base = Base(
            name=data["name"],
            icao=data["icao"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            description=f"South African Air Force – {data['name']}",
        )
        db.session.add(base)
    db.session.commit()
