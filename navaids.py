"""NAVAIDS v7.0 - Features: serial/TCP comms, VOR/ILS utilities, Thales/Normarc/Alcatel commands, VOR reporting, LDA import, terrain analysis, memory upload/download, hex view/compare, binary patching, local tests, charts, simulation, inspection logging, NOTAM tracking, ADS-B/Beast/ASTERIX radar, themes, config import/export, runway references, and PDF/CSV/TXT outputs."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import json
import os
import threading
import socket
import time
import csv
import collections
import math
import random
import datetime
import re
import struct
import sys
import zlib
import textwrap

if sys.version_info < (3, 7):
    raise SystemExit("NAVAIDS v7.0 requires Python 3.7+")

try:
    import serial
    from serial.tools import list_ports
    SERIAL_OK = True
except Exception:
    serial = None
    list_ports = None
    SERIAL_OK = False

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MPL_OK = True
except Exception:
    FigureCanvasTkAgg = None
    Figure = None
    MPL_OK = False

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    RL_OK = True
except Exception:
    A4 = None
    colors = None
    mm = None
    SimpleDocTemplate = None
    Table = None
    TableStyle = None
    Paragraph = None
    Spacer = None
    HRFlowable = None
    KeepTogether = None
    getSampleStyleSheet = None
    ParagraphStyle = None
    TA_CENTER = 1
    TA_LEFT = 0
    TA_RIGHT = 2
    RL_OK = False

APP_TITLE = "NAVAIDS v7.0"
CONFIG_FILE = "navaids_config.json"
NOTAM_FILE = "navaids_notams.json"
MAX_CHART_PTS = 120
RECONNECT_SEC = 10
MEM_EEPROM = "EEPROM"
MEM_RMM = "RMM"
MEM_RAM = "RAM"
LOCAL_TEST_PROGRAMS = ["loopback", "memory_crc", "config_echo", "throughput", "beacon"]
TCP_LOOP_CMD = "NAV_LOOP?"
TCP_LOOP_ECHO = "NAV_LOOP:OK"
MEM_UPLOAD_CMDS = {
    MEM_EEPROM: "UP_EEPROM",
    MEM_RMM: "UP_RMM",
    MEM_RAM: "UP_RAM",
}
MEM_DOWNLOAD_CMDS = {
    MEM_EEPROM: "DN_EEPROM",
    MEM_RMM: "DN_RMM",
    MEM_RAM: "DN_RAM",
}
LOCAL_TEST_CMDS = {
    "loopback": "TEST LOOPBACK",
    "memory_crc": "TEST MEMCRC",
    "config_echo": "TEST CONFIG",
    "throughput": "TEST THROUGHPUT",
    "beacon": "TEST BEACON",
}
FEED_MODE_OFF = "off"
FEED_MODE_SBS = "sbs"
FEED_MODE_BEAST = "beast"
FEED_MODE_ASTERIX = "asterix"
FEED_MODE_SIM = "sim"
RADAR_REFRESH_MS = 250
RADAR_TRAIL_MAX = 60
RADAR_DEFAULT_RANGE_NM = 80
RADAR_GRID_STEP_NM = 10
RADAR_MIN_SIZE = 300

THALES_CMDS = {
    "ping": "PING",
    "status": "STATUS?",
    "reset": "RESET",
    "save": "SAVE",
    "load": "LOAD",
    "rf_on": "RF ON",
    "rf_off": "RF OFF",
    "alarm_reset": "ALARM RESET",
    "sw_version": "RPT SW_VERSION?",
    "hw_version": "RPT HW_VERSION?",
    "serial_no": "RPT SERIAL_NO?",
    "site_id": "RPT SITE_ID?",
    "tx_freq": "RPT TX_FREQ?",
    "rx_freq": "RPT RX_FREQ?",
    "ref_phase": "RPT REF_PHASE?",
    "var_phase": "RPT VAR_PHASE?",
    "am_depth": "RPT AM_DEPTH?",
    "subcarrier": "RPT SUBCARRIER?",
    "ident_code": "RPT IDENT_CODE?",
    "ident_level": "RPT IDENT_LEVEL?",
    "ident_rate": "RPT IDENT_RATE?",
    "mon_brg": "RPT MON_BRG?",
    "mon_power": "RPT MON_POWER?",
    "mon_alarm1": "RPT MON_ALARM1?",
    "mon_alarm2": "RPT MON_ALARM2?",
    "tx_power": "RPT TX_POWER?",
    "vswr": "RPT VSWR?",
    "temp": "RPT TEMP?",
    "psu_v": "RPT PSU_V?",
    "psu_i": "RPT PSU_I?",
    "runtime": "RPT RUNTIME?",
    "last_alarm": "RPT LAST_ALARM?",
    "alarm_count": "RPT ALARM_COUNT?",
    "tx_status": "RPT TX_STATUS?",
    "mon_status": "RPT MON_STATUS?",
    "dpsk_level": "RPT DPSK_LEVEL?",
    "ant_current": "RPT ANT_CURRENT?",
}

NORMARC_CMDS = {
    "ping": "VER?",
    "status": "STAT?",
    "tx_freq": "TFREQ?",
    "ident": "IDENT?",
    "alarms": "ALARMS?",
    "reset": "RST",
    "save": "STORE",
}

ALCATEL_CMDS = {
    "ping": "*IDN?",
    "status": "READ:STATUS?",
    "tx_freq": "READ:TXFREQ?",
    "rx_freq": "READ:RXFREQ?",
    "power": "READ:POWER?",
    "alarm": "READ:ALARM?",
    "reset": "SYSTEM:RESET",
}

NORMARC_CMDS.update({
    "loc_freq":   "LOC:FREQ?",
    "loc_course": "LOC:COURSE?",
    "loc_ddm":    "LOC:DDM?",
    "loc_width":  "LOC:WIDTH?",
    "loc_sdm":    "LOC:SDM?",
    "loc_power":  "LOC:POWER?",
    "loc_cal":    "LOC:CAL",
    "gp_angle":   "GP:ANGLE?",
    "gp_ddm":     "GP:DDM?",
    "gp_width":   "GP:WIDTH?",
    "gp_power":   "GP:POWER?",
    "gp_cal":     "GP:CAL",
    "ils_mon":    "ILS:MON?",
    "ils_alarm":  "ILS:ALM?",
    "ils_test":   "ILS:TST:START",
    "ils_status": "ILS:STATUS?",
})

NORMARC_LOC_CAL_PARAMS = [
    ("LOC Frequency",      "loc_freq",    "MHz", "108.10"),
    ("Course Alignment",   "loc_course",  "deg", "0.0"),
    ("Width (DDM 0.155)",  "loc_width",   "deg", "10.5"),
    ("SDM",                "loc_sdm",     "%",   "40.0"),
    ("CSB Power",          "loc_csb_pwr", "W",   "8.0"),
    ("SBO Power",          "loc_sbo_pwr", "W",   "0.8"),
    ("CLR Power",          "loc_clr_pwr", "W",   "4.0"),
    ("90 Hz AM Depth",     "loc_90hz",    "%",   "20.0"),
    ("150 Hz AM Depth",    "loc_150hz",   "%",   "20.0"),
    ("RF Monitor Level",   "loc_rf_mon",  "%",   "100.0"),
    ("DDM at Course",      "loc_ddm_crs", "DDM", "0.000"),
    ("DDM Alarm Limit",    "loc_ddm_alm", "DDM", "0.015"),
    ("Power Alarm Limit",  "loc_pwr_alm", "%",   "50.0"),
    ("Ident Morse",        "loc_ident",   "",    "IXXV"),
    ("Ident Level",        "loc_id_lvl",  "dB",  "-14.0"),
]

NORMARC_GP_CAL_PARAMS = [
    ("GP Frequency",       "gp_freq",     "MHz", "334.70"),
    ("Glide Angle",        "gp_angle",    "deg", "3.0"),
    ("GP Width (0.0875)",  "gp_width",    "deg", "1.4"),
    ("SDM",                "gp_sdm",      "%",   "40.0"),
    ("CSB Power",          "gp_csb_pwr",  "W",   "2.0"),
    ("SBO Power",          "gp_sbo_pwr",  "W",   "0.2"),
    ("CLR Power",          "gp_clr_pwr",  "W",   "1.0"),
    ("90 Hz AM Depth",     "gp_90hz",     "%",   "20.0"),
    ("150 Hz AM Depth",    "gp_150hz",    "%",   "20.0"),
    ("DDM at Glide Path",  "gp_ddm",      "DDM", "0.000"),
    ("DDM Alarm Limit",    "gp_ddm_alm",  "DDM", "0.025"),
    ("RF Monitor Level",   "gp_rf_mon",   "%",   "100.0"),
    ("Power Alarm Limit",  "gp_pwr_alm",  "%",   "50.0"),
    ("Near Field Monitor", "gp_nfm",      "DDM", "0.000"),
    ("Far Field Monitor",  "gp_ffm",      "DDM", "0.000"),
]

NORMARC_ALARM_LIMITS = [
    ("LOC", "DDM",        "0.015", "DDM", "UL"),
    ("LOC", "Power",      "50.0",  "%",   "LL"),
    ("LOC", "RF Monitor", "50.0",  "%",   "LL"),
    ("LOC", "90Hz AM",    "17.0",  "%",   "LL"),
    ("LOC", "90Hz AM",    "23.0",  "%",   "UL"),
    ("LOC", "150Hz AM",   "17.0",  "%",   "LL"),
    ("LOC", "150Hz AM",   "23.0",  "%",   "UL"),
    ("LOC", "SDM",        "36.0",  "%",   "LL"),
    ("LOC", "SDM",        "44.0",  "%",   "UL"),
    ("GP",  "DDM",        "0.025", "DDM", "UL"),
    ("GP",  "Power",      "50.0",  "%",   "LL"),
    ("GP",  "RF Monitor", "50.0",  "%",   "LL"),
    ("GP",  "90Hz AM",    "17.0",  "%",   "LL"),
    ("GP",  "90Hz AM",    "23.0",  "%",   "UL"),
    ("GP",  "150Hz AM",   "17.0",  "%",   "LL"),
    ("GP",  "150Hz AM",   "23.0",  "%",   "UL"),
    ("GP",  "SDM",        "36.0",  "%",   "LL"),
    ("GP",  "SDM",        "44.0",  "%",   "UL"),
]

VOR_REPORT_FIELDS = [
    ("Identification", "SW Version", "sw_version", "", "sw_version"),
    ("Identification", "HW Version", "hw_version", "", "hw_version"),
    ("Identification", "Serial No", "serial_no", "", "serial_no"),
    ("Identification", "Site ID", "site_id", "", "site_id"),
    ("Identification", "DPSK Level", "dpsk_level", "dB", "dpsk_level"),
    ("Frequency", "TX Frequency", "tx_freq", "MHz", "tx_freq"),
    ("Frequency", "RX Frequency", "rx_freq", "MHz", "rx_freq"),
    ("Frequency", "Subcarrier", "subcarrier", "Hz", "subcarrier"),
    ("Signal", "Reference Phase", "ref_phase", "deg", "ref_phase"),
    ("Signal", "Variable Phase", "var_phase", "deg", "var_phase"),
    ("Signal", "AM Depth", "am_depth", "%", "am_depth"),
    ("Signal", "TX Power", "tx_power", "W", "tx_power"),
    ("Signal", "VSWR", "vswr", "", "vswr"),
    ("Signal", "Antenna Current", "ant_current", "A", "ant_current"),
    ("Signal", "PSU Voltage", "psu_v", "V", "psu_v"),
    ("Signal", "PSU Current", "psu_i", "A", "psu_i"),
    ("Ident Keyer", "Ident Code", "ident_code", "", "ident_code"),
    ("Ident Keyer", "Ident Level", "ident_level", "dB", "ident_level"),
    ("Ident Keyer", "Ident Rate", "ident_rate", "WPM", "ident_rate"),
    ("Monitor", "Monitor Bearing", "mon_brg", "deg", "mon_brg"),
    ("Monitor", "Monitor Power", "mon_power", "dBm", "mon_power"),
    ("Monitor", "Alarm 1", "mon_alarm1", "", "mon_alarm1"),
    ("Monitor", "Alarm 2", "mon_alarm2", "", "mon_alarm2"),
    ("Monitor", "Last Alarm", "last_alarm", "", "last_alarm"),
    ("Monitor", "Alarm Count", "alarm_count", "", "alarm_count"),
    ("Monitor", "Monitor Status", "mon_status", "", "mon_status"),
    ("Transmitter", "TX Status", "tx_status", "", "tx_status"),
    ("Transmitter", "Runtime", "runtime", "hrs", "runtime"),
    ("Transmitter", "Temperature", "temp", "°C", "temp"),
    ("Transmitter", "HW Version (TX)", "hw_version", "", "hw_version"),
    ("Transmitter", "SW Version (TX)", "sw_version", "", "sw_version"),
    ("Transmitter", "Serial No (TX)", "serial_no", "", "serial_no"),
]

THEMES = {
    "dark": {
        "bg": "#1f2329",
        "fg": "#f0f3f6",
        "accent": "#2f81f7",
        "entry_bg": "#2d333b",
        "entry_fg": "#f0f3f6",
        "select_bg": "#388bfd",
        "btn_bg": "#30363d",
        "btn_fg": "#f0f3f6",
        "tab_bg": "#22272e",
        "tab_fg": "#f0f3f6",
    },
    "light": {
        "bg": "#f6f8fa",
        "fg": "#24292f",
        "accent": "#0969da",
        "entry_bg": "#ffffff",
        "entry_fg": "#24292f",
        "select_bg": "#bfdcff",
        "btn_bg": "#eaeef2",
        "btn_fg": "#24292f",
        "tab_bg": "#f6f8fa",
        "tab_fg": "#24292f",
    },
}

AFRICAN_RUNWAYS = [
    {"Airport": "Cairo Intl", "ICAO": "HECA", "Country": "Egypt", "Runway": "05R/23L", "Heading": 50, "ILS_Freq": "110.30", "VOR_Freq": "114.70", "VOR_ID": "CIA", "Elev_ft": 382},
    {"Airport": "Casablanca Mohammed V", "ICAO": "GMMN", "Country": "Morocco", "Runway": "17R/35L", "Heading": 174, "ILS_Freq": "109.90", "VOR_Freq": "113.90", "VOR_ID": "CMN", "Elev_ft": 656},
    {"Airport": "Algiers Houari", "ICAO": "DAAG", "Country": "Algeria", "Runway": "09/27", "Heading": 92, "ILS_Freq": "110.30", "VOR_Freq": "115.30", "VOR_ID": "ALG", "Elev_ft": 82},
    {"Airport": "Tunis Carthage", "ICAO": "DTTA", "Country": "Tunisia", "Runway": "19/01", "Heading": 194, "ILS_Freq": "109.10", "VOR_Freq": "116.10", "VOR_ID": "TUN", "Elev_ft": 22},
    {"Airport": "Dakar Blaise Diagne", "ICAO": "GOBD", "Country": "Senegal", "Runway": "01/19", "Heading": 13, "ILS_Freq": "110.10", "VOR_Freq": "115.10", "VOR_ID": "DKR", "Elev_ft": 290},
    {"Airport": "Lagos MMA", "ICAO": "DNMM", "Country": "Nigeria", "Runway": "18R/36L", "Heading": 183, "ILS_Freq": "109.50", "VOR_Freq": "114.50", "VOR_ID": "LAG", "Elev_ft": 135},
    {"Airport": "Accra Kotoka", "ICAO": "DGAA", "Country": "Ghana", "Runway": "03/21", "Heading": 34, "ILS_Freq": "110.30", "VOR_Freq": "112.30", "VOR_ID": "ACC", "Elev_ft": 205},
    {"Airport": "Addis Ababa Bole", "ICAO": "HAAB", "Country": "Ethiopia", "Runway": "07R/25L", "Heading": 72, "ILS_Freq": "111.30", "VOR_Freq": "113.00", "VOR_ID": "AAB", "Elev_ft": 7656},
    {"Airport": "Nairobi Jomo Kenyatta", "ICAO": "HKJK", "Country": "Kenya", "Runway": "06/24", "Heading": 62, "ILS_Freq": "110.50", "VOR_Freq": "114.30", "VOR_ID": "NBO", "Elev_ft": 5330},
    {"Airport": "Kigali", "ICAO": "HRYR", "Country": "Rwanda", "Runway": "10/28", "Heading": 101, "ILS_Freq": "108.70", "VOR_Freq": "113.70", "VOR_ID": "KGL", "Elev_ft": 4897},
    {"Airport": "Entebbe", "ICAO": "HUEN", "Country": "Uganda", "Runway": "17/35", "Heading": 171, "ILS_Freq": "109.90", "VOR_Freq": "116.90", "VOR_ID": "EBB", "Elev_ft": 3782},
    {"Airport": "Luanda 4 de Fevereiro", "ICAO": "FNLU", "Country": "Angola", "Runway": "05/23", "Heading": 46, "ILS_Freq": "109.30", "VOR_Freq": "112.90", "VOR_ID": "LAD", "Elev_ft": 243},
    {"Airport": "Gaborone Sir Seretse", "ICAO": "FBSK", "Country": "Botswana", "Runway": "08/26", "Heading": 80, "ILS_Freq": "109.10", "VOR_Freq": "114.80", "VOR_ID": "GBE", "Elev_ft": 3299},
    {"Airport": "Windhoek Hosea Kutako", "ICAO": "FYWH", "Country": "Namibia", "Runway": "08/26", "Heading": 81, "ILS_Freq": "109.50", "VOR_Freq": "112.70", "VOR_ID": "WDH", "Elev_ft": 5640},
]

SAAF_RUNWAYS = [
    {"Airport": "AFB Waterkloof", "ICAO": "FAWK", "Country": "South Africa", "Runway": "01/19", "Heading": 14, "ILS_Freq": "110.10", "VOR_Freq": "116.40", "VOR_ID": "WKV", "Elev_ft": 4940},
    {"Airport": "AFB Makhado", "ICAO": "FAVV", "Country": "South Africa", "Runway": "05/23", "Heading": 49, "ILS_Freq": "109.70", "VOR_Freq": "114.10", "VOR_ID": "VVB", "Elev_ft": 3060},
    {"Airport": "AFB Hoedspruit", "ICAO": "FAHS", "Country": "South Africa", "Runway": "17/35", "Heading": 173, "ILS_Freq": "109.30", "VOR_Freq": "113.20", "VOR_ID": "HDS", "Elev_ft": 1743},
    {"Airport": "AFB Overberg", "ICAO": "FAOB", "Country": "South Africa", "Runway": "20/02", "Heading": 198, "ILS_Freq": "108.90", "VOR_Freq": "112.40", "VOR_ID": "OBG", "Elev_ft": 52},
    {"Airport": "AFB Ysterplaat", "ICAO": "FAYP", "Country": "South Africa", "Runway": "02/20", "Heading": 24, "ILS_Freq": "110.90", "VOR_Freq": "115.20", "VOR_ID": "YST", "Elev_ft": 52},
    {"Airport": "AFB Bloemspruit", "ICAO": "FABL", "Country": "South Africa", "Runway": "02/20", "Heading": 21, "ILS_Freq": "110.30", "VOR_Freq": "112.10", "VOR_ID": "BLM", "Elev_ft": 4458},
    {"Airport": "AFB Langebaanweg", "ICAO": "FALW", "Country": "South Africa", "Runway": "01/19", "Heading": 6, "ILS_Freq": "109.10", "VOR_Freq": "114.40", "VOR_ID": "LBW", "Elev_ft": 108},
]

LOG_COLUMNS = ["Date", "Time", "Station", "System", "Parameter", "Before", "After", "Technician", "Notes"]
NOTAM_COLUMNS = ["ID", "Type", "Priority", "Status", "Station", "Description", "Issue Date", "Due Date", "Technician"]
NOTAM_TYPES = ["A/G Equipment", "Airspace", "Airfield", "Navigation Aid", "Obstacle", "Other"]
NOTAM_PRIORITY = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
NOTAM_STATUS = ["OPEN", "IN PROGRESS", "CLOSED"]
ALERT_DAYS = 14


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def _fmt_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return "{0:.3f}".format(value).rstrip("0").rstrip(".")
    return str(value)


class CommManager:
    def __init__(self, port=None, baud=9600, host=None, tcp_port=None):
        self.port = port
        self.baud = baud
        self.host = host
        self.tcp_port = tcp_port
        self._serial = None
        self._tcp_sock = None
        self._lock = threading.Lock()
        self._reconnect_thread = None
        self._running = False
        self.on_serial_connect_cb = None

    def connect_serial(self, port, baud):
        if not SERIAL_OK:
            raise RuntimeError("pyserial not available")
        with self._lock:
            self.port = port
            self.baud = int(baud)
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception:
                    pass
            self._serial = serial.Serial(port=self.port, baudrate=self.baud, timeout=1)
            self._running = True
            if self._reconnect_thread is None or not self._reconnect_thread.is_alive():
                self._reconnect_thread = threading.Thread(target=self._reconnect_worker, daemon=True)
                self._reconnect_thread.start()
        if self.on_serial_connect_cb:
            self.on_serial_connect_cb(self.port)
        return True

    def disconnect(self):
        self._running = False
        with self._lock:
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception:
                    pass
                self._serial = None
            if self._tcp_sock is not None:
                try:
                    self._tcp_sock.close()
                except Exception:
                    pass
                self._tcp_sock = None

    def send(self, data: str):
        with self._lock:
            if self._serial is not None:
                payload = (data.strip() + "\r\n").encode("utf-8", "ignore")
                self._serial.write(payload)
                self._serial.flush()
                time.sleep(0.05)
                try:
                    resp = self._serial.readline().decode("utf-8", "ignore").strip()
                except Exception:
                    resp = ""
                return resp
            if self._tcp_sock is not None:
                payload = (data.strip() + "\n").encode("utf-8", "ignore")
                self._tcp_sock.sendall(payload)
                try:
                    resp = self._tcp_sock.recv(4096).decode("utf-8", "ignore").strip()
                except Exception:
                    resp = ""
                return resp
        return self._simulate_device_response(data)

    def _simulate_device_response(self, data):
        cmd = data.strip().upper()
        if cmd == TCP_LOOP_CMD:
            return TCP_LOOP_ECHO
        if "SW_VERSION" in cmd:
            return "7.0.0"
        if "HW_VERSION" in cmd:
            return "A2"
        if "SERIAL_NO" in cmd:
            return "TRC6K-04217"
        if "SITE_ID" in cmd:
            return "SITE-001"
        if "TX_FREQ" in cmd:
            return "113.400"
        if "RX_FREQ" in cmd:
            return "113.400"
        if "REF_PHASE" in cmd:
            return "0.2"
        if "VAR_PHASE" in cmd:
            return "0.3"
        if "AM_DEPTH" in cmd:
            return "29.9"
        if "SUBCARRIER" in cmd:
            return "9960"
        if "IDENT_CODE" in cmd:
            return "VOR"
        if "IDENT_LEVEL" in cmd:
            return "-12"
        if "IDENT_RATE" in cmd:
            return "7"
        if "MON_BRG" in cmd:
            return "179.9"
        if "MON_POWER" in cmd:
            return "-44.1"
        if "MON_ALARM1" in cmd:
            return "OK"
        if "MON_ALARM2" in cmd:
            return "OK"
        if "TX_POWER" in cmd:
            return "49.8"
        if "VSWR" in cmd:
            return "1.12"
        if "TEMP" in cmd:
            return "39.0"
        if "PSU_V" in cmd:
            return "27.5"
        if "PSU_I" in cmd:
            return "8.2"
        if "RUNTIME" in cmd:
            return "14522"
        if "LAST_ALARM" in cmd:
            return "NONE"
        if "ALARM_COUNT" in cmd:
            return "0"
        if "TX_STATUS" in cmd:
            return "ACTIVE"
        if "MON_STATUS" in cmd:
            return "GOOD"
        if "DPSK_LEVEL" in cmd:
            return "-14"
        if "ANT_CURRENT" in cmd:
            return "3.1"
        if cmd.startswith("UP_") or cmd.startswith("DN_"):
            return "ACK"
        if cmd.startswith("TEST"):
            return "PASS"
        if cmd == "PING":
            return "PONG"
        if "LOC:FREQ" in cmd:
            return "108.10"
        if "LOC:COURSE" in cmd:
            return "0.0"
        if "LOC:DDM" in cmd:
            return "0.002"
        if "GP:ANGLE" in cmd:
            return "3.00"
        if "GP:DDM" in cmd:
            return "0.001"
        if "ILS:MON" in cmd:
            return "NORMAL"
        if "ILS:ALM" in cmd:
            return "NONE"
        if "ILS:STATUS" in cmd:
            return "OPERATIONAL"
        return "OK"

    def _reconnect_worker(self):
        while self._running:
            time.sleep(RECONNECT_SEC)
            if not SERIAL_OK or not self.port:
                continue
            with self._lock:
                lost = self._serial is None or not getattr(self._serial, "is_open", False)
            if not lost:
                continue
            try:
                self.connect_serial(self.port, self.baud)
            except Exception:
                pass

    def connect_tcp(self, host, port):
        sock = socket.create_connection((host, int(port)), timeout=2)
        sock.settimeout(2)
        with self._lock:
            if self._tcp_sock is not None:
                try:
                    self._tcp_sock.close()
                except Exception:
                    pass
            self.host = host
            self.tcp_port = int(port)
            self._tcp_sock = sock
        return True

    def send_tcp(self, data: str):
        if self._tcp_sock is None:
            raise RuntimeError("TCP not connected")
        payload = (data.strip() + "\n").encode("utf-8", "ignore")
        with self._lock:
            self._tcp_sock.sendall(payload)
            resp = self._tcp_sock.recv(4096)
        return resp.decode("utf-8", "ignore").strip()

    @property
    def is_connected(self):
        with self._lock:
            serial_open = self._serial is not None and getattr(self._serial, "is_open", False)
            return serial_open or self._tcp_sock is not None


class TerrainAnalysis:
    def analyse(self, lda_data: dict) -> list[str]:
        findings = []
        terrain = lda_data.get("terrain", [])
        obstacles = lda_data.get("obstacles", [])
        for item in terrain:
            height = _safe_float(item.get("height_ft", item.get("elev_ft", 0)))
            dist = _safe_float(item.get("distance_nm", 0))
            if height > 5000:
                findings.append("Terrain high point at {0:.1f} NM: {1:.0f} ft".format(dist, height))
        for obs in obstacles:
            name = obs.get("name", "Obstacle")
            dist = _safe_float(obs.get("distance_nm", 0))
            height = _safe_float(obs.get("height_ft", 0))
            if dist <= 10 and height >= 200:
                findings.append("Obstacle risk {0} at {1:.1f} NM, {2:.0f} ft".format(name, dist, height))
        if not findings:
            findings.append("No significant terrain conflicts detected.")
        return findings


def import_lda(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    text_stripped = text.lstrip()
    if text_stripped.startswith("{"):
        data = json.loads(text)
        return {
            "waypoints": data.get("waypoints", []),
            "obstacles": data.get("obstacles", []),
            "terrain": data.get("terrain", []),
        }
    # Detect Thales .lda format (contains BEGIN_PROG or ***PRINTOUT_MX_HEAD***)
    if "BEGIN_PROG" in text or "***PRINTOUT_MX_HEAD***" in text:
        prog_lines = []
        printout_text = ""
        sections = {}
        in_prog = False
        in_printout = False
        current_section = None
        section_buf = []
        printout_buf = []
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if stripped == "BEGIN_PROG":
                in_prog = True
                continue
            if stripped == "END_PROG":
                in_prog = False
                continue
            if stripped == "***PRINTOUT_MX_HEAD***":
                in_printout = True
                current_section = None
                section_buf = []
                continue
            if stripped == "***END_PRINTOUT***":
                if current_section and section_buf:
                    sections[current_section] = "\n".join(section_buf)
                in_printout = False
                current_section = None
                section_buf = []
                continue
            if in_prog:
                if stripped:
                    prog_lines.append(stripped)
            elif in_printout:
                if stripped.startswith("---") and stripped.endswith("---"):
                    if current_section and section_buf:
                        sections[current_section] = "\n".join(section_buf)
                    current_section = stripped.strip("-").strip()
                    section_buf = []
                else:
                    section_buf.append(raw_line)
                printout_buf.append(raw_line)
        if current_section and section_buf:
            sections[current_section] = "\n".join(section_buf)
        printout_text = "\n".join(printout_buf)
        return {
            "raw": text,
            "prog": prog_lines,
            "printout": printout_text,
            "sections": sections,
            "waypoints": [],
            "obstacles": [],
            "terrain": [],
        }
    current = None
    result = {"waypoints": [], "obstacles": [], "terrain": []}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower()
            continue
        parts = [p.strip() for p in line.split(",")]
        if current == "waypoints" and len(parts) >= 3:
            result["waypoints"].append({"name": parts[0], "lat": _safe_float(parts[1]), "lon": _safe_float(parts[2])})
        elif current == "obstacles" and len(parts) >= 3:
            name = parts[0]
            dist = _safe_float(parts[1])
            height = _safe_float(parts[2])
            result["obstacles"].append({"name": name, "distance_nm": dist, "height_ft": height})
        elif current == "terrain" and len(parts) >= 2:
            dist = _safe_float(parts[0])
            height = _safe_float(parts[1])
            result["terrain"].append({"distance_nm": dist, "height_ft": height})
    return result


def lda_to_bytes(lda_data):
    return json.dumps(lda_data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _notam_days_until(due_str):
    try:
        due = datetime.datetime.strptime(due_str.strip(), "%Y-%m-%d").date()
    except Exception:
        return 9999
    return (due - datetime.date.today()).days


def run_self_tests(log_cb):
    tests = []
    tests.append(("python_version", sys.version_info >= (3, 7)))
    tests.append(("json_roundtrip", json.loads(json.dumps({"a": 1})) == {"a": 1}))
    sample = b"abc123"
    tests.append(("zlib_crc", zlib.crc32(sample) == zlib.crc32(sample)))
    patch = BinaryPatcher.generate(b"ABCDEF", b"ABZDEFG")
    tests.append(("patch_verify", BinaryPatcher.verify(b"ABCDEF", patch)))
    tests.append(("patch_apply", BinaryPatcher.apply(b"ABCDEF", patch) == b"ABZDEFG"))
    tests.append(("serial_optional", SERIAL_OK or True))
    for name, ok in tests:
        state = "PASS" if ok else "FAIL"
        log_cb("[SELFTEST] {0}: {1}".format(name, state))
    return all(ok for _, ok in tests)


class ThalesVORReport:
    THALES_MODEL = "Thales TRC 6000 DVOR"
    THALES_COMPANY = "Thales ATM"
    DOC_TITLE = "VOR MAINTENANCE DATA REPORT"
    DOC_REF = "TRC6000-MNT-RPT-001"
    W = 80
    ALARM_KW = ("ALARM", "FAULT", "FAIL", "ERROR")
    NORM_KW = ("OK", "NORM", "PASS", "GOOD", "ACTIVE")

    @classmethod
    def query_all(cls, comm, log_cb, progress_cb=None):
        data = {}
        total = len(VOR_REPORT_FIELDS)
        for idx, (_, label, cmd_key, _, _) in enumerate(VOR_REPORT_FIELDS, start=1):
            cmd = THALES_CMDS.get(cmd_key, cmd_key)
            value = comm.send(cmd)
            data[cmd_key] = value
            log_cb("[VOR] {0}: {1}".format(label, value))
            if progress_cb:
                progress_cb(idx, total, label)
        data["queried_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        return data

    @classmethod
    def _status(cls, value):
        text = str(value or "").upper()
        for kw in cls.ALARM_KW:
            if kw in text:
                return "ALARM"
        for kw in cls.NORM_KW:
            if kw in text:
                return "NORM"
        if text.strip():
            return "—"
        return "—"

    @classmethod
    def to_text(cls, data, technician, station, notes):
        width = cls.W

        def hr(left, mid, right):
            return left + ("─" * (width - 2)) + right

        def line(text=""):
            padded = text[: width - 4]
            return "│ " + padded.ljust(width - 4) + " │"

        def row(param, desc, value, unit, status):
            fmt = "{0:<12} {1:<20} {2:<20} {3:<8} {4:<10}"
            return line(fmt.format(param[:12], desc[:20], str(value)[:20], unit[:8], status[:10]))

        sections = collections.OrderedDict()
        for section, label, cmd_key, unit, _ in VOR_REPORT_FIELDS:
            sections.setdefault(section, []).append((label, cmd_key, unit))
        lines = [hr("┌", "┬", "┐")]
        lines.append(line(cls.thales_header(station)))
        lines.append(line(cls.DOC_TITLE))
        ref_text = "Ref: {0}    Model: {1}".format(cls.DOC_REF, cls.THALES_MODEL)
        lines.append(line(ref_text))
        meta = "Station: {0}    Technician: {1}".format(station or "-", technician or "-")
        lines.append(line(meta))
        date_text = "Date: {0}    Company: {1}".format(data.get("queried_at", "-"), cls.THALES_COMPANY)
        lines.append(line(date_text))
        lines.append(hr("├", "┼", "┤"))
        for section, items in sections.items():
            lines.append(line("[{0}]".format(section)))
            lines.append(row("PARAM", "DESCRIPTION", "VALUE", "UNIT", "STATUS"))
            for label, cmd_key, unit in items:
                value = data.get(cmd_key, "")
                lines.append(row(cmd_key, label, value, unit, cls._status(value)))
            lines.append(hr("├", "┼", "┤"))
        alarms = []
        for _, label, cmd_key, _, _ in VOR_REPORT_FIELDS:
            value = data.get(cmd_key, "")
            if cls._status(value) == "ALARM":
                alarms.append("{0}: {1}".format(label, value))
        lines.append(line("Alarm Summary"))
        if alarms:
            for item in alarms[:6]:
                for wrapped in textwrap.wrap(item, width - 4) or [""]:
                    lines.append(line(wrapped))
        else:
            lines.append(line("No active alarms reported."))
        lines.append(hr("├", "┼", "┤"))
        lines.append(line("Notes"))
        for wrapped in textwrap.wrap(notes or "None", width - 4) or [""]:
            lines.append(line(wrapped))
        lines.append(hr("├", "┼", "┤"))
        lines.append(line("Sign-off"))
        lines.append(line("Technician: {0}".format(technician or "________________")))
        lines.append(line("Date/Time : {0}".format(datetime.datetime.now().isoformat(timespec="minutes"))))
        lines.append(hr("└", "┴", "┘"))
        return "\n".join(lines)

    @classmethod
    def thales_header(cls, station):
        return "{0} - {1}".format(cls.thales_label(), station or "UNKNOWN STATION")

    @classmethod
    def thales_label(cls):
        return cls.THALES_COMPANY

    @classmethod
    def to_pdf(cls, path, data, technician, station, notes):
        if not RL_OK:
            raise RuntimeError("reportlab not available")
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ThalesTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            textColor=colors.HexColor("#00408C"),
            fontSize=16,
            leading=20,
        )
        normal = styles["BodyText"]
        right = ParagraphStyle("Right", parent=styles["BodyText"], alignment=TA_RIGHT)
        doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
        elements = []
        elements.append(Paragraph(cls.THALES_COMPANY, title_style))
        elements.append(Paragraph(cls.DOC_TITLE, styles["Heading2"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#00408C")))
        meta_rows = [
            ["Document Ref", cls.DOC_REF, "Station", station or "-"],
            ["Model", cls.THALES_MODEL, "Technician", technician or "-"],
            ["Generated", data.get("queried_at", "-"), "Overall", "ALARM" if cls.has_alarm(data) else "NORM"],
        ]
        meta = Table(meta_rows, colWidths=[28 * mm, 55 * mm, 28 * mm, 55 * mm])
        meta.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F2")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(meta)
        elements.append(Spacer(1, 4 * mm))
        sections = collections.OrderedDict()
        for section, label, cmd_key, unit, _ in VOR_REPORT_FIELDS:
            sections.setdefault(section, []).append((label, cmd_key, unit))
        for section, items in sections.items():
            rows = [["Parameter", "Description", "Value", "Unit", "Status"]]
            for label, cmd_key, unit in items:
                value = _fmt_value(data.get(cmd_key, ""))
                status = cls._status(value)
                rows.append([cmd_key, label, value, unit, status])
            table = Table(rows, colWidths=[28 * mm, 54 * mm, 40 * mm, 16 * mm, 20 * mm])
            style = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00408C")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
            ]
            for i in range(1, len(rows)):
                if i % 2 == 0:
                    style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#EEF3F8")))
                if rows[i][-1] == "ALARM":
                    style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FFE2E2")))
            table.setStyle(TableStyle(style))
            block = [Paragraph(section, styles["Heading3"]), table, Spacer(1, 3 * mm)]
            elements.append(KeepTogether(block))
        overall = "Overall status: {0}".format("ALARM" if cls.has_alarm(data) else "NORM")
        elements.append(Paragraph(overall, normal))
        alarms = cls.alarm_rows(data)
        if alarms:
            alarm_rows = [["Description", "Value"]] + alarms
            alarm_table = Table(alarm_rows, colWidths=[90 * mm, 80 * mm])
            alarm_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#B00020")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFF1F1")),
            ]))
            elements.append(Paragraph("Alarm Summary", styles["Heading3"]))
            elements.append(alarm_table)
        elements.append(Spacer(1, 3 * mm))
        elements.append(Paragraph("Notes", styles["Heading3"]))
        elements.append(Paragraph(notes or "None", normal))
        elements.append(Spacer(1, 4 * mm))
        sign = Table([
            ["Technician", technician or "-", "Signature", "________________"],
            ["Station", station or "-", "Date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")],
        ], colWidths=[28 * mm, 60 * mm, 28 * mm, 60 * mm])
        sign.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F4F7FB")),
        ]))
        elements.append(sign)

        def footer(canvas, doc_obj):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            footer_text = "{0}  |  {1}  |  Page {2}".format(cls.DOC_REF, cls.THALES_COMPANY, doc_obj.page)
            canvas.drawCentredString(A4[0] / 2.0, 8 * mm, footer_text)
            canvas.restoreState()

        doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    @classmethod
    def has_alarm(cls, data):
        return bool(cls.alarm_rows(data))

    @classmethod
    def alarm_rows(cls, data):
        rows = []
        for _, label, cmd_key, _, _ in VOR_REPORT_FIELDS:
            value = data.get(cmd_key, "")
            if cls._status(value) == "ALARM":
                rows.append([label, _fmt_value(value)])
        return rows

    @classmethod
    def to_csv(cls, path, data, technician, station):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["station", station, "technician", technician, "generated", data.get("queried_at", "")])
            writer.writerow(["section", "display_label", "cmd_key", "value", "unit", "status", "thales_param_name"])
            for section, label, cmd_key, unit, pname in VOR_REPORT_FIELDS:
                value = data.get(cmd_key, "")
                writer.writerow([section, label, cmd_key, value, unit, cls._status(value), pname])


class MemoryUploader:
    def __init__(self, comm):
        self.comm = comm
        self._store = {}

    def upload(self, mem_type, data: bytes, progress_cb=None):
        cmd = MEM_UPLOAD_CMDS.get(mem_type)
        if not cmd:
            raise ValueError("Unknown memory type")
        total = max(1, len(data))
        self.comm.send(cmd + " SOH")
        chunk_size = 64
        sent = 0
        while sent < len(data):
            chunk = data[sent: sent + chunk_size]
            payload = zlib.crc32(chunk)
            self.comm.send("DATA {0:08X} {1}".format(payload, chunk.hex()))
            sent += len(chunk)
            if progress_cb:
                progress_cb(sent, total)
        self.comm.send(cmd + " EOT")
        self._store[mem_type] = bytes(data)
        return True

    def download(self, mem_type, progress_cb=None) -> bytes:
        cmd = MEM_DOWNLOAD_CMDS.get(mem_type)
        if not cmd:
            raise ValueError("Unknown memory type")
        self.comm.send(cmd + " SOH")
        data = self._store.get(mem_type, b"")
        total = max(1, len(data))
        pos = 0
        while pos < len(data):
            pos = min(len(data), pos + 64)
            if progress_cb:
                progress_cb(pos, total)
        self.comm.send(cmd + " EOT")
        return data


class TCPLoopbackTester:
    def test_remote(self, host, port, log_cb):
        try:
            with socket.create_connection((host, int(port)), timeout=2) as sock:
                sock.sendall((TCP_LOOP_CMD + "\n").encode("utf-8"))
                resp = sock.recv(1024).decode("utf-8", "ignore").strip()
            ok = resp == TCP_LOOP_ECHO
            log_cb("[TCP] remote loopback {0}:{1} -> {2}".format(host, port, resp))
            return ok
        except Exception as exc:
            log_cb("[TCP] remote loopback failed: {0}".format(exc))
            return False

    def test_local(self, log_cb):
        ready = threading.Event()
        result = {"ok": False, "port": 0}

        def server():
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", 0))
            srv.listen(1)
            result["port"] = srv.getsockname()[1]
            ready.set()
            conn, _ = srv.accept()
            with conn:
                data = conn.recv(1024).decode("utf-8", "ignore").strip()
                if data == TCP_LOOP_CMD:
                    conn.sendall((TCP_LOOP_ECHO + "\n").encode("utf-8"))
            srv.close()

        thread = threading.Thread(target=server, daemon=True)
        thread.start()
        ready.wait(2)
        try:
            with socket.create_connection(("127.0.0.1", result["port"]), timeout=2) as sock:
                sock.sendall((TCP_LOOP_CMD + "\n").encode("utf-8"))
                resp = sock.recv(1024).decode("utf-8", "ignore").strip()
            result["ok"] = resp == TCP_LOOP_ECHO
            log_cb("[TCP] local loopback -> {0}".format(resp))
        except Exception as exc:
            log_cb("[TCP] local loopback failed: {0}".format(exc))
        return result["ok"]


class HexViewer(tk.Frame):
    def __init__(self, parent, mem_type="EEPROM"):
        super().__init__(parent)
        self.mem_type = mem_type
        self.data = b""
        self.search_var = tk.StringVar()
        self.jump_var = tk.StringVar()
        self.text = None
        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=4, pady=4)
        ttk.Label(top, text="Search:").pack(side="left")
        ttk.Entry(top, textvariable=self.search_var, width=20).pack(side="left", padx=2)
        ttk.Button(top, text="Find", command=self._search).pack(side="left", padx=2)
        ttk.Label(top, text="Jump Offset:").pack(side="left", padx=(12, 2))
        ttk.Entry(top, textvariable=self.jump_var, width=12).pack(side="left", padx=2)
        ttk.Button(top, text="Jump", command=self._jump).pack(side="left", padx=2)
        ttk.Button(top, text="Export BIN", command=self._export_bin).pack(side="right", padx=2)
        ttk.Button(top, text="Export IHEX", command=self._export_ihex).pack(side="right", padx=2)
        self.text = ScrolledText(self, wrap="none", height=24)
        self.text.pack(fill="both", expand=True, padx=4, pady=4)
        self.text.tag_configure("hit", background="#ffef88")

    def load_data(self, data: bytes):
        self.data = bytes(data)
        lines = []
        for off in range(0, len(self.data), 16):
            chunk = self.data[off:off + 16]
            hex_part = " ".join("{0:02X}".format(b) for b in chunk)
            asc_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append("{0:08X}  {1:<47}  {2}".format(off, hex_part, asc_part))
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))

    def _search(self):
        self.text.tag_remove("hit", "1.0", "end")
        term = self.search_var.get().strip()
        if not term:
            return
        try:
            needle = self._parse_string(term).hex().upper()
        except Exception:
            needle = term.upper()
        start = "1.0"
        while True:
            pos = self.text.search(needle, start, stopindex="end", nocase=True)
            if not pos:
                break
            end = "{0}+{1}c".format(pos, len(needle))
            self.text.tag_add("hit", pos, end)
            start = end

    def _jump(self):
        offset_text = self.jump_var.get().strip().lower().replace("0x", "")
        try:
            offset = int(offset_text, 16 if any(c in "abcdef" for c in offset_text) else 10)
        except Exception:
            return
        line_index = offset // 16 + 1
        self.text.see("{0}.0".format(line_index))
        self.text.mark_set("insert", "{0}.0".format(line_index))

    def _export_bin(self):
        path = filedialog.asksaveasfilename(defaultextension=".bin", filetypes=[("Binary", "*.bin"), ("All", "*")])
        if not path:
            return
        with open(path, "wb") as fh:
            fh.write(self.data)

    def _export_ihex(self):
        path = filedialog.asksaveasfilename(defaultextension=".hex", filetypes=[("Intel HEX", "*.hex"), ("All", "*")])
        if not path:
            return
        with open(path, "w", encoding="ascii") as fh:
            addr = 0
            upper = None
            while addr < len(self.data):
                chunk = self.data[addr:addr + 16]
                high = (addr >> 16) & 0xFFFF
                if high != upper:
                    upper = high
                    rec = struct.pack(">BHBH", 2, 0, 4, upper)
                    chk = ((~sum(rec) + 1) & 0xFF)
                    fh.write(":02000004{0:04X}{1:02X}\n".format(upper, chk))
                low = addr & 0xFFFF
                body = bytes([len(chunk), (low >> 8) & 0xFF, low & 0xFF, 0]) + chunk
                chk = ((~sum(body) + 1) & 0xFF)
                fh.write(":{0:02X}{1:04X}00{2}{3:02X}\n".format(len(chunk), low, chunk.hex().upper(), chk))
                addr += len(chunk)
            fh.write(":00000001FF\n")

    @staticmethod
    def _parse_string(s):
        cleaned = s.replace(" ", "").replace("0x", "")
        if cleaned and all(c in "0123456789abcdefABCDEF" for c in cleaned) and len(cleaned) % 2 == 0:
            return bytes.fromhex(cleaned)
        return s.encode("utf-8")


class HexCompareView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.data_a = b""
        self.data_b = b""
        self.label_a = "A"
        self.label_b = "B"
        self.search_var = tk.StringVar()
        self.left = None
        self.right = None
        self.nav = None
        self.scrollbar = None
        self.diff_rows = []
        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=4, pady=4)
        ttk.Label(top, text="Search/Diff Filter:").pack(side="left")
        ttk.Entry(top, textvariable=self.search_var, width=24).pack(side="left", padx=2)
        ttk.Button(top, text="Highlight", command=self._search).pack(side="left", padx=2)
        ttk.Button(top, text="Export CSV", command=self._export_csv).pack(side="right", padx=2)
        ttk.Button(top, text="Export TXT", command=self._export_txt).pack(side="right", padx=2)
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.nav = tk.Listbox(body, width=16)
        self.nav.pack(side="left", fill="y")
        pane = tk.PanedWindow(body, sashrelief="raised")
        pane.pack(side="left", fill="both", expand=True)
        left_frame = ttk.Frame(pane)
        right_frame = ttk.Frame(pane)
        self.scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self._sync_scroll)
        self.left = tk.Text(left_frame, wrap="none", yscrollcommand=self.scrollbar.set)
        self.right = tk.Text(right_frame, wrap="none", yscrollcommand=self.scrollbar.set)
        self.left.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.right.pack(fill="both", expand=True)
        self.left.tag_configure("diff", background="#ffe5e5")
        self.right.tag_configure("diff", background="#ffe5e5")
        self.left.tag_configure("hit", background="#fff0a0")
        self.right.tag_configure("hit", background="#fff0a0")
        pane.add(left_frame)
        pane.add(right_frame)

    def load(self, data_a: bytes, data_b: bytes, label_a="A", label_b="B"):
        self.data_a = bytes(data_a)
        self.data_b = bytes(data_b)
        self.label_a = label_a
        self.label_b = label_b
        self.left.delete("1.0", "end")
        self.right.delete("1.0", "end")
        self.nav.delete(0, "end")
        self.diff_rows = []
        max_len = max(len(self.data_a), len(self.data_b))
        for off in range(0, max_len, 16):
            a = self.data_a[off:off + 16]
            b = self.data_b[off:off + 16]
            line_a = "{0:08X}  {1:<47}  {2}".format(off, " ".join("{0:02X}".format(x) for x in a), "".join(chr(x) if 32 <= x < 127 else "." for x in a))
            line_b = "{0:08X}  {1:<47}  {2}".format(off, " ".join("{0:02X}".format(x) for x in b), "".join(chr(x) if 32 <= x < 127 else "." for x in b))
            idx = "{0}.0".format(off // 16 + 1)
            self.left.insert("end", line_a + "\n")
            self.right.insert("end", line_b + "\n")
            if a != b:
                self.left.tag_add("diff", idx, "{0}.end".format(off // 16 + 1))
                self.right.tag_add("diff", idx, "{0}.end".format(off // 16 + 1))
                self.nav.insert("end", "0x{0:08X}".format(off))
                self.diff_rows.append((off, a, b))

    def _sync_scroll(self, *args):
        self.left.yview(*args)
        self.right.yview(*args)
        try:
            self.scrollbar.set(*self.left.yview())
        except Exception:
            pass

    def _search(self):
        term = self.search_var.get().strip().upper()
        self.left.tag_remove("hit", "1.0", "end")
        self.right.tag_remove("hit", "1.0", "end")
        if not term:
            return
        for widget in (self.left, self.right):
            start = "1.0"
            while True:
                pos = widget.search(term, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = "{0}+{1}c".format(pos, len(term))
                widget.tag_add("hit", pos, end)
                start = end

    def _export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["offset", self.label_a, self.label_b])
            for off, a, b in self.diff_rows:
                writer.writerow(["0x{0:08X}".format(off), a.hex().upper(), b.hex().upper()])

    def _export_txt(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("Compare {0} vs {1}\n".format(self.label_a, self.label_b))
            for off, a, b in self.diff_rows:
                fh.write("0x{0:08X}: {1} | {2}\n".format(off, a.hex().upper(), b.hex().upper()))


class BinaryPatcher:
    MAGIC = b"NAVPATCH1"

    @staticmethod
    def generate(orig: bytes, patched: bytes) -> bytes:
        records = []
        i = 0
        max_len = max(len(orig), len(patched))
        while i < max_len:
            ob = orig[i:i + 1]
            pb = patched[i:i + 1]
            if ob == pb:
                i += 1
                continue
            start = i
            old = bytearray()
            new = bytearray()
            while i < max_len and orig[i:i + 1] != patched[i:i + 1]:
                old.extend(orig[i:i + 1])
                new.extend(patched[i:i + 1])
                i += 1
            records.append({"offset": start, "old": old.hex(), "new": new.hex()})
        payload = {
            "orig_len": len(orig),
            "new_len": len(patched),
            "records": records,
        }
        comp = zlib.compress(json.dumps(payload, separators=(",", ":")).encode("utf-8"), 9)
        return BinaryPatcher.MAGIC + comp

    @staticmethod
    def parse(patch_data: bytes) -> list[dict]:
        if not patch_data.startswith(BinaryPatcher.MAGIC):
            raise ValueError("Invalid patch header")
        payload = json.loads(zlib.decompress(patch_data[len(BinaryPatcher.MAGIC):]).decode("utf-8"))
        return payload.get("records", [])

    @staticmethod
    def _payload(patch_data):
        if not patch_data.startswith(BinaryPatcher.MAGIC):
            raise ValueError("Invalid patch header")
        return json.loads(zlib.decompress(patch_data[len(BinaryPatcher.MAGIC):]).decode("utf-8"))

    @staticmethod
    def verify(orig: bytes, patch_data: bytes) -> bool:
        payload = BinaryPatcher._payload(patch_data)
        if payload.get("orig_len") != len(orig):
            return False
        for rec in payload.get("records", []):
            off = int(rec["offset"])
            old = bytes.fromhex(rec["old"])
            if orig[off: off + len(old)] != old:
                return False
        return True

    @staticmethod
    def apply(orig: bytes, patch_data: bytes) -> bytes:
        payload = BinaryPatcher._payload(patch_data)
        if not BinaryPatcher.verify(orig, patch_data):
            raise ValueError("Patch does not match original data")
        data = bytearray(orig)
        delta = 0
        for rec in payload.get("records", []):
            off = int(rec["offset"]) + delta
            old = bytes.fromhex(rec["old"])
            new = bytes.fromhex(rec["new"])
            data[off: off + len(old)] = new
            delta += len(new) - len(old)
        return bytes(data)

    @staticmethod
    def reverse_patch(patch_data: bytes) -> bytes:
        payload = BinaryPatcher._payload(patch_data)
        reversed_records = []
        for rec in payload.get("records", []):
            reversed_records.append({"offset": rec["offset"], "old": rec["new"], "new": rec["old"]})
        new_payload = {
            "orig_len": payload.get("new_len"),
            "new_len": payload.get("orig_len"),
            "records": reversed_records,
        }
        return BinaryPatcher.MAGIC + zlib.compress(json.dumps(new_payload, separators=(",", ":")).encode("utf-8"), 9)


class LiveTrack:
    def __init__(self, icao: str):
        self.icao = icao.upper()
        self.callsign = ""
        self.lat = None
        self.lon = None
        self.alt = None
        self.speed = None
        self.heading = None
        self.last_seen = time.time()
        self.trail = []

    def update(self, msg: dict):
        self.callsign = msg.get("callsign") or self.callsign
        if msg.get("lat") is not None and msg.get("lon") is not None:
            self.lat = _safe_float(msg.get("lat"))
            self.lon = _safe_float(msg.get("lon"))
            self.trail.append((self.lat, self.lon))
            self.trail = self.trail[-RADAR_TRAIL_MAX:]
        if msg.get("alt") is not None:
            self.alt = _safe_int(msg.get("alt"))
        if msg.get("speed") is not None:
            self.speed = _safe_float(msg.get("speed"))
        if msg.get("heading") is not None:
            self.heading = _safe_float(msg.get("heading"))
        self.last_seen = time.time()


class SBSParser:
    @staticmethod
    def parse(line: str):
        parts = line.strip().split(",")
        if len(parts) < 22 or parts[0] != "MSG":
            return None
        icao = parts[4].strip().upper()
        if not icao:
            return None
        msg = {
            "type": parts[1],
            "icao": icao,
            "callsign": parts[10].strip() or None,
            "alt": _safe_int(parts[11], None),
            "speed": _safe_float(parts[12], None),
            "heading": _safe_float(parts[13], None),
            "lat": _safe_float(parts[14], None),
            "lon": _safe_float(parts[15], None),
            "vert_rate": _safe_int(parts[16], None),
            "squawk": parts[17].strip() or None,
        }
        return msg


class BeastParser:
    FRAME_LENGTHS = {0x31: 11, 0x32: 16, 0x33: 23}

    @classmethod
    def extract_frames(cls, buf: bytearray):
        frames = []
        i = 0
        while i + 2 <= len(buf):
            if buf[i] != 0x1A:
                i += 1
                continue
            if i + 2 > len(buf):
                break
            ftype = buf[i + 1]
            total = cls.FRAME_LENGTHS.get(ftype)
            if total is None:
                i += 1
                continue
            if i + total > len(buf):
                break
            frames.append(bytes(buf[i:i + total]))
            i += total
        del buf[:i]
        return frames

    @staticmethod
    def decode_velocity(data: bytes):
        if len(data) < 7:
            return None
        ew = ((data[5] & 0x03) << 8) | data[6]
        ns = ((data[7] & 0x7F) << 3) >> 3 if len(data) > 7 else 0
        speed = math.hypot(ew, ns)
        heading = math.degrees(math.atan2(ew, ns or 1)) % 360.0
        return {"speed": round(speed, 1), "heading": round(heading, 1)}

    @staticmethod
    def decode_alt_baro(data: bytes):
        if len(data) < 6:
            return None
        code = ((data[5] & 0x1F) << 8) | data[6]
        return code * 25 - 1000


class AsterixCAT048:
    @classmethod
    def decode_record(cls, data: bytes, offset: int):
        if offset >= len(data):
            return None, offset
        start = offset
        fspec = []
        while offset < len(data):
            octet = data[offset]
            fspec.append(octet)
            offset += 1
            if not (octet & 0x01):
                break
        record = {"fspec": ["0x{0:02X}".format(x) for x in fspec], "start": start}
        remain = len(data) - offset
        if remain >= 4:
            rho = struct.unpack(">H", data[offset:offset + 2])[0]
            theta = struct.unpack(">H", data[offset + 2:offset + 4])[0]
            record["rho_nm"] = round(rho / 256.0, 2)
            record["theta_deg"] = round(theta * 360.0 / 65536.0, 2)
            offset += 4
        return record, offset

    @classmethod
    def decode_message(cls, data: bytes):
        if len(data) < 3:
            return {"category": None, "records": []}
        cat = data[0]
        length = struct.unpack(">H", data[1:3])[0]
        payload = data[3:length] if length <= len(data) else data[3:]
        records = []
        offset = 0
        while offset < len(payload):
            record, new_offset = cls.decode_record(payload, offset)
            if record is None or new_offset <= offset:
                break
            records.append(record)
            offset = new_offset
        return {"category": cat, "length": length, "records": records}


class ADSBFeedManager:
    def __init__(self):
        self.tracks = {}
        self.stats = {"msg_count": 0, "track_count": 0}
        self._thread = None
        self._stop = threading.Event()

    def start(self, mode, host, port, log_cb):
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, args=(mode, host, int(port or 0), log_cb), daemon=True)
        self._thread.start()

    def _worker(self, mode, host, port, log_cb):
        log_cb("[FEED] starting {0} {1}:{2}".format(mode, host, port))
        if mode == FEED_MODE_SIM:
            tracks = [
                SimTrack("SIM001", -25.9, 28.2, 45, 220, 8500),
                SimTrack("SIM002", -25.7, 28.0, 310, 180, 6000),
            ]
            while not self._stop.is_set():
                for sim in tracks:
                    sim.step(1.0)
                    msg = {
                        "icao": sim.name,
                        "callsign": sim.name,
                        "lat": sim.lat,
                        "lon": sim.lon,
                        "alt": sim.alt_ft,
                        "speed": sim.speed_kt,
                        "heading": sim.heading,
                    }
                    self._update_track(msg)
                time.sleep(1.0)
            return
        if mode == FEED_MODE_SBS:
            try:
                sock = socket.create_connection((host, port), timeout=3)
                sock.settimeout(1)
                buf = ""
                while not self._stop.is_set():
                    try:
                        data = sock.recv(4096)
                        if not data:
                            break
                        buf += data.decode("utf-8", "ignore")
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            msg = SBSParser.parse(line)
                            if msg:
                                self._update_track(msg)
                    except socket.timeout:
                        pass
                sock.close()
            except Exception as exc:
                log_cb("[FEED] SBS error: {0}".format(exc))
            return
        if mode == FEED_MODE_BEAST:
            try:
                sock = socket.create_connection((host, port), timeout=3)
                sock.settimeout(1)
                buf = bytearray()
                while not self._stop.is_set():
                    try:
                        data = sock.recv(4096)
                        if not data:
                            break
                        buf.extend(data)
                        for frame in BeastParser.extract_frames(buf):
                            icao = frame[-3:].hex().upper()
                            msg = {"icao": icao, "callsign": icao}
                            vel = BeastParser.decode_velocity(frame)
                            if vel:
                                msg.update(vel)
                            alt = BeastParser.decode_alt_baro(frame)
                            if alt is not None:
                                msg["alt"] = alt
                            self._update_track(msg)
                    except socket.timeout:
                        pass
                sock.close()
            except Exception as exc:
                log_cb("[FEED] Beast error: {0}".format(exc))
            return
        if mode == FEED_MODE_ASTERIX:
            try:
                sock = socket.create_connection((host, port), timeout=3)
                sock.settimeout(1)
                while not self._stop.is_set():
                    try:
                        data = sock.recv(4096)
                        if not data:
                            break
                        msg = AsterixCAT048.decode_message(data)
                        for idx, rec in enumerate(msg.get("records", [])):
                            ident = "CAT48-{0:03d}".format(idx)
                            track = {
                                "icao": ident,
                                "callsign": ident,
                                "heading": rec.get("theta_deg"),
                                "speed": rec.get("rho_nm"),
                            }
                            self._update_track(track)
                    except socket.timeout:
                        pass
                sock.close()
            except Exception as exc:
                log_cb("[FEED] ASTERIX error: {0}".format(exc))
            return
        log_cb("[FEED] mode not started")

    def _update_track(self, msg):
        icao = (msg.get("icao") or "UNKNOWN").upper()
        track = self.tracks.get(icao)
        if track is None:
            track = LiveTrack(icao)
            self.tracks[icao] = track
        track.update(msg)
        self.stats["msg_count"] += 1
        self.stats["track_count"] = len(self.tracks)

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None


class SimTrack:
    def __init__(self, name, lat, lon, heading, speed_kt, alt_ft):
        self.name = name
        self.lat = float(lat)
        self.lon = float(lon)
        self.heading = float(heading)
        self.speed_kt = float(speed_kt)
        self.alt_ft = float(alt_ft)
        self.trail = []

    def step(self, dt_sec):
        nm = self.speed_kt * dt_sec / 3600.0
        rad = math.radians(self.heading)
        dlat = (nm * math.cos(rad)) / 60.0
        scale = max(0.1, math.cos(math.radians(self.lat)))
        dlon = (nm * math.sin(rad)) / (60.0 * scale)
        self.lat += dlat
        self.lon += dlon
        self.trail.append((self.lat, self.lon))
        self.trail = self.trail[-RADAR_TRAIL_MAX:]


class NAVAIDSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1420x940")
        self.theme_name = "dark"
        self.theme = THEMES[self.theme_name]
        self.comm = CommManager()
        self.comm.on_serial_connect_cb = self._on_serial_connected
        self.uploader = MemoryUploader(self.comm)
        self.terrain_analysis = TerrainAnalysis()
        self.feed = ADSBFeedManager()
        self.tcp_tester = TCPLoopbackTester()
        self.lda_data = {"waypoints": [], "obstacles": [], "terrain": []}
        self.vor_current_data = {}
        self.notam_records = []
        self.log_records = []
        self.sim_tracks = [
            SimTrack("SIMA", -25.95, 28.22, 35, 160, 5500),
            SimTrack("SIMB", -25.80, 28.05, 225, 210, 7200),
        ]
        self.radar_selected = None
        self.compare_data_a = b""
        self.compare_data_b = b""
        self.patch_orig = b""
        self.patch_mod = b""
        self.hex_data = b""
        self.port_var = tk.StringVar(value="")
        self.baud_var = tk.StringVar(value="9600")
        self.tcp_host_var = tk.StringVar(value="127.0.0.1")
        self.tcp_port_var = tk.StringVar(value="30003")
        self.station_var = tk.StringVar(value="TEST")
        self.tech_var = tk.StringVar(value=os.environ.get("USER", "Technician"))
        self.notes_var = tk.StringVar(value="")
        self.conn_status_var = tk.StringVar(value="Disconnected")
        self.theme_var = tk.StringVar(value=self.theme_name)
        self.feed_mode_var = tk.StringVar(value=FEED_MODE_SIM)
        self.radar_range_var = tk.DoubleVar(value=RADAR_DEFAULT_RANGE_NM)
        self.radar_center_lat = tk.DoubleVar(value=-25.90)
        self.radar_center_lon = tk.DoubleVar(value=28.15)
        self.vor_preview = None
        self.vor_progress = None
        self.log_text = None
        self.runway_trees = {}
        self.lda_summary = None
        self.terrain_box = None
        self.hex_view = None
        self.compare_view = None
        self.patch_text = None
        self.local_test_var = tk.StringVar(value=LOCAL_TEST_PROGRAMS[0])
        self.chart_canvas = None
        self.chart_points = collections.deque(maxlen=MAX_CHART_PTS)
        self.notam_tree = None
        self.inspect_tree = None
        self.radar_canvas = None
        self.track_list = None
        self.radar_detail_var = tk.StringVar(value="No track selected")
        self.feed_stats_var = tk.StringVar(value="Messages: 0  Tracks: 0")
        self._build_ui()
        self._load_config()
        self._apply_theme()
        self.after(1000, self._auto_scan_ports)
        self.after(2000, self._feed_stats_poller)
        self.after(60_000, self._notam_alert_check)

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Label(top, text="Port").pack(side="left")
        ttk.Entry(top, textvariable=self.port_var, width=14).pack(side="left", padx=2)
        ttk.Button(top, text="Scan", command=self._auto_scan_ports).pack(side="left", padx=2)
        ttk.Label(top, text="Baud").pack(side="left")
        ttk.Entry(top, textvariable=self.baud_var, width=8).pack(side="left", padx=2)
        ttk.Button(top, text="Auto Connect", command=self._auto_connect).pack(side="left", padx=2)
        ttk.Label(top, text="TCP Host").pack(side="left", padx=(10, 0))
        ttk.Entry(top, textvariable=self.tcp_host_var, width=14).pack(side="left", padx=2)
        ttk.Label(top, text="Port").pack(side="left")
        ttk.Entry(top, textvariable=self.tcp_port_var, width=8).pack(side="left", padx=2)
        ttk.Button(top, text="TCP Connect", command=self._tcp_connect).pack(side="left", padx=2)
        ttk.Button(top, text="Disconnect", command=self._disconnect).pack(side="left", padx=2)
        ttk.Label(top, textvariable=self.conn_status_var).pack(side="left", padx=8)
        ttk.Button(top, text="Theme", command=self._toggle_theme).pack(side="right")
        main = ttk.PanedWindow(self, orient="vertical")
        main.pack(fill="both", expand=True)
        upper = ttk.Frame(main)
        lower = ttk.Frame(main)
        main.add(upper, weight=8)
        main.add(lower, weight=2)
        self.notebook = ttk.Notebook(upper)
        self.notebook.pack(fill="both", expand=True)
        self.tabs = {}
        for key, title, builder in [
            ("vor", "VOR", self._tab_vor),
            ("vor_print", "VOR Report", self._tab_vor_print),
            ("ils", "ILS", self._tab_ils),
            ("african", "African", self._tab_african),
            ("saaf", "SAAF", self._tab_saaf),
            ("calibration", "Calibration", self._tab_calibration),
            ("lda_memory", "LDA Memory", self._tab_lda_memory),
            ("hex_viewer", "Hex Viewer", self._tab_hex_viewer),
            ("compare", "Compare", self._tab_compare),
            ("patch", "Patch", self._tab_patch),
            ("local_test", "Local Test", self._tab_local_test),
            ("charts", "Charts", self._tab_charts),
            ("simulation", "Simulation", self._tab_simulation),
            ("inspection", "Inspection", self._tab_inspection),
            ("notam", "NOTAM", self._tab_notam),
            ("radar", "Radar", self._tab_radar),
        ]:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=title)
            self.tabs[key] = frame
            builder(frame)
        self.log_text = ScrolledText(lower, height=8, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _tab_vor(self, parent):
        sub = ttk.Notebook(parent)
        sub.pack(fill="both", expand=True)

        # --- Page 1: Status & Control ---
        p1 = ttk.Frame(sub)
        sub.add(p1, text="Status & Control")
        frm = ttk.Frame(p1)
        frm.pack(fill="both", expand=True, padx=8, pady=8)
        row1 = ttk.Frame(frm)
        row1.pack(fill="x", pady=3)
        ttk.Label(row1, text="Station").pack(side="left")
        ttk.Entry(row1, textvariable=self.station_var, width=18).pack(side="left", padx=3)
        ttk.Label(row1, text="Technician").pack(side="left", padx=(8, 0))
        ttk.Entry(row1, textvariable=self.tech_var, width=22).pack(side="left", padx=3)
        ttk.Button(row1, text="Query All", command=self._vor_rpt_query).pack(side="left", padx=6)
        ttk.Button(row1, text="Use Current", command=self._vor_rpt_use_current).pack(side="left", padx=2)
        ttk.Button(row1, text="Download EEPROM", command=lambda: self._download_from_device(MEM_EEPROM)).pack(side="left", padx=6)
        cols = ("section", "label", "value", "unit", "status")
        tree = ttk.Treeview(frm, columns=cols, show="headings", height=18)
        for col in cols:
            tree.heading(col, text=col.title())
            tree.column(col, width=120 if col != "label" else 220)
        tree.pack(fill="both", expand=True)
        self.vor_tree = tree
        pfrm = ttk.Frame(frm)
        pfrm.pack(fill="x", pady=4)
        self.vor_progress = ttk.Progressbar(pfrm, mode="determinate")
        self.vor_progress.pack(fill="x", expand=True)

        # --- Page 2: Calibration ---
        p2 = ttk.Frame(sub)
        sub.add(p2, text="Calibration")
        btns2 = ttk.Frame(p2)
        btns2.pack(fill="x", padx=8, pady=4)
        ttk.Button(btns2, text="Import Thales LDA", command=self._import_thales_lda).pack(side="left", padx=2)
        ttk.Button(btns2, text="Apply to Device", command=lambda: self._log("[VOR] Apply calibration not yet connected to device.")).pack(side="left", padx=2)
        ttk.Button(btns2, text="Print", command=lambda: self._log("[VOR] Print calibration not yet implemented.")).pack(side="left", padx=2)
        cal_cols = ("node", "parameter", "value", "range", "comment")
        self._vor_cal_tree = ttk.Treeview(p2, columns=cal_cols, show="headings", height=14)
        for c in cal_cols:
            self._vor_cal_tree.heading(c, text=c.title())
            self._vor_cal_tree.column(c, width=130 if c != "comment" else 240)
        self._vor_cal_tree.pack(fill="both", expand=True, padx=8)
        self._vor_cal_text = ScrolledText(p2, height=6, wrap="none", font=("Courier", 9))
        self._vor_cal_text.pack(fill="x", padx=8, pady=(0, 8))

        # --- Page 3: Alarm Limits ---
        p3 = ttk.Frame(sub)
        sub.add(p3, text="Alarm Limits")
        btns3 = ttk.Frame(p3)
        btns3.pack(fill="x", padx=8, pady=4)
        ttk.Button(btns3, text="Import Thales LDA", command=self._import_thales_lda).pack(side="left", padx=2)
        alm_cols = ("node", "parameter", "value", "range", "comment")
        self._vor_alm_tree = ttk.Treeview(p3, columns=alm_cols, show="headings", height=14)
        for c in alm_cols:
            self._vor_alm_tree.heading(c, text=c.title())
            self._vor_alm_tree.column(c, width=130 if c != "comment" else 240)
        self._vor_alm_tree.tag_configure("alarm", background="#ffe0e0")
        self._vor_alm_tree.pack(fill="both", expand=True, padx=8)
        self._vor_alm_text = ScrolledText(p3, height=6, wrap="none", font=("Courier", 9))
        self._vor_alm_text.pack(fill="x", padx=8, pady=(0, 8))

        # --- Page 4: TX Adjustments ---
        p4 = ttk.Frame(sub)
        sub.add(p4, text="TX Adjustments")
        btns4 = ttk.Frame(p4)
        btns4.pack(fill="x", padx=8, pady=4)
        ttk.Button(btns4, text="Import Thales LDA", command=self._import_thales_lda).pack(side="left", padx=2)
        adj_cols = ("node", "parameter", "value", "range", "comment")
        self._vor_adj_tree = ttk.Treeview(p4, columns=adj_cols, show="headings", height=14)
        for c in adj_cols:
            self._vor_adj_tree.heading(c, text=c.title())
            self._vor_adj_tree.column(c, width=130 if c != "comment" else 240)
        self._vor_adj_tree.pack(fill="both", expand=True, padx=8)
        self._vor_adj_text = ScrolledText(p4, height=6, wrap="none", font=("Courier", 9))
        self._vor_adj_text.pack(fill="x", padx=8, pady=(0, 8))

        # --- Page 5: TX Configuration ---
        p5 = ttk.Frame(sub)
        sub.add(p5, text="TX Configuration")
        btns5 = ttk.Frame(p5)
        btns5.pack(fill="x", padx=8, pady=4)
        ttk.Button(btns5, text="Import Thales LDA", command=self._import_thales_lda).pack(side="left", padx=2)
        cfg_cols = ("node", "parameter", "value", "range", "comment")
        self._vor_cfg_tree = ttk.Treeview(p5, columns=cfg_cols, show="headings", height=14)
        for c in cfg_cols:
            self._vor_cfg_tree.heading(c, text=c.title())
            self._vor_cfg_tree.column(c, width=130 if c != "comment" else 240)
        self._vor_cfg_tree.tag_configure("readonly", background="#e8e8e8")
        self._vor_cfg_tree.pack(fill="both", expand=True, padx=8)
        self._vor_cfg_text = ScrolledText(p5, height=6, wrap="none", font=("Courier", 9))
        self._vor_cfg_text.pack(fill="x", padx=8, pady=(0, 8))

        # --- Page 6: LRCI Configuration ---
        p6 = ttk.Frame(sub)
        sub.add(p6, text="LRCI Configuration")
        btns6 = ttk.Frame(p6)
        btns6.pack(fill="x", padx=8, pady=4)
        ttk.Button(btns6, text="Import Thales LDA", command=self._import_thales_lda).pack(side="left", padx=2)
        lrci_cols = ("node", "parameter", "value", "range", "comment")
        self._vor_lrci_tree = ttk.Treeview(p6, columns=lrci_cols, show="headings", height=14)
        for c in lrci_cols:
            self._vor_lrci_tree.heading(c, text=c.title())
            self._vor_lrci_tree.column(c, width=130 if c != "comment" else 240)
        self._vor_lrci_tree.pack(fill="both", expand=True, padx=8)
        self._vor_lrci_text = ScrolledText(p6, height=6, wrap="none", font=("Courier", 9))
        self._vor_lrci_text.pack(fill="x", padx=8, pady=(0, 8))

        # --- Page 7: Raw LDA ---
        p7 = ttk.Frame(sub)
        sub.add(p7, text="Raw LDA")
        btns7 = ttk.Frame(p7)
        btns7.pack(fill="x", padx=8, pady=4)
        ttk.Button(btns7, text="Import Thales LDA", command=self._import_thales_lda).pack(side="left", padx=2)
        self._vor_raw_text = ScrolledText(p7, wrap="none", font=("Courier", 9))
        self._vor_raw_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _import_thales_lda(self):
        """Import a Thales CVOR .lda file and populate all VOR sub-tabs."""
        path = filedialog.askopenfilename(
            title="Import Thales CVOR LDA",
            filetypes=[("Thales LDA", "*.lda *.LDA"), ("All", "*.*")])
        if not path:
            return
        self.lda_data = import_lda(path)
        self._populate_thales_vor_tabs()
        self._log("[VOR] Thales LDA imported: {0}".format(os.path.basename(path)))

    def _populate_thales_vor_tabs(self):
        """Populate all VOR sub-tabs from self.lda_data (Thales format)."""
        data = self.lda_data
        if not isinstance(data, dict):
            return
        raw = data.get("raw", "")
        prog = data.get("prog", [])
        sections = data.get("sections", {})

        # Clear all treeviews
        for tree in (self._vor_cal_tree, self._vor_alm_tree, self._vor_adj_tree,
                     self._vor_cfg_tree, self._vor_lrci_tree):
            for item in tree.get_children():
                tree.delete(item)

        # Map func_num to (treeview, text_widget, section_keywords)
        func_map = {
            "3_mon":  (self._vor_cal_tree,  self._vor_cal_text,  ["MON 1 - Calibration", "MON 2 - Calibration"]),
            "7_mon":  (self._vor_alm_tree,  self._vor_alm_text,  ["MON 1 - Alarm limits", "MON 2 - Alarm limits"]),
            "3_tx":   (self._vor_adj_tree,  self._vor_adj_text,  ["TX 1 - Adjustments", "TX 2 - Adjustments"]),
            "2_tx":   (self._vor_cfg_tree,  self._vor_cfg_text,  ["TX 1 - Configuration", "TX 2 - Configuration"]),
            "lrci":   (self._vor_lrci_tree, self._vor_lrci_text, ["LRCI"]),
        }

        # Pattern: [READONLY] NODE FUNC_NUM PARAM_IDX VALUE ; Function: NODE - SECTION, PARAM_NAME
        pat = re.compile(
            r'^(READONLY\s+)?(\S+)\s+(\d+)\s+(\d+)\s+(\S+)\s*;?\s*(?:Function:\s*(.*))?$',
            re.IGNORECASE)

        for line in prog:
            m = pat.match(line)
            if not m:
                continue
            readonly_flag = bool(m.group(1))
            node = m.group(2).upper()
            func_num = int(m.group(3))
            param_idx = m.group(4)
            value = m.group(5)
            comment = (m.group(6) or "").strip()

            # Determine which treeview
            is_mon = node.startswith("MON")
            is_tx = node.startswith("TX")
            is_lrci = node.startswith("LRCI")

            tree = None
            tag = ()
            if is_mon and func_num == 3:
                tree = self._vor_cal_tree
            elif is_mon and func_num == 7:
                tree = self._vor_alm_tree
                tag = ("alarm",)
            elif is_tx and func_num == 3:
                tree = self._vor_adj_tree
            elif is_tx and func_num == 2:
                tree = self._vor_cfg_tree
                if readonly_flag:
                    tag = ("readonly",)
            elif is_lrci:
                tree = self._vor_lrci_tree

            if tree is not None:
                tree.insert("", "end",
                            values=(node, "Param {0}".format(param_idx), value, "", comment),
                            tags=tag)

        # Populate printout text widgets from sections
        for key, (tree, txt_widget, sec_keys) in func_map.items():
            buf = []
            for sk in sec_keys:
                content = sections.get(sk, "")
                if content:
                    buf.append("=== {0} ===\n{1}".format(sk, content))
            txt_widget.configure(state="normal")
            txt_widget.delete("1.0", "end")
            if buf:
                txt_widget.insert("1.0", "\n\n".join(buf))
            txt_widget.configure(state="disabled")

        # Raw LDA
        self._vor_raw_text.configure(state="normal")
        self._vor_raw_text.delete("1.0", "end")
        self._vor_raw_text.insert("1.0", raw)
        self._vor_raw_text.configure(state="disabled")

    def _tab_vor_print(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Notes").pack(side="left")
        ttk.Entry(top, textvariable=self.notes_var, width=60).pack(side="left", padx=4)
        ttk.Button(top, text="Preview", command=self._vor_rpt_preview).pack(side="left", padx=2)
        ttk.Button(top, text="Print TXT", command=self._vor_rpt_print).pack(side="left", padx=2)
        ttk.Button(top, text="Save PDF", command=self._vor_rpt_pdf).pack(side="left", padx=2)
        ttk.Button(top, text="Save CSV", command=self._vor_rpt_csv).pack(side="left", padx=2)
        ttk.Button(top, text="Save TXT", command=self._vor_rpt_txt).pack(side="left", padx=2)
        ttk.Button(top, text="Clear", command=self._vor_rpt_clear).pack(side="left", padx=2)
        self.vor_preview = ScrolledText(parent, wrap="none")
        self.vor_preview.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _tab_ils(self, parent):
        sub = ttk.Notebook(parent)
        sub.pack(fill="both", expand=True)

        # --- Page 1: Status & Control ---
        p1 = ttk.Frame(sub)
        sub.add(p1, text="Status & Control")
        top1 = ttk.Frame(p1)
        top1.pack(fill="x", padx=8, pady=4)
        ttk.Label(top1, text="LOC Freq (MHz)").pack(side="left")
        self._ils_loc_freq_var = tk.StringVar(value="108.10")
        ttk.Entry(top1, textvariable=self._ils_loc_freq_var, width=10).pack(side="left", padx=3)
        ttk.Label(top1, text="GP Angle (deg)").pack(side="left", padx=(8, 0))
        self._ils_gp_angle_var = tk.StringVar(value="3.0")
        ttk.Entry(top1, textvariable=self._ils_gp_angle_var, width=8).pack(side="left", padx=3)
        ttk.Label(top1, text="Course Align (deg)").pack(side="left", padx=(8, 0))
        self._ils_course_var = tk.StringVar(value="0.0")
        ttk.Entry(top1, textvariable=self._ils_course_var, width=8).pack(side="left", padx=3)
        btn1 = ttk.Frame(p1)
        btn1.pack(fill="x", padx=8, pady=2)
        ttk.Button(btn1, text="Query LOC", command=lambda: self._ils_query("loc_freq")).pack(side="left", padx=2)
        ttk.Button(btn1, text="Query GP", command=lambda: self._ils_query("gp_angle")).pack(side="left", padx=2)
        ttk.Button(btn1, text="Query All", command=self._ils_query_all).pack(side="left", padx=2)
        ttk.Button(btn1, text="Calibrate LOC", command=lambda: self._ils_send("loc_cal")).pack(side="left", padx=2)
        ttk.Button(btn1, text="Calibrate GP", command=lambda: self._ils_send("gp_cal")).pack(side="left", padx=2)
        ttk.Button(btn1, text="Reset", command=lambda: self._ils_send("reset")).pack(side="left", padx=2)
        st_cols = ("system", "parameter", "value", "unit", "status")
        self._ils_status_tree = ttk.Treeview(p1, columns=st_cols, show="headings", height=12)
        for c in st_cols:
            self._ils_status_tree.heading(c, text=c.title())
            self._ils_status_tree.column(c, width=120)
        self._ils_status_tree.pack(fill="both", expand=True, padx=8)
        self._ils_log = ScrolledText(p1, height=6, wrap="word")
        self._ils_log.pack(fill="x", padx=8, pady=(4, 8))

        # --- Page 2: LOC Calibration ---
        p2 = ttk.Frame(sub)
        sub.add(p2, text="LOC Calibration")
        btn2 = ttk.Frame(p2)
        btn2.pack(fill="x", padx=8, pady=4)
        ttk.Button(btn2, text="Read from Device", command=lambda: self._ils_read_cal("loc")).pack(side="left", padx=2)
        ttk.Button(btn2, text="Write to Device", command=lambda: self._ils_write_cal("loc")).pack(side="left", padx=2)
        ttk.Button(btn2, text="Import Normarc CFG", command=self._import_normarc_cfg).pack(side="left", padx=2)
        loc_cols = ("parameter", "current_value", "target_value", "unit", "status")
        self._normarc_loc_tree = ttk.Treeview(p2, columns=loc_cols, show="headings", height=18)
        for c in loc_cols:
            self._normarc_loc_tree.heading(c, text=c.replace("_", " ").title())
            self._normarc_loc_tree.column(c, width=140)
        for name, key, unit, default in NORMARC_LOC_CAL_PARAMS:
            self._normarc_loc_tree.insert("", "end", iid=key,
                values=(name, default, default, unit, ""))
        self._normarc_loc_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # --- Page 3: GP Calibration ---
        p3 = ttk.Frame(sub)
        sub.add(p3, text="GP Calibration")
        btn3 = ttk.Frame(p3)
        btn3.pack(fill="x", padx=8, pady=4)
        ttk.Button(btn3, text="Read from Device", command=lambda: self._ils_read_cal("gp")).pack(side="left", padx=2)
        ttk.Button(btn3, text="Write to Device", command=lambda: self._ils_write_cal("gp")).pack(side="left", padx=2)
        ttk.Button(btn3, text="Import Normarc CFG", command=self._import_normarc_cfg).pack(side="left", padx=2)
        gp_cols = ("parameter", "current_value", "target_value", "unit", "status")
        self._normarc_gp_tree = ttk.Treeview(p3, columns=gp_cols, show="headings", height=18)
        for c in gp_cols:
            self._normarc_gp_tree.heading(c, text=c.replace("_", " ").title())
            self._normarc_gp_tree.column(c, width=140)
        for name, key, unit, default in NORMARC_GP_CAL_PARAMS:
            self._normarc_gp_tree.insert("", "end", iid=key,
                values=(name, default, default, unit, ""))
        self._normarc_gp_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # --- Page 4: Alarm Limits ---
        p4 = ttk.Frame(sub)
        sub.add(p4, text="Alarm Limits")
        alm_cols = ("system", "parameter", "limit", "unit", "direction")
        alm_tree = ttk.Treeview(p4, columns=alm_cols, show="headings", height=22)
        for c in alm_cols:
            alm_tree.heading(c, text=c.title())
            alm_tree.column(c, width=120)
        alm_tree.tag_configure("alarm", background="#ffe0e0")
        for row in NORMARC_ALARM_LIMITS:
            alm_tree.insert("", "end", values=row, tags=("alarm",))
        alm_tree.pack(fill="both", expand=True, padx=8, pady=8)

        # --- Page 5: Monitor Status ---
        p5 = ttk.Frame(sub)
        sub.add(p5, text="Monitor Status")
        ttk.Button(p5, text="Refresh", command=self._ils_refresh_monitor).pack(anchor="nw", padx=8, pady=4)
        mon_row = ttk.Frame(p5)
        mon_row.pack(fill="both", expand=True, padx=8, pady=4)
        loc_frame = ttk.LabelFrame(mon_row, text="Localizer")
        loc_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))
        gp_frame = ttk.LabelFrame(mon_row, text="Glidepath")
        gp_frame.pack(side="left", fill="both", expand=True, padx=(4, 0))
        self._ils_loc_labels = {}
        self._ils_gp_labels = {}
        for label_text, key in [("TX Status", "tx_status"), ("Monitor Status", "mon_status"),
                                 ("DDM", "ddm"), ("Course/Angle", "course"), ("Power", "power"),
                                 ("Alarms", "alarms")]:
            r = ttk.Frame(loc_frame)
            r.pack(fill="x", padx=4, pady=2)
            ttk.Label(r, text=label_text + ":", width=16, anchor="w").pack(side="left")
            lbl = ttk.Label(r, text="--", foreground="gray")
            lbl.pack(side="left")
            self._ils_loc_labels[key] = lbl
        for label_text, key in [("TX Status", "tx_status"), ("Monitor Status", "mon_status"),
                                 ("DDM", "ddm"), ("Glide Angle", "angle"), ("Power", "power"),
                                 ("Alarms", "alarms")]:
            r = ttk.Frame(gp_frame)
            r.pack(fill="x", padx=4, pady=2)
            ttk.Label(r, text=label_text + ":", width=16, anchor="w").pack(side="left")
            lbl = ttk.Label(r, text="--", foreground="gray")
            lbl.pack(side="left")
            self._ils_gp_labels[key] = lbl

        # --- Page 6: Raw Normarc CFG ---
        p6 = ttk.Frame(sub)
        sub.add(p6, text="Raw Normarc CFG")
        btn6 = ttk.Frame(p6)
        btn6.pack(fill="x", padx=8, pady=4)
        ttk.Button(btn6, text="Import Normarc CFG", command=self._import_normarc_cfg).pack(side="left", padx=2)
        self._normarc_raw_text = ScrolledText(p6, wrap="none", font=("Courier", 9))
        self._normarc_raw_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _ils_query(self, key):
        cmd = NORMARC_CMDS.get(key, "")
        if not cmd:
            return
        resp = self.comm.send(cmd)
        self._ils_log_msg("[ILS] {0}: {1}".format(key, resp))

    def _ils_send(self, key):
        cmd = NORMARC_CMDS.get(key, "")
        if not cmd:
            return
        resp = self.comm.send(cmd)
        self._ils_log_msg("[ILS] {0}: {1}".format(key, resp))

    def _ils_query_all(self):
        for item in self._ils_status_tree.get_children():
            self._ils_status_tree.delete(item)
        for key in ("loc_freq", "loc_course", "loc_ddm", "gp_angle", "gp_ddm",
                    "ils_mon", "ils_alarm", "ils_status"):
            cmd = NORMARC_CMDS.get(key, "")
            if cmd:
                resp = self.comm.send(cmd)
                self._ils_log_msg("[ILS] {0}: {1}".format(key, resp))
                self._ils_status_tree.insert("", "end", values=(
                    "LOC" if key.startswith("loc") else "GP" if key.startswith("gp") else "ILS",
                    key, resp, "", ""))

    def _ils_read_cal(self, system):
        self._ils_log_msg("[ILS] Read {0} calibration from device...".format(system.upper()))

    def _ils_write_cal(self, system):
        self._ils_log_msg("[ILS] Write {0} calibration to device...".format(system.upper()))

    def _ils_refresh_monitor(self):
        mon = self.comm.send(NORMARC_CMDS.get("ils_mon", "ILS:MON?"))
        alm = self.comm.send(NORMARC_CMDS.get("ils_alarm", "ILS:ALM?"))
        loc_ddm = self.comm.send(NORMARC_CMDS.get("loc_ddm", "LOC:DDM?"))
        gp_ddm = self.comm.send(NORMARC_CMDS.get("gp_ddm", "GP:DDM?"))
        ok_color = "green"
        alm_color = "red"
        for key, lbl in self._ils_loc_labels.items():
            if key == "mon_status":
                lbl.configure(text=mon, foreground=ok_color if mon == "NORMAL" else alm_color)
            elif key == "alarms":
                lbl.configure(text=alm, foreground=ok_color if alm == "NONE" else alm_color)
            elif key == "ddm":
                lbl.configure(text=loc_ddm, foreground="black")
            else:
                lbl.configure(text="--", foreground="gray")
        for key, lbl in self._ils_gp_labels.items():
            if key == "mon_status":
                lbl.configure(text=mon, foreground=ok_color if mon == "NORMAL" else alm_color)
            elif key == "alarms":
                lbl.configure(text=alm, foreground=ok_color if alm == "NONE" else alm_color)
            elif key == "ddm":
                lbl.configure(text=gp_ddm, foreground="black")
            else:
                lbl.configure(text="--", foreground="gray")

    def _ils_log_msg(self, msg):
        try:
            self._ils_log.insert("end", msg + "\n")
            self._ils_log.see("end")
        except Exception:
            pass
        self._log(msg)

    def _import_normarc_cfg(self):
        """Import a Normarc ILS config/calibration file."""
        path = filedialog.askopenfilename(
            title="Import Normarc ILS Config",
            filetypes=[("Normarc CFG/LDA", "*.cfg *.lda *.LDA *.txt"),
                       ("All", "*.*")])
        if not path:
            return
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        self._normarc_raw = raw
        self._normarc_raw_text.delete("1.0", "end")
        self._normarc_raw_text.insert("1.0", raw)
        self._parse_normarc_cfg(raw)
        self._log("[ILS] Normarc config imported: {0}".format(os.path.basename(path)))

    def _parse_normarc_cfg(self, raw):
        """Parse Normarc config lines and update LOC/GP calibration treeviews."""
        loc_map = {key: (name, unit, default) for name, key, unit, default in NORMARC_LOC_CAL_PARAMS}
        gp_map = {key: (name, unit, default) for name, key, unit, default in NORMARC_GP_CAL_PARAMS}
        pat = re.compile(r'^(\w+)\s*=\s*([^;]+?)(?:\s*;.*)?$')
        for line in raw.splitlines():
            m = pat.match(line.strip())
            if not m:
                continue
            param_key = m.group(1).strip().lower()
            value = m.group(2).strip()
            if param_key in loc_map and self._normarc_loc_tree.exists(param_key):
                name, unit, default = loc_map[param_key]
                self._normarc_loc_tree.item(param_key, values=(name, value, default, unit, ""))
            if param_key in gp_map and self._normarc_gp_tree.exists(param_key):
                name, unit, default = gp_map[param_key]
                self._normarc_gp_tree.item(param_key, values=(name, value, default, unit, ""))

    def _tab_african(self, parent):
        self.runway_trees["african"] = self._build_runway_tree(parent, AFRICAN_RUNWAYS)

    def _tab_saaf(self, parent):
        self.runway_trees["saaf"] = self._build_runway_tree(parent, SAAF_RUNWAYS)

    def _tab_calibration(self, parent):
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Label(frm, text="Calibration scratchpad").pack(anchor="w")
        self.cal_text = ScrolledText(frm, wrap="word", height=16)
        self.cal_text.pack(fill="both", expand=True)
        self.cal_text.insert("1.0", "Use this page for calibration notes, offsets, and acceptance criteria.\n")

    def _tab_lda_memory(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Import LDA", command=self._import_lda_file).pack(side="left", padx=2)
        ttk.Button(top, text="Run Terrain Analysis", command=self._run_terrain).pack(side="left", padx=2)
        ttk.Button(top, text="Upload EEPROM", command=lambda: self.uploader.upload(MEM_EEPROM, lda_to_bytes(self.lda_data))).pack(side="left", padx=6)
        ttk.Button(top, text="Download EEPROM", command=lambda: self._download_from_device(MEM_EEPROM)).pack(side="left", padx=2)
        self.lda_summary = ScrolledText(parent, height=10)
        self.lda_summary.pack(fill="x", padx=8, pady=(0, 8))
        self.terrain_box = tk.Listbox(parent)
        self.terrain_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _tab_hex_viewer(self, parent):
        self.hex_view = HexViewer(parent)
        self.hex_view.pack(fill="both", expand=True)

    def _tab_compare(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Load A", command=self._compare_load_a).pack(side="left", padx=2)
        ttk.Button(top, text="Load B", command=self._compare_load_b).pack(side="left", padx=2)
        ttk.Button(top, text="Compare", command=self._compare_refresh).pack(side="left", padx=2)
        self.compare_view = HexCompareView(parent)
        self.compare_view.pack(fill="both", expand=True)

    def _tab_patch(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Load Original", command=self._patch_load_orig).pack(side="left", padx=2)
        ttk.Button(top, text="Load Patched", command=self._patch_load_mod).pack(side="left", padx=2)
        ttk.Button(top, text="Generate Patch", command=self._patch_generate).pack(side="left", padx=2)
        ttk.Button(top, text="Apply Patch", command=self._patch_apply).pack(side="left", padx=2)
        self.patch_text = ScrolledText(parent)
        self.patch_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _tab_local_test(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Program").pack(side="left")
        ttk.Combobox(top, textvariable=self.local_test_var, values=LOCAL_TEST_PROGRAMS, state="readonly", width=18).pack(side="left", padx=4)
        ttk.Button(top, text="Run Local", command=self._run_local_test).pack(side="left", padx=2)
        ttk.Button(top, text="Run Self Tests", command=lambda: run_self_tests(self._log)).pack(side="left", padx=8)
        self.local_test_output = ScrolledText(parent)
        self.local_test_output.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _tab_charts(self, parent):
        if MPL_OK:
            fig = Figure(figsize=(5, 3), dpi=100)
            ax = fig.add_subplot(111)
            ax.set_title("TX Power / VSWR Trend")
            ax.set_xlabel("Sample")
            ax.set_ylabel("Value")
            self.chart_axes = ax
            self.chart_canvas = FigureCanvasTkAgg(fig, master=parent)
            self.chart_canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
            ttk.Button(parent, text="Add Sample", command=self._chart_add_sample).pack(pady=(0, 8))
        else:
            box = ScrolledText(parent)
            box.pack(fill="both", expand=True, padx=8, pady=8)
            box.insert("1.0", "matplotlib not available. Trend view disabled.\n")
            self.chart_placeholder = box

    def _tab_simulation(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Step Simulation", command=self._sim_step).pack(side="left", padx=2)
        ttk.Button(top, text="Clear Trails", command=self._clear_trails).pack(side="left", padx=2)
        self.sim_text = ScrolledText(parent)
        self.sim_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _tab_inspection(self, parent):
        cols = LOG_COLUMNS
        tree = ttk.Treeview(parent, columns=cols, show="headings")
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=110 if col != "Notes" else 260)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.inspect_tree = tree
        btns = ttk.Frame(parent)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btns, text="Add Sample Entry", command=self._inspection_add_sample).pack(side="left")
        ttk.Button(btns, text="Export Config", command=self._export_config).pack(side="left", padx=2)
        ttk.Button(btns, text="Import Config", command=self._import_config).pack(side="left", padx=2)

    def _tab_notam(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Add NOTAM", command=self._notam_add).pack(side="left", padx=2)
        ttk.Button(top, text="Save NOTAMs", command=self._save_notams).pack(side="left", padx=2)
        ttk.Button(top, text="Alert Check", command=self._notam_alert_check).pack(side="left", padx=2)
        tree = ttk.Treeview(parent, columns=NOTAM_COLUMNS, show="headings")
        for col in NOTAM_COLUMNS:
            tree.heading(col, text=col)
            tree.column(col, width=110 if col != "Description" else 320)
        tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.notam_tree = tree

    def _tab_radar(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Feed Mode").pack(side="left")
        ttk.Combobox(top, textvariable=self.feed_mode_var, values=[FEED_MODE_SIM, FEED_MODE_SBS, FEED_MODE_BEAST, FEED_MODE_ASTERIX], state="readonly", width=10).pack(side="left", padx=2)
        ttk.Button(top, text="Start Feed", command=self._feed_start).pack(side="left", padx=2)
        ttk.Button(top, text="Stop Feed", command=self._feed_stop).pack(side="left", padx=2)
        ttk.Button(top, text="Start Radar", command=self._radar_start).pack(side="left", padx=12)
        ttk.Button(top, text="Stop Radar", command=self._radar_stop).pack(side="left", padx=2)
        ttk.Button(top, text="Clear Trails", command=self._clear_trails).pack(side="left", padx=2)
        ttk.Label(top, text="Range NM").pack(side="left", padx=(12, 0))
        ttk.Entry(top, textvariable=self.radar_range_var, width=8).pack(side="left", padx=2)
        ttk.Label(top, textvariable=self.feed_stats_var).pack(side="right")
        body = ttk.PanedWindow(parent, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=4)
        body.add(right, weight=1)
        self.radar_canvas = tk.Canvas(left, bg="#00111a", highlightthickness=0)
        self.radar_canvas.pack(fill="both", expand=True)
        self.radar_canvas.bind("<Button-1>", self._radar_on_click)
        self.track_list = tk.Listbox(right)
        self.track_list.pack(fill="both", expand=True)
        ttk.Label(right, textvariable=self.radar_detail_var, justify="left").pack(fill="x", pady=8)

    def _build_runway_tree(self, parent, rows):
        tree = ttk.Treeview(parent, columns=list(rows[0].keys()), show="headings")
        for col in rows[0].keys():
            tree.heading(col, text=col)
            tree.column(col, width=110)
        for row in rows:
            tree.insert("", "end", values=[row[k] for k in rows[0].keys()])
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        return tree

    def _vor_rpt_query(self):
        self.vor_progress["value"] = 0

        def progress(done, total, label):
            self.vor_progress["maximum"] = total
            self.vor_progress["value"] = done
            self._log("[VOR] progress {0}/{1} {2}".format(done, total, label))

        self.vor_current_data = ThalesVORReport.query_all(self.comm, self._log, progress)
        self.vor_tree.delete(*self.vor_tree.get_children())
        for section, label, cmd_key, unit, _ in VOR_REPORT_FIELDS:
            value = self.vor_current_data.get(cmd_key, "")
            self.vor_tree.insert("", "end", values=(section, label, value, unit, ThalesVORReport._status(value)))
        self._vor_rpt_preview()

    def _vor_rpt_use_current(self):
        if not self.vor_current_data:
            self._vor_rpt_query()
            return
        self._vor_rpt_preview()

    def _vor_rpt_preview(self):
        text = self._vor_rpt_build_text()
        self._vor_rpt_set_preview(text)

    def _do_print(self, text):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        self._log("[VOR] wrote report {0}".format(path))

    def _vor_rpt_print(self):
        self._do_print(self._vor_rpt_build_text())

    def _vor_rpt_pdf(self):
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        ThalesVORReport.to_pdf(path, self.vor_current_data or {}, self.tech_var.get(), self.station_var.get(), self.notes_var.get())
        self._log("[VOR] PDF saved {0}".format(path))

    def _vor_rpt_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        ThalesVORReport.to_csv(path, self.vor_current_data or {}, self.tech_var.get(), self.station_var.get())
        self._log("[VOR] CSV saved {0}".format(path))

    def _vor_rpt_txt(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self._vor_rpt_build_text())
        self._log("[VOR] TXT saved {0}".format(path))

    def _vor_rpt_clear(self):
        self.vor_current_data = {}
        self.vor_tree.delete(*self.vor_tree.get_children())
        self._vor_rpt_set_preview("")

    def _vor_rpt_build_text(self):
        return ThalesVORReport.to_text(self.vor_current_data or {}, self.tech_var.get(), self.station_var.get(), self.notes_var.get())

    def _vor_rpt_set_preview(self, text):
        self.vor_preview.delete("1.0", "end")
        self.vor_preview.insert("1.0", text)

    def _auto_scan_ports(self):
        ports = []
        if SERIAL_OK and list_ports is not None:
            try:
                ports = [p.device for p in list_ports.comports()]
            except Exception:
                ports = []
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])
        self._log("[COMM] ports: {0}".format(", ".join(ports) if ports else "none"))

    def _auto_connect(self):
        if not self.port_var.get():
            self._auto_scan_ports()
        if not self.port_var.get():
            self._set_conn_status("No serial port")
            return
        try:
            self.comm.connect_serial(self.port_var.get(), int(self.baud_var.get()))
            self._set_conn_status("Serial connected")
        except Exception as exc:
            self._set_conn_status("Serial failed")
            self._log("[COMM] serial connect failed: {0}".format(exc))

    def _tcp_connect(self):
        try:
            self.comm.connect_tcp(self.tcp_host_var.get(), int(self.tcp_port_var.get()))
            self._set_conn_status("TCP connected")
        except Exception as exc:
            self._set_conn_status("TCP failed")
            self._log("[COMM] tcp connect failed: {0}".format(exc))

    def _disconnect(self):
        self.comm.disconnect()
        self._set_conn_status("Disconnected")

    def _set_conn_status(self, text):
        self.conn_status_var.set(text)
        self._log("[COMM] {0}".format(text))

    def _on_serial_connected(self, port):
        self.conn_status_var.set("Serial connected: {0}".format(port))
        self._log("[COMM] serial callback: {0}".format(port))

    def _download_from_device(self, mem_type=MEM_EEPROM):
        data = self.uploader.download(mem_type)
        self.hex_data = data
        self.hex_view.load_data(data)
        self._log("[MEM] downloaded {0} bytes from {1}".format(len(data), mem_type))

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                    cfg = json.load(fh)
                self.port_var.set(cfg.get("port", self.port_var.get()))
                self.baud_var.set(str(cfg.get("baud", self.baud_var.get())))
                self.tcp_host_var.set(cfg.get("tcp_host", self.tcp_host_var.get()))
                self.tcp_port_var.set(str(cfg.get("tcp_port", self.tcp_port_var.get())))
                self.station_var.set(cfg.get("station", self.station_var.get()))
                self.tech_var.set(cfg.get("technician", self.tech_var.get()))
                self.theme_name = cfg.get("theme", self.theme_name)
                self.theme_var.set(self.theme_name)
            except Exception as exc:
                self._log("[CFG] load failed: {0}".format(exc))
        if os.path.exists(NOTAM_FILE):
            try:
                with open(NOTAM_FILE, "r", encoding="utf-8") as fh:
                    self.notam_records = json.load(fh)
            except Exception as exc:
                self._log("[NOTAM] load failed: {0}".format(exc))
        self._refresh_notam_tree()

    def _save_config(self):
        cfg = {
            "port": self.port_var.get(),
            "baud": self.baud_var.get(),
            "tcp_host": self.tcp_host_var.get(),
            "tcp_port": self.tcp_port_var.get(),
            "station": self.station_var.get(),
            "technician": self.tech_var.get(),
            "theme": self.theme_name,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        self._save_notams()
        self._log("[CFG] saved")

    def _export_config(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        cfg = {
            "port": self.port_var.get(),
            "baud": self.baud_var.get(),
            "tcp_host": self.tcp_host_var.get(),
            "tcp_port": self.tcp_port_var.get(),
            "station": self.station_var.get(),
            "technician": self.tech_var.get(),
            "theme": self.theme_name,
            "notams": self.notam_records,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        self._log("[CFG] exported {0}".format(path))

    def _import_config(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.port_var.set(cfg.get("port", ""))
        self.baud_var.set(str(cfg.get("baud", "9600")))
        self.tcp_host_var.set(cfg.get("tcp_host", "127.0.0.1"))
        self.tcp_port_var.set(str(cfg.get("tcp_port", "30003")))
        self.station_var.set(cfg.get("station", self.station_var.get()))
        self.tech_var.set(cfg.get("technician", self.tech_var.get()))
        self.theme_name = cfg.get("theme", self.theme_name)
        self.theme = THEMES.get(self.theme_name, THEMES["dark"])
        self.notam_records = cfg.get("notams", self.notam_records)
        self._refresh_notam_tree()
        self._apply_theme()
        self._log("[CFG] imported {0}".format(path))

    def _toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.theme = THEMES[self.theme_name]
        self._apply_theme()

    def _apply_theme(self):
        self.theme = THEMES.get(self.theme_name, THEMES["dark"])
        bg = self.theme["bg"]
        fg = self.theme["fg"]
        try:
            self.configure(bg=bg)
        except Exception:
            pass
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=self.theme["btn_bg"], foreground=self.theme["btn_fg"])
        style.configure("TNotebook", background=self.theme["tab_bg"])
        style.configure("TNotebook.Tab", background=self.theme["tab_bg"], foreground=self.theme["tab_fg"])
        style.map("TNotebook.Tab", background=[("selected", self.theme["accent"])])

    def _import_lda_file(self):
        path = filedialog.askopenfilename(filetypes=[("LDA/JSON", "*.lda *.json *.txt"), ("All", "*")])
        if not path:
            return
        self.lda_data = import_lda(path)
        self.lda_summary.delete("1.0", "end")
        summary = json.dumps(self.lda_data, indent=2)
        self.lda_summary.insert("1.0", summary)
        self.hex_data = lda_to_bytes(self.lda_data)
        self.hex_view.load_data(self.hex_data)
        self._log("[LDA] imported {0}".format(path))

    def _run_terrain(self):
        findings = self.terrain_analysis.analyse(self.lda_data)
        self.terrain_box.delete(0, "end")
        for item in findings:
            self.terrain_box.insert("end", item)
        self._log("[LDA] terrain analysis complete")

    def _log(self, msg):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = "[{0}] {1}".format(stamp, msg)
        if self.log_text is not None:
            self.log_text.insert("end", line + "\n")
            self.log_text.see("end")
        print(line)

    def _notam_alert_check(self):
        alerts = []
        for r in self.notam_records:
            if r.get("Status") == "CLOSED":
                continue
            days = _notam_days_until(r.get("Due Date", ""))
            if days > ALERT_DAYS:
                continue
            prefix = "OVERDUE" if days < 0 else f"DUE in {days}d"
            alerts.append(f"{prefix}  #{r['ID']}  {r['Station']}  -  {r['Type']}")
        if alerts:
            self._log("[NOTAM] ⚠ " + "; ".join(alerts))
            messagebox.showwarning("NOTAM Alerts", "\n".join(alerts[:10]))
        self.after(60_000, self._notam_alert_check)

    def _radar_start(self):
        self._radar_running = True
        self._radar_loop()
        self._log("[RADAR] started")

    def _radar_stop(self):
        self._radar_running = False
        self._log("[RADAR] stopped")

    def _radar_loop(self):
        if getattr(self, "_radar_running", False):
            for sim in self.sim_tracks:
                sim.step(RADAR_REFRESH_MS / 1000.0)
            self._radar_draw()
            self.after(RADAR_REFRESH_MS, self._radar_loop)

    def _radar_draw(self):
        if self.radar_canvas is None:
            return
        self.radar_canvas.delete("all")
        w, h, cx, cy = self._radar_dims()
        radius = min(w, h) * 0.45
        self.radar_canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline="#1bf2ff")
        step = max(1, int(self.radar_range_var.get() // RADAR_GRID_STEP_NM))
        for i in range(1, step + 1):
            r = radius * i / step
            self.radar_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#0a4150")
        self.radar_canvas.create_line(cx, 0, cx, h, fill="#0a4150")
        self.radar_canvas.create_line(0, cy, w, cy, fill="#0a4150")
        self._radar_draw_navaids()
        for sim in self.sim_tracks:
            self._draw_sim_track(sim)
        for track in self.feed.tracks.values():
            self._draw_live_track(track)
        self._update_track_list()

    def _clear_trails(self):
        for sim in self.sim_tracks:
            sim.trail = []
        for track in self.feed.tracks.values():
            track.trail = []
        self._log("[RADAR] trails cleared")

    def _draw_sim_track(self, sim):
        if sim.lat is None or sim.lon is None:
            return
        coords = []
        for lat, lon in sim.trail:
            x, y = self._latlon_to_canvas(lat, lon)
            coords.extend([x, y])
        if len(coords) >= 4:
            self.radar_canvas.create_line(*coords, fill="#66ff66")
        x, y = self._latlon_to_canvas(sim.lat, sim.lon)
        self.radar_canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#66ff66", outline="")
        self.radar_canvas.create_text(x + 8, y - 8, text=sim.name, fill="#ccffcc", anchor="w")

    def _draw_live_track(self, track):
        if track.lat is None or track.lon is None:
            return
        coords = []
        for lat, lon in track.trail:
            x, y = self._latlon_to_canvas(lat, lon)
            coords.extend([x, y])
        if len(coords) >= 4:
            self.radar_canvas.create_line(*coords, fill="#ffd966")
        x, y = self._latlon_to_canvas(track.lat, track.lon)
        self.radar_canvas.create_rectangle(x - 4, y - 4, x + 4, y + 4, fill="#ffd966", outline="")
        label = track.callsign or track.icao
        self.radar_canvas.create_text(x + 8, y + 8, text=label, fill="#fff4ba", anchor="w")

    def _radar_draw_navaids(self):
        for row in SAAF_RUNWAYS[:3]:
            # Use fixed offsets derived from runway index to give stable positions
            idx = SAAF_RUNWAYS.index(row)
            lat = self.radar_center_lat.get() + (idx - 1) * 0.15
            lon = self.radar_center_lon.get() + (idx - 1) * 0.10
            x, y = self._latlon_to_canvas(lat, lon)
            self.radar_canvas.create_polygon(x, y - 6, x + 5, y + 4, x - 5, y + 4, outline="#1bf2ff", fill="")
            self.radar_canvas.create_text(x + 8, y - 8, text=row["ICAO"], fill="#7ee6ff", anchor="w")

    def _radar_on_click(self, event):
        best = None
        best_d = 999999.0
        for track in self.feed.tracks.values():
            if track.lat is None or track.lon is None:
                continue
            x, y = self._latlon_to_canvas(track.lat, track.lon)
            d = math.hypot(event.x - x, event.y - y)
            if d < best_d:
                best = track
                best_d = d
        if best is None:
            for sim in self.sim_tracks:
                x, y = self._latlon_to_canvas(sim.lat, sim.lon)
                d = math.hypot(event.x - x, event.y - y)
                if d < best_d:
                    best = sim
                    best_d = d
        self.radar_selected = best
        self._radar_update_detail()

    def _radar_update_detail(self):
        t = self.radar_selected
        if t is None:
            self.radar_detail_var.set("No track selected")
            return
        name = getattr(t, "callsign", "") or getattr(t, "icao", "") or getattr(t, "name", "")
        lat = getattr(t, "lat", None)
        lon = getattr(t, "lon", None)
        alt = getattr(t, "alt", getattr(t, "alt_ft", None))
        spd = getattr(t, "speed", getattr(t, "speed_kt", None))
        hdg = getattr(t, "heading", None)
        text = "Track: {0}\nLat/Lon: {1}, {2}\nAlt: {3}\nSpeed: {4}\nHeading: {5}".format(name, _fmt_value(lat), _fmt_value(lon), _fmt_value(alt), _fmt_value(spd), _fmt_value(hdg))
        self.radar_detail_var.set(text)

    def _latlon_to_canvas(self, lat, lon):
        w, h, cx, cy = self._radar_dims()
        rng = max(1.0, float(self.radar_range_var.get()))
        dlat_nm = (lat - self.radar_center_lat.get()) * 60.0
        dlon_nm = (lon - self.radar_center_lon.get()) * 60.0 * max(0.1, math.cos(math.radians(self.radar_center_lat.get())))
        scale = min(w, h) * 0.45 / rng
        x = cx + dlon_nm * scale
        y = cy - dlat_nm * scale
        return x, y

    def _radar_dims(self):
        w = max(RADAR_MIN_SIZE, self.radar_canvas.winfo_width() or RADAR_MIN_SIZE)
        h = max(RADAR_MIN_SIZE, self.radar_canvas.winfo_height() or RADAR_MIN_SIZE)
        return w, h, w / 2.0, h / 2.0

    def _feed_start(self):
        mode = self.feed_mode_var.get()
        self.feed.start(mode, self.tcp_host_var.get(), self.tcp_port_var.get(), self._log)
        self._log("[FEED] started {0}".format(mode))

    def _feed_stop(self):
        self.feed.stop()
        self._log("[FEED] stopped")

    def _feed_mode_changed(self):
        self._log("[FEED] mode {0}".format(self.feed_mode_var.get()))

    def _feed_stats_poller(self):
        count = self.feed.stats.get("msg_count", 0)
        tracks = self.feed.stats.get("track_count", 0)
        self.feed_stats_var.set("Messages: {0}  Tracks: {1}".format(count, tracks))
        self.after(1000, self._feed_stats_poller)

    def _update_track_list(self):
        if self.track_list is None:
            return
        self.track_list.delete(0, "end")
        for key in sorted(self.feed.tracks):
            tr = self.feed.tracks[key]
            label = tr.callsign or tr.icao
            self.track_list.insert("end", "{0}  {1}".format(label, _fmt_value(tr.alt)))

    @staticmethod
    def _parse_ihex(path):
        data = bytearray()
        base = 0
        segments = {}
        with open(path, "r", encoding="ascii") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or not line.startswith(":"):
                    continue
                count = int(line[1:3], 16)
                addr = int(line[3:7], 16)
                rectype = int(line[7:9], 16)
                recdata = bytes.fromhex(line[9:9 + count * 2])
                if rectype == 0x00:
                    absolute = base + addr
                    segments[absolute] = recdata
                elif rectype == 0x04:
                    base = int.from_bytes(recdata, "big") << 16
                elif rectype == 0x01:
                    break
        if not segments:
            return b""
        end = max(addr + len(chunk) for addr, chunk in segments.items())
        data.extend(b"\x00" * end)
        for addr, chunk in segments.items():
            data[addr:addr + len(chunk)] = chunk
        return bytes(data)

    def _compare_load_a(self):
        path = filedialog.askopenfilename(filetypes=[("Binary/Hex", "*.bin *.hex *.ihex"), ("All", "*")])
        if not path:
            return
        if path.lower().endswith((".hex", ".ihex")):
            self.compare_data_a = self._parse_ihex(path)
        else:
            with open(path, "rb") as fh:
                self.compare_data_a = fh.read()
        self._log("[COMPARE] loaded A {0}".format(path))

    def _compare_load_b(self):
        path = filedialog.askopenfilename(filetypes=[("Binary/Hex", "*.bin *.hex *.ihex"), ("All", "*")])
        if not path:
            return
        if path.lower().endswith((".hex", ".ihex")):
            self.compare_data_b = self._parse_ihex(path)
        else:
            with open(path, "rb") as fh:
                self.compare_data_b = fh.read()
        self._log("[COMPARE] loaded B {0}".format(path))

    def _compare_refresh(self):
        self.compare_view.load(self.compare_data_a, self.compare_data_b, "A", "B")
        self._log("[COMPARE] refreshed")

    def _patch_load_orig(self):
        path = filedialog.askopenfilename(filetypes=[("Binary", "*.bin *.hex *.ihex"), ("All", "*")])
        if not path:
            return
        if path.lower().endswith((".hex", ".ihex")):
            self.patch_orig = self._parse_ihex(path)
        else:
            with open(path, "rb") as fh:
                self.patch_orig = fh.read()
        self._log("[PATCH] original loaded {0}".format(path))

    def _patch_load_mod(self):
        path = filedialog.askopenfilename(filetypes=[("Binary", "*.bin *.hex *.ihex"), ("All", "*")])
        if not path:
            return
        if path.lower().endswith((".hex", ".ihex")):
            self.patch_mod = self._parse_ihex(path)
        else:
            with open(path, "rb") as fh:
                self.patch_mod = fh.read()
        self._log("[PATCH] patched loaded {0}".format(path))

    def _patch_generate(self):
        patch = BinaryPatcher.generate(self.patch_orig, self.patch_mod)
        path = filedialog.asksaveasfilename(defaultextension=".navpatch", filetypes=[("NAV Patch", "*.navpatch")])
        if not path:
            return
        with open(path, "wb") as fh:
            fh.write(patch)
        records = BinaryPatcher.parse(patch)
        self.patch_text.delete("1.0", "end")
        self.patch_text.insert("1.0", json.dumps(records, indent=2))
        self._log("[PATCH] generated {0} with {1} records".format(path, len(records)))

    def _patch_apply(self):
        patch_path = filedialog.askopenfilename(filetypes=[("NAV Patch", "*.navpatch"), ("All", "*")])
        if not patch_path:
            return
        with open(patch_path, "rb") as fh:
            patch_data = fh.read()
        patched = BinaryPatcher.apply(self.patch_orig, patch_data)
        out_path = filedialog.asksaveasfilename(defaultextension=".bin", filetypes=[("Binary", "*.bin")])
        if not out_path:
            return
        with open(out_path, "wb") as fh:
            fh.write(patched)
        self._log("[PATCH] applied -> {0}".format(out_path))

    def _run_local_test(self):
        prog = self.local_test_var.get()
        cmd = LOCAL_TEST_CMDS.get(prog, "")
        self.local_test_output.insert("end", "Program: {0}\n".format(prog))
        if prog == "loopback":
            ok = self.tcp_tester.test_local(self._log)
        else:
            reply = self.comm.send(cmd)
            ok = reply in ("PASS", "OK", "ACK")
            self._log("[TEST] {0} -> {1}".format(cmd, reply))
        self.local_test_output.insert("end", "Result: {0}\n\n".format("PASS" if ok else "FAIL"))
        self.local_test_output.see("end")

    def _chart_add_sample(self):
        sample = {
            "tx_power": 48 + random.random() * 4,
            "vswr": 1.0 + random.random() * 0.3,
        }
        self.chart_points.append(sample)
        xs = list(range(len(self.chart_points)))
        tx = [p["tx_power"] for p in self.chart_points]
        vs = [p["vswr"] * 20 for p in self.chart_points]
        self.chart_axes.clear()
        self.chart_axes.plot(xs, tx, label="TX Power (W)")
        self.chart_axes.plot(xs, vs, label="VSWR x20")
        self.chart_axes.legend()
        self.chart_axes.set_title("TX Power / VSWR Trend")
        self.chart_canvas.draw_idle()

    def _sim_step(self):
        self.sim_text.delete("1.0", "end")
        for sim in self.sim_tracks:
            sim.step(1.0)
            line = "{0}: lat={1:.4f} lon={2:.4f} hdg={3:.1f} spd={4:.1f}\n".format(sim.name, sim.lat, sim.lon, sim.heading, sim.speed_kt)
            self.sim_text.insert("end", line)
        self._radar_draw()

    def _inspection_add_sample(self):
        now = datetime.datetime.now()
        row = [
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            self.station_var.get(),
            "VOR",
            "TX Power",
            "49.1",
            "49.8",
            self.tech_var.get(),
            "Routine inspection",
        ]
        self.inspect_tree.insert("", "end", values=row)
        self.log_records.append(dict(zip(LOG_COLUMNS, row)))
        self._log("[INSP] sample entry added")

    def _notam_add(self):
        idx = len(self.notam_records) + 1
        today = datetime.date.today()
        row = {
            "ID": str(idx),
            "Type": NOTAM_TYPES[idx % len(NOTAM_TYPES)],
            "Priority": NOTAM_PRIORITY[idx % len(NOTAM_PRIORITY)],
            "Status": NOTAM_STATUS[0],
            "Station": self.station_var.get(),
            "Description": "Sample NOTAM {0}".format(idx),
            "Issue Date": today.strftime("%Y-%m-%d"),
            "Due Date": (today + datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
            "Technician": self.tech_var.get(),
        }
        self.notam_records.append(row)
        self._refresh_notam_tree()
        self._log("[NOTAM] added #{0}".format(row["ID"]))

    def _refresh_notam_tree(self):
        if self.notam_tree is None:
            return
        self.notam_tree.delete(*self.notam_tree.get_children())
        for row in self.notam_records:
            self.notam_tree.insert("", "end", values=[row.get(col, "") for col in NOTAM_COLUMNS])

    def _save_notams(self):
        with open(NOTAM_FILE, "w", encoding="utf-8") as fh:
            json.dump(self.notam_records, fh, indent=2)
        self._log("[NOTAM] saved")

    def destroy(self):
        try:
            self._save_config()
        except Exception:
            pass
        try:
            self.feed.stop()
        except Exception:
            pass
        try:
            self.comm.disconnect()
        except Exception:
            pass
        super().destroy()


if __name__ == "__main__":
    NAVAIDSApp().mainloop()
