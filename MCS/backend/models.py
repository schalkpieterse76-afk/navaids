"""SQLAlchemy database models for MCS CVOR Remote Management System."""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Base(db.Model):
    """Represents an SAAF air force base."""
    __tablename__ = "bases"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    icao = db.Column(db.String(4), unique=True, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cvor_systems = db.relationship("CVORSystem", back_populates="base", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "icao": self.icao,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "cvor_count": len(self.cvor_systems),
        }


class CVORSystem(db.Model):
    """Represents a CVOR navigation system at a base."""
    __tablename__ = "cvor_systems"

    id = db.Column(db.Integer, primary_key=True)
    base_id = db.Column(db.Integer, db.ForeignKey("bases.id"), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    subnet_mask = db.Column(db.String(45), default="255.255.255.0")
    gateway = db.Column(db.String(45), default="")
    tcp_port = db.Column(db.Integer, default=4000)
    frequency = db.Column(db.Float, default=0.0)
    power_level = db.Column(db.String(16), default="HIGH")
    mode = db.Column(db.String(16), default="NORMAL")
    ident = db.Column(db.String(8), default="")
    status = db.Column(db.String(16), default="UNKNOWN")
    last_polled = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    base = db.relationship("Base", back_populates="cvor_systems")
    alarms = db.relationship("Alarm", back_populates="cvor_system", cascade="all, delete-orphan")
    shelter_slots = db.relationship("ShelterSlot", back_populates="cvor_system", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "base_id": self.base_id,
            "name": self.name,
            "ip_address": self.ip_address,
            "subnet_mask": self.subnet_mask,
            "gateway": self.gateway,
            "tcp_port": self.tcp_port,
            "frequency": self.frequency,
            "power_level": self.power_level,
            "mode": self.mode,
            "ident": self.ident,
            "status": self.status,
            "last_polled": self.last_polled.isoformat() if self.last_polled else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Alarm(db.Model):
    """Represents an alarm raised by a CVOR system."""
    __tablename__ = "alarms"

    id = db.Column(db.Integer, primary_key=True)
    cvor_system_id = db.Column(db.Integer, db.ForeignKey("cvor_systems.id"), nullable=False)
    code = db.Column(db.String(32), nullable=False)
    severity = db.Column(db.String(16), default="WARNING")  # INFO, WARNING, CRITICAL
    message = db.Column(db.Text, default="")
    acknowledged = db.Column(db.Boolean, default=False)
    raised_at = db.Column(db.DateTime, default=datetime.utcnow)
    acknowledged_at = db.Column(db.DateTime, nullable=True)

    cvor_system = db.relationship("CVORSystem", back_populates="alarms")

    def to_dict(self):
        return {
            "id": self.id,
            "cvor_system_id": self.cvor_system_id,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "acknowledged": self.acknowledged,
            "raised_at": self.raised_at.isoformat() if self.raised_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }


class ShelterSlot(db.Model):
    """Represents an equipment slot in a CVOR shelter."""
    __tablename__ = "shelter_slots"

    id = db.Column(db.Integer, primary_key=True)
    cvor_system_id = db.Column(db.Integer, db.ForeignKey("cvor_systems.id"), nullable=False)
    slot_number = db.Column(db.Integer, nullable=False)
    equipment_type = db.Column(db.String(64), default="")
    serial_number = db.Column(db.String(64), default="")
    description = db.Column(db.Text, default="")
    installed_at = db.Column(db.DateTime, nullable=True)

    cvor_system = db.relationship("CVORSystem", back_populates="shelter_slots")

    def to_dict(self):
        return {
            "id": self.id,
            "cvor_system_id": self.cvor_system_id,
            "slot_number": self.slot_number,
            "equipment_type": self.equipment_type,
            "serial_number": self.serial_number,
            "description": self.description,
            "installed_at": self.installed_at.isoformat() if self.installed_at else None,
        }
