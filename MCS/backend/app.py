"""Flask REST API for MCS CVOR Remote Management System.

Run with:
    python app.py

Or set environment variables:
    MCS_HOST   (default: 0.0.0.0)
    MCS_PORT   (default: 5000)
    MCS_DB_PATH (default: ../database/mcs.db)
    MCS_DEBUG  (default: false)
"""

import os
import sys
import io
import zipfile
import json
import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_file, abort
from flask_cors import CORS

# Allow running from the backend/ directory directly
sys.path.insert(0, os.path.dirname(__file__))

from models import db, Base, CVORSystem, Alarm, ShelterSlot
from database import init_db
import tcp_client
import network_detect
import file_import

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5000", "http://localhost:5000", "null"])

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.environ.get(
    "MCS_DB_PATH",
    os.path.join(_BASE_DIR, "..", "database", "mcs.db"),
)
os.makedirs(os.path.dirname(os.path.abspath(_DB_PATH)), exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.abspath(_DB_PATH)}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
init_db(app)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _json_or_400(required: list = None):
    """Return request JSON or abort with 400."""
    data = request.get_json(silent=True) or {}
    if required:
        missing = [k for k in required if k not in data]
        if missing:
            abort(400, description=f"Missing fields: {', '.join(missing)}")
    return data


# ---------------------------------------------------------------------------
# Base endpoints
# ---------------------------------------------------------------------------

@app.route("/api/bases", methods=["GET"])
def list_bases():
    bases = Base.query.order_by(Base.name).all()
    return jsonify([b.to_dict() for b in bases])


@app.route("/api/bases/<int:base_id>", methods=["GET"])
def get_base(base_id):
    base = Base.query.get_or_404(base_id)
    return jsonify(base.to_dict())


@app.route("/api/bases", methods=["POST"])
def create_base():
    data = _json_or_400(["name", "icao", "latitude", "longitude"])
    base = Base(
        name=data["name"],
        icao=data["icao"].upper(),
        latitude=float(data["latitude"]),
        longitude=float(data["longitude"]),
        description=data.get("description", ""),
    )
    db.session.add(base)
    db.session.commit()
    return jsonify(base.to_dict()), 201


@app.route("/api/bases/<int:base_id>", methods=["PUT"])
def update_base(base_id):
    base = Base.query.get_or_404(base_id)
    data = _json_or_400()
    for field in ("name", "icao", "latitude", "longitude", "description"):
        if field in data:
            value = data[field]
            if field == "icao":
                value = value.upper()
            if field in ("latitude", "longitude"):
                value = float(value)
            setattr(base, field, value)
    base.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(base.to_dict())


@app.route("/api/bases/<int:base_id>", methods=["DELETE"])
def delete_base(base_id):
    base = Base.query.get_or_404(base_id)
    db.session.delete(base)
    db.session.commit()
    return jsonify({"deleted": base_id})


# ---------------------------------------------------------------------------
# CVOR system endpoints
# ---------------------------------------------------------------------------

@app.route("/api/systems", methods=["GET"])
def list_all_systems():
    systems = CVORSystem.query.all()
    return jsonify([s.to_dict() for s in systems])


@app.route("/api/bases/<int:base_id>/systems", methods=["GET"])
def list_systems(base_id):
    Base.query.get_or_404(base_id)
    systems = CVORSystem.query.filter_by(base_id=base_id).all()
    return jsonify([s.to_dict() for s in systems])


@app.route("/api/systems/<int:system_id>", methods=["GET"])
def get_system(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    return jsonify(system.to_dict())


@app.route("/api/bases/<int:base_id>/systems", methods=["POST"])
def create_system(base_id):
    Base.query.get_or_404(base_id)
    data = _json_or_400(["name", "ip_address"])
    system = CVORSystem(
        base_id=base_id,
        name=data["name"],
        ip_address=data["ip_address"],
        subnet_mask=data.get("subnet_mask", "255.255.255.0"),
        gateway=data.get("gateway", ""),
        tcp_port=int(data.get("tcp_port", 4000)),
        frequency=float(data.get("frequency", 0.0)),
        power_level=data.get("power_level", "HIGH"),
        mode=data.get("mode", "NORMAL"),
        ident=data.get("ident", ""),
    )
    db.session.add(system)
    db.session.commit()
    return jsonify(system.to_dict()), 201


@app.route("/api/systems/<int:system_id>", methods=["PUT"])
def update_system(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    data = _json_or_400()
    for field in ("name", "ip_address", "subnet_mask", "gateway", "tcp_port",
                  "frequency", "power_level", "mode", "ident", "status"):
        if field in data:
            value = data[field]
            if field == "tcp_port":
                value = int(value)
            if field == "frequency":
                value = float(value)
            setattr(system, field, value)
    system.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(system.to_dict())


@app.route("/api/systems/<int:system_id>", methods=["DELETE"])
def delete_system(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    db.session.delete(system)
    db.session.commit()
    return jsonify({"deleted": system_id})


# ---------------------------------------------------------------------------
# TCP/IP remote commands
# ---------------------------------------------------------------------------

@app.route("/api/systems/<int:system_id>/ping", methods=["POST"])
def ping_system(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    reachable = tcp_client.ping(system.ip_address, system.tcp_port)
    system.status = "ONLINE" if reachable else "OFFLINE"
    system.last_polled = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"reachable": reachable, "status": system.status})


@app.route("/api/systems/<int:system_id>/poll", methods=["POST"])
def poll_system(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    try:
        result = tcp_client.poll_status(system.ip_address, system.tcp_port, system_id)
        system.status = result.get("status", "UNKNOWN")
        system.last_polled = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify(result)
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/systems/<int:system_id>/command", methods=["POST"])
def send_command(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    data = _json_or_400(["cmd"])
    try:
        result = tcp_client.send_command(system.ip_address, system.tcp_port, data)
        return jsonify(result)
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/systems/<int:system_id>/set_frequency", methods=["POST"])
def set_frequency(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    data = _json_or_400(["frequency"])
    try:
        result = tcp_client.set_frequency(
            system.ip_address, system.tcp_port, system_id, float(data["frequency"])
        )
        system.frequency = float(data["frequency"])
        db.session.commit()
        return jsonify(result)
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/systems/<int:system_id>/set_power", methods=["POST"])
def set_power(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    data = _json_or_400(["level"])
    try:
        result = tcp_client.set_power(
            system.ip_address, system.tcp_port, system_id, data["level"]
        )
        system.power_level = data["level"]
        db.session.commit()
        return jsonify(result)
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/systems/<int:system_id>/set_mode", methods=["POST"])
def set_mode(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    data = _json_or_400(["mode"])
    try:
        result = tcp_client.set_mode(
            system.ip_address, system.tcp_port, system_id, data["mode"]
        )
        system.mode = data["mode"]
        db.session.commit()
        return jsonify(result)
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/systems/<int:system_id>/set_ident", methods=["POST"])
def set_ident(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    data = _json_or_400(["ident"])
    try:
        result = tcp_client.set_ident(
            system.ip_address, system.tcp_port, system_id, data["ident"]
        )
        system.ident = data["ident"]
        db.session.commit()
        return jsonify(result)
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/systems/<int:system_id>/reboot", methods=["POST"])
def reboot_system(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    try:
        result = tcp_client.reboot(system.ip_address, system.tcp_port, system_id)
        return jsonify(result)
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/systems/<int:system_id>/estop", methods=["POST"])
def estop_system(system_id):
    system = CVORSystem.query.get_or_404(system_id)
    try:
        result = tcp_client.emergency_stop(system.ip_address, system.tcp_port, system_id)
        return jsonify(result)
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 502


# ---------------------------------------------------------------------------
# Alarm endpoints
# ---------------------------------------------------------------------------

@app.route("/api/systems/<int:system_id>/alarms", methods=["GET"])
def list_alarms(system_id):
    CVORSystem.query.get_or_404(system_id)
    alarms = Alarm.query.filter_by(cvor_system_id=system_id).order_by(Alarm.raised_at.desc()).all()
    return jsonify([a.to_dict() for a in alarms])


@app.route("/api/systems/<int:system_id>/alarms/fetch", methods=["POST"])
def fetch_alarms(system_id):
    """Retrieve alarms from live system and persist them."""
    system = CVORSystem.query.get_or_404(system_id)
    try:
        result = tcp_client.get_alarms(system.ip_address, system.tcp_port, system_id)
        for alarm_data in result.get("alarms", []):
            alarm = Alarm(
                cvor_system_id=system_id,
                code=alarm_data.get("code", "UNKNOWN"),
                severity=alarm_data.get("severity", "WARNING"),
                message=alarm_data.get("message", ""),
            )
            db.session.add(alarm)
        db.session.commit()
        return jsonify(result)
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/alarms/<int:alarm_id>/acknowledge", methods=["POST"])
def acknowledge_alarm(alarm_id):
    alarm = Alarm.query.get_or_404(alarm_id)
    alarm.acknowledged = True
    alarm.acknowledged_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(alarm.to_dict())


# ---------------------------------------------------------------------------
# Shelter slot endpoints
# ---------------------------------------------------------------------------

@app.route("/api/systems/<int:system_id>/shelter", methods=["GET"])
def list_shelter_slots(system_id):
    CVORSystem.query.get_or_404(system_id)
    slots = ShelterSlot.query.filter_by(cvor_system_id=system_id).order_by(ShelterSlot.slot_number).all()
    return jsonify([s.to_dict() for s in slots])


@app.route("/api/systems/<int:system_id>/shelter", methods=["POST"])
def create_shelter_slot(system_id):
    CVORSystem.query.get_or_404(system_id)
    data = _json_or_400(["slot_number"])
    slot = ShelterSlot(
        cvor_system_id=system_id,
        slot_number=int(data["slot_number"]),
        equipment_type=data.get("equipment_type", ""),
        serial_number=data.get("serial_number", ""),
        description=data.get("description", ""),
    )
    db.session.add(slot)
    db.session.commit()
    return jsonify(slot.to_dict()), 201


@app.route("/api/shelter/<int:slot_id>", methods=["PUT"])
def update_shelter_slot(slot_id):
    slot = ShelterSlot.query.get_or_404(slot_id)
    data = _json_or_400()
    for field in ("slot_number", "equipment_type", "serial_number", "description"):
        if field in data:
            value = data[field]
            if field == "slot_number":
                value = int(value)
            setattr(slot, field, value)
    db.session.commit()
    return jsonify(slot.to_dict())


@app.route("/api/shelter/<int:slot_id>", methods=["DELETE"])
def delete_shelter_slot(slot_id):
    slot = ShelterSlot.query.get_or_404(slot_id)
    db.session.delete(slot)
    db.session.commit()
    return jsonify({"deleted": slot_id})


# ---------------------------------------------------------------------------
# Network detection
# ---------------------------------------------------------------------------

@app.route("/api/network", methods=["GET"])
def get_network_info():
    return jsonify(network_detect.get_local_network_info())


# ---------------------------------------------------------------------------
# File import
# ---------------------------------------------------------------------------

@app.route("/api/import", methods=["POST"])
def import_file():
    if "file" not in request.files:
        abort(400, description="No file part")
    f = request.files["file"]
    if not f.filename:
        abort(400, description="No filename")
    content = f.read().decode("utf-8", errors="replace")
    parsed = file_import.parse_file(f.filename, content)
    return jsonify({"filename": f.filename, "data": parsed})


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@app.route("/api/export", methods=["GET"])
def export_all():
    """Export all data as a JSON ZIP archive."""
    bases = [b.to_dict() for b in Base.query.all()]
    systems = [s.to_dict() for s in CVORSystem.query.all()]
    alarms = [a.to_dict() for a in Alarm.query.all()]
    slots = [s.to_dict() for s in ShelterSlot.query.all()]

    payload = json.dumps(
        {"bases": bases, "systems": systems, "alarms": alarms, "shelter_slots": slots},
        indent=2,
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mcs_export.json", payload)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="mcs_export.zip")


@app.route("/api/export/base/<int:base_id>", methods=["GET"])
def export_base(base_id):
    """Export a single base and its CVOR systems as a JSON ZIP."""
    base = Base.query.get_or_404(base_id)
    systems = CVORSystem.query.filter_by(base_id=base_id).all()

    payload = json.dumps(
        {"base": base.to_dict(), "systems": [s.to_dict() for s in systems]},
        indent=2,
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{base.icao}_export.json", payload)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{base.icao}_export.zip",
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "2.1"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    host = os.environ.get("MCS_HOST", "0.0.0.0")
    port = int(os.environ.get("MCS_PORT", 5000))
    debug = os.environ.get("MCS_DEBUG", "false").lower() == "true"
    app.run(host=host, port=port, debug=debug)
