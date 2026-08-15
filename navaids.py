"""
navaids.py – NAVAIDS ADS-B / Radar display application.

Includes:
  • SBS-1, Beast, AVR, ASTERIX CAT-048 feed managers
  • ADS-B Recording / Replay (ADSBRecorder, ADSBReplayer)
  • Tkinter GUI with Radar PPI, ADSB config, and Rec/Play tabs
"""
from __future__ import annotations

import os
import socket
import struct
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants – Feed modes
# ---------------------------------------------------------------------------
FEED_MODE_NONE    = "NONE"
FEED_MODE_SBS     = "SBS"
FEED_MODE_BEAST   = "BEAST"
FEED_MODE_AVR     = "AVR"
FEED_MODE_ASTERIX = "ASTERIX"

# ---------------------------------------------------------------------------
# Constants – ADS-B Replay / Recording
# ---------------------------------------------------------------------------
REPLAY_DIR          = "adsb_recordings"     # default folder for recordings
REPLAY_MAGIC        = b"NAVADSB1"           # 8-byte file magic
REPLAY_FRAME_MARKER = b"\xFE\xED"          # 2-byte marker before each frame
REPLAY_MARKER       = REPLAY_FRAME_MARKER  # alias used in write_frame

# Create recordings folder on startup
os.makedirs(REPLAY_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Simple data container for a tracked aircraft
# ---------------------------------------------------------------------------
class Track:
    __slots__ = ("icao", "callsign", "lat", "lon", "alt", "speed",
                 "heading", "vrate", "last_seen", "source")

    def __init__(self, icao: str):
        self.icao      = icao
        self.callsign  = ""
        self.lat: Optional[float] = None
        self.lon: Optional[float] = None
        self.alt: Optional[int]   = None
        self.speed: Optional[float] = None
        self.heading: Optional[float] = None
        self.vrate: Optional[int] = None
        self.last_seen = time.time()
        self.source    = FEED_MODE_NONE

    def __repr__(self) -> str:
        return (f"Track({self.icao} cs={self.callsign!r} "
                f"lat={self.lat} lon={self.lon} alt={self.alt})")


# ---------------------------------------------------------------------------
# SBS-1 text parser
# ---------------------------------------------------------------------------
class SBSParser:
    """Parse SBS-1 BaseStation text messages."""

    @staticmethod
    def parse_line(line: str) -> Optional[Dict]:
        """Return a dict of extracted fields or None if unparseable."""
        line = line.strip()
        if not line:
            return None
        parts = line.split(",")
        if len(parts) < 22:
            return None
        msg_type = parts[0]
        if msg_type != "MSG":
            return None
        result: Dict = {"icao": parts[4].upper()}
        trans = parts[1]
        try:
            if trans in ("1",):
                result["callsign"] = parts[10].strip()
            elif trans in ("3",):
                result["alt"]   = int(parts[11]) if parts[11] else None
                raw_lat = parts[14]
                raw_lon = parts[15]
                if raw_lat and raw_lon:
                    result["lat"] = float(raw_lat)
                    result["lon"] = float(raw_lon)
            elif trans in ("4",):
                result["speed"]   = float(parts[12]) if parts[12] else None
                result["heading"] = float(parts[13]) if parts[13] else None
                result["vrate"]   = int(parts[16])   if parts[16] else None
        except (ValueError, IndexError):
            pass
        return result


# ---------------------------------------------------------------------------
# Beast binary frame parser
# ---------------------------------------------------------------------------
class BeastParser:
    """Parse Mode-S Beast binary frames (1A escape protocol)."""

    ESCAPE = 0x1A

    @staticmethod
    def extract_frames(buf: bytes) -> Tuple[List[bytes], bytes]:
        """
        Extract complete Beast frames from a buffer.
        Returns (list_of_frames, remaining_bytes).
        """
        frames: List[bytes] = []
        i = 0
        n = len(buf)
        while i < n:
            if buf[i] != BeastParser.ESCAPE:
                i += 1
                continue
            if i + 1 >= n:
                break
            frame_type = buf[i + 1]
            if frame_type not in (0x31, 0x32, 0x33, 0x34):
                i += 2
                continue
            # frame lengths: 0x31=2+7, 0x32=2+14, 0x33=2+21, 0x34=2+14
            lengths = {0x31: 9, 0x32: 16, 0x33: 23, 0x34: 16}
            total = lengths[frame_type]
            if i + total > n:
                break
            raw = buf[i: i + total]
            frames.append(raw)
            i += total
        return frames, buf[i:]

    @staticmethod
    def parse_frame(raw: bytes) -> Optional[Dict]:
        """Parse a single Beast frame into a dict."""
        if len(raw) < 2 or raw[0] != BeastParser.ESCAPE:
            return None
        frame_type = raw[1]
        if frame_type not in (0x31, 0x32, 0x33, 0x34):
            return None
        payload_starts = {0x31: 9, 0x32: 16, 0x33: 23, 0x34: 16}
        pstart = payload_starts.get(frame_type, 2)
        payload = raw[2: pstart] if len(raw) >= pstart else b""
        if len(payload) < 7:
            return None
        # MLAT timestamp (6 bytes) + signal level (1 byte) + DF bytes
        df_bytes = payload[7:] if len(payload) > 7 else b""
        if not df_bytes:
            return None
        df = (df_bytes[0] >> 3) & 0x1F
        icao = ""
        if len(df_bytes) >= 4:
            icao = df_bytes[1:4].hex().upper()
        return {"icao": icao, "df": df, "raw_payload": df_bytes.hex()}


# ---------------------------------------------------------------------------
# ASTERIX CAT-048 decoder (minimal)
# ---------------------------------------------------------------------------
class AsterixCAT048:
    """Minimal ASTERIX CAT-048 decoder."""

    @staticmethod
    def decode_message(data: bytes) -> List[Dict]:
        """
        Decode a CAT-048 ASTERIX message.
        Returns list of track dicts.
        """
        if len(data) < 3:
            return []
        cat = data[0]
        if cat != 48:
            return []
        length = struct.unpack(">H", data[1:3])[0]
        if length > len(data):
            return []
        # Very minimal: just extract ICAO from fixed byte positions if possible
        result: Dict = {}
        # FSPEC starts at offset 3
        offset = 3
        fspec: List[int] = []
        while offset < len(data):
            b = data[offset]
            fspec.append(b)
            offset += 1
            if not (b & 0x01):
                break
        # data items follow – we only attempt to extract I048/220 (aircraft address)
        # For a minimal implementation, mark the icao as unknown
        result["icao"] = "UNKNOWN"
        result["source"] = FEED_MODE_ASTERIX
        return [result]


# ---------------------------------------------------------------------------
# ADSBFeedManager
# ---------------------------------------------------------------------------
class ADSBFeedManager:
    """
    Manages live ADS-B data feeds: SBS-1, Beast, AVR, ASTERIX CAT-048.
    """

    def __init__(self, log_cb: Callable[[str], None]):
        self.log     = log_cb
        self.tracks: Dict[str, Track] = {}
        self._lock   = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.mode     = FEED_MODE_NONE
        self.host     = "127.0.0.1"
        self.port     = 30003
        self.recorder: Optional["ADSBRecorder"] = None  # hooked recorder

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def connect(self, host: str, port: int, mode: str):
        self.stop()
        self.host = host
        self.port = port
        self.mode = mode
        self._running = True
        worker_map = {
            FEED_MODE_SBS:     self._worker_sbs,
            FEED_MODE_BEAST:   self._worker_beast,
            FEED_MODE_AVR:     self._worker_avr,
            FEED_MODE_ASTERIX: self._worker_asterix,
        }
        worker = worker_map.get(mode, self._worker_sbs)
        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _merge(self, data: Dict, source: str):
        """Merge parsed track data into tracks dict."""
        icao = data.get("icao", "")
        if not icao or icao == "UNKNOWN":
            return
        with self._lock:
            track = self.tracks.setdefault(icao, Track(icao))
            track.source    = source
            track.last_seen = time.time()
            if "callsign" in data and data["callsign"]:
                track.callsign = data["callsign"]
            if "lat" in data and data["lat"] is not None:
                track.lat = data["lat"]
            if "lon" in data and data["lon"] is not None:
                track.lon = data["lon"]
            if "alt" in data and data["alt"] is not None:
                track.alt = data["alt"]
            if "speed" in data and data["speed"] is not None:
                track.speed = data["speed"]
            if "heading" in data and data["heading"] is not None:
                track.heading = data["heading"]
            if "vrate" in data and data["vrate"] is not None:
                track.vrate = data["vrate"]

    # ------------------------------------------------------------------
    # SBS-1 worker
    # ------------------------------------------------------------------
    def _worker_sbs(self):
        buf = b""
        sock = None
        try:
            sock = socket.create_connection((self.host, self.port), timeout=5)
            sock.settimeout(1.0)
            while self._running:
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line_bytes, buf = buf.split(b"\n", 1)
                    line_bytes += b"\n"
                    # Hook recorder
                    if self.recorder and self.recorder.recording:
                        self.recorder.write_frame(line_bytes)
                    parsed = SBSParser.parse_line(line_bytes.decode("ascii", errors="replace"))
                    if parsed:
                        self._merge(parsed, FEED_MODE_SBS)
        except OSError as exc:
            self.log(f"[SBS] Connection error: {exc}")
        finally:
            if sock:
                sock.close()

    # ------------------------------------------------------------------
    # Beast worker
    # ------------------------------------------------------------------
    def _worker_beast(self):
        buf = b""
        sock = None
        try:
            sock = socket.create_connection((self.host, self.port), timeout=5)
            sock.settimeout(1.0)
            while self._running:
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf += chunk
                frames, buf = BeastParser.extract_frames(buf)
                for frame in frames:
                    # Hook recorder
                    if self.recorder and self.recorder.recording:
                        self.recorder.write_frame(frame)
                    parsed = BeastParser.parse_frame(frame)
                    if parsed:
                        self._merge(parsed, FEED_MODE_BEAST)
        except OSError as exc:
            self.log(f"[BEAST] Connection error: {exc}")
        finally:
            if sock:
                sock.close()

    # ------------------------------------------------------------------
    # AVR worker
    # ------------------------------------------------------------------
    def _worker_avr(self):
        buf = b""
        sock = None
        try:
            sock = socket.create_connection((self.host, self.port), timeout=5)
            sock.settimeout(1.0)
            while self._running:
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line += b"\n"
                    # Hook recorder
                    if self.recorder and self.recorder.recording:
                        self.recorder.write_frame(line)
                    line_str = line.decode("ascii", errors="replace").strip()
                    if line_str.startswith("*") and line_str.endswith(";"):
                        hex_data = line_str[1:-1]
                        try:
                            raw = bytes.fromhex(hex_data)
                            parsed = BeastParser.parse_frame(
                                bytes([BeastParser.ESCAPE, 0x33]) + raw
                            )
                            if parsed:
                                self._merge(parsed, FEED_MODE_AVR)
                        except ValueError:
                            pass
        except OSError as exc:
            self.log(f"[AVR] Connection error: {exc}")
        finally:
            if sock:
                sock.close()

    # ------------------------------------------------------------------
    # ASTERIX worker (UDP)
    # ------------------------------------------------------------------
    def _worker_asterix(self):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.settimeout(1.0)
            while self._running:
                try:
                    data, _ = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                # Hook recorder
                if self.recorder and self.recorder.recording:
                    self.recorder.write_frame(data)
                records = AsterixCAT048.decode_message(data)
                for rec in records:
                    self._merge(rec, FEED_MODE_ASTERIX)
        except OSError as exc:
            self.log(f"[ASTERIX] Socket error: {exc}")
        finally:
            if sock:
                sock.close()


# ---------------------------------------------------------------------------
# ADSBRecorder
# ---------------------------------------------------------------------------
class ADSBRecorder:
    """
    Records raw ADS-B / ASTERIX frames to a binary .adsbrec file.

    File format (binary, little-endian):
    ┌──────────────────────────────────────────────────────────┐
    │  Header (32 bytes)                                       │
    │    magic      8B  = NAVADSB1                             │
    │    version    2B  = 0x0001                               │
    │    feed_mode  2B  = 0..4  (NONE/SBS/BEAST/AVR/ASTERIX)  │
    │    start_ts   8B  = Unix timestamp float64               │
    │    reserved   12B = 0x00                                 │
    ├──────────────────────────────────────────────────────────┤
    │  Frames (repeated)                                       │
    │    marker     2B  = 0xFEED                               │
    │    rel_time   8B  = float64 seconds since recording start│
    │    data_len   2B  = uint16 frame byte length             │
    │    data       NB  = raw frame bytes                      │
    └──────────────────────────────────────────────────────────┘
    """

    def __init__(self, log_cb: Callable[[str], None]):
        self.log        = log_cb
        self._file      = None
        self._path      = ""
        self._start_ts  = 0.0
        self._count     = 0
        self._lock      = threading.Lock()
        self.recording  = False

    def start(self, path: str, feed_mode: str):
        """Open recording file and write header."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._path     = path
        self._start_ts = time.time()
        self._count    = 0
        mode_idx = {
            FEED_MODE_NONE:    0,
            FEED_MODE_SBS:     1,
            FEED_MODE_BEAST:   2,
            FEED_MODE_AVR:     3,
            FEED_MODE_ASTERIX: 4,
        }.get(feed_mode, 0)
        with self._lock:
            self._file = open(path, "wb")   # noqa: WPS515
            self._file.write(REPLAY_MAGIC)
            self._file.write(struct.pack("<H", 1))               # version
            self._file.write(struct.pack("<H", mode_idx))        # feed mode
            self._file.write(struct.pack("<d", self._start_ts))  # start ts
            self._file.write(b"\x00" * 12)                       # reserved
            self._file.flush()
            self.recording = True
        self.log(f"[REC] Recording started \u2192 {path}")

    def write_frame(self, raw_bytes: bytes):
        """Write one frame with relative timestamp. Thread-safe."""
        if not self.recording or not self._file:
            return
        rel = time.time() - self._start_ts
        with self._lock:
            self._file.write(REPLAY_MARKER)
            self._file.write(struct.pack("<d", rel))
            self._file.write(struct.pack("<H", len(raw_bytes)))
            self._file.write(raw_bytes)
            self._count += 1

    def stop(self):
        """Flush and close recording file."""
        self.recording = False
        with self._lock:
            if self._file:
                self._file.flush()
                self._file.close()
                self._file = None
        self.log(f"[REC] Recording stopped \u2013 {self._count} frames \u2192 {self._path}")

    @property
    def frame_count(self) -> int:
        return self._count

    @property
    def duration(self) -> float:
        return time.time() - self._start_ts if self.recording else 0.0

    @property
    def file_size(self) -> int:
        """Current size of recording file in bytes."""
        try:
            return os.path.getsize(self._path) if self._path else 0
        except OSError:
            return 0


# ---------------------------------------------------------------------------
# Helper: scan an open .adsbrec file (positioned after the 32-byte header)
# and return (frame_count, last_rel_time).  Does not close the file.
# ---------------------------------------------------------------------------
def _scan_adsbrec_frames(fh) -> Tuple[int, float]:
    """Count frames and find the last relative timestamp in a recording file."""
    frame_count = 0
    last_rel    = 0.0
    while True:
        marker = fh.read(2)
        if not marker or marker != REPLAY_FRAME_MARKER:
            break
        rel_bytes = fh.read(8)
        if len(rel_bytes) < 8:
            break
        rel = struct.unpack("<d", rel_bytes)[0]
        len_bytes = fh.read(2)
        if len(len_bytes) < 2:
            break
        data_len = struct.unpack("<H", len_bytes)[0]
        fh.seek(data_len, 1)
        frame_count += 1
        last_rel = rel
    return frame_count, last_rel


# ---------------------------------------------------------------------------
# ADSBReplayer
# ---------------------------------------------------------------------------
class ADSBReplayer:
    """
    Reads a .adsbrec file and replays frames into an ADSBFeedManager
    at adjustable speed.

    Speed multiplier:  0.25x, 0.5x, 1x, 2x, 5x, 10x, MAX (as fast as possible)
    """

    SPEEDS       = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 0.0]  # 0.0 = MAX speed
    SPEED_LABELS = ["0.25\u00d7", "0.5\u00d7", "1\u00d7",
                    "2\u00d7", "5\u00d7", "10\u00d7", "MAX"]

    _MODE_NAMES = ["NONE", "SBS", "BEAST", "AVR", "ASTERIX"]

    def __init__(self, log_cb: Callable[[str], None]):
        self.log             = log_cb
        self._thread: Optional[threading.Thread] = None
        self._running        = False
        self._paused         = False
        self._speed          = 1.0
        self._path           = ""
        self._total_frames   = 0
        self._played_frames  = 0
        self._duration       = 0.0
        self._current_ts     = 0.0
        self._feed: Optional[ADSBFeedManager] = None
        self._on_progress    = None   # callback(played, total, current_ts, duration)
        self._on_complete    = None   # callback()
        self._feed_to_radar  = True
        self._seek_target: Optional[float] = None
        self._meta: Optional[Dict] = None

    # ------------------------------------------------------------------
    # load
    # ------------------------------------------------------------------
    def load(self, path: str) -> Dict:
        """
        Parse file header. Returns metadata dict.
        Raises ValueError on bad magic.
        """
        stat = os.stat(path)
        with open(path, "rb") as fh:
            magic = fh.read(8)
            if magic != REPLAY_MAGIC:
                raise ValueError(f"Bad magic: {magic!r}")
            version      = struct.unpack("<H", fh.read(2))[0]
            feed_mode_idx = struct.unpack("<H", fh.read(2))[0]
            start_ts     = struct.unpack("<d", fh.read(8))[0]
            fh.read(12)  # reserved

            # Count frames and find duration by scanning the file
            frame_count, last_rel = _scan_adsbrec_frames(fh)

        mode_names = self._MODE_NAMES
        feed_mode = mode_names[feed_mode_idx] if feed_mode_idx < len(mode_names) else "UNKNOWN"
        meta = {
            "path":          path,
            "version":       version,
            "feed_mode_idx": feed_mode_idx,
            "feed_mode":     feed_mode,
            "start_ts":      start_ts,
            "frame_count":   frame_count,
            "duration":      last_rel,
            "file_size":     stat.st_size,
        }
        self._meta         = meta
        self._path         = path
        self._total_frames = frame_count
        self._duration     = last_rel
        return meta

    # ------------------------------------------------------------------
    # start
    # ------------------------------------------------------------------
    def start(self, feed: ADSBFeedManager, speed: float = 1.0,
              on_progress: Optional[Callable] = None,
              on_complete: Optional[Callable] = None):
        """Begin replay in a background thread."""
        if self._running:
            self.stop()
        self._feed        = feed
        self._speed       = speed
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._running     = True
        self._paused      = False
        self._played_frames = 0
        self._current_ts  = 0.0
        self._seek_target = None
        self._thread = threading.Thread(target=self._replay_worker, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # pause / stop / set_speed / seek
    # ------------------------------------------------------------------
    def pause(self):
        """Toggle pause state."""
        self._paused = not self._paused

    def stop(self):
        """Stop replay cleanly."""
        self._running = False
        self._paused  = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def set_speed(self, speed: float):
        """Change playback speed mid-replay."""
        self._speed = speed

    def seek(self, target_ts: float):
        """Seek to a relative timestamp (seconds from start)."""
        self._seek_target = float(target_ts)

    # ------------------------------------------------------------------
    # _replay_worker
    # ------------------------------------------------------------------
    def _replay_worker(self):
        """
        Background thread: open file, replay frames with timing.
        """
        if not self._path or not self._meta:
            self.log("[REPLAY] No file loaded.")
            return

        feed_mode_idx = self._meta["feed_mode_idx"]
        mode_names    = self._MODE_NAMES

        last_cb_time  = 0.0

        def _call_progress():
            nonlocal last_cb_time
            now = time.time()
            if now - last_cb_time < 0.1:
                return
            last_cb_time = now
            if self._on_progress:
                self._on_progress(
                    self._played_frames,
                    self._total_frames,
                    self._current_ts,
                    self._duration,
                )

        def _parse_and_merge(raw_bytes: bytes):
            """Parse raw bytes according to feed mode and merge into feed."""
            if not self._feed_to_radar or self._feed is None:
                return
            feed = self._feed
            if feed_mode_idx == 1:  # SBS
                lines = raw_bytes.decode("ascii", errors="replace").split("\n")
                for ln in lines:
                    parsed = SBSParser.parse_line(ln)
                    if parsed:
                        feed._merge(parsed, FEED_MODE_SBS)
            elif feed_mode_idx == 2:  # BEAST
                frames, _ = BeastParser.extract_frames(raw_bytes)
                for frm in frames:
                    parsed = BeastParser.parse_frame(frm)
                    if parsed:
                        feed._merge(parsed, FEED_MODE_BEAST)
                # Also try direct parse if extract_frames returned nothing
                if not frames:
                    parsed = BeastParser.parse_frame(raw_bytes)
                    if parsed:
                        feed._merge(parsed, FEED_MODE_BEAST)
            elif feed_mode_idx == 3:  # AVR
                line_str = raw_bytes.decode("ascii", errors="replace").strip()
                if line_str.startswith("*") and line_str.endswith(";"):
                    hex_data = line_str[1:-1]
                    try:
                        raw = bytes.fromhex(hex_data)
                        parsed = BeastParser.parse_frame(
                            bytes([BeastParser.ESCAPE, 0x33]) + raw
                        )
                        if parsed:
                            feed._merge(parsed, FEED_MODE_AVR)
                    except ValueError:
                        pass
            elif feed_mode_idx == 4:  # ASTERIX
                records = AsterixCAT048.decode_message(raw_bytes)
                for rec in records:
                    feed._merge(rec, FEED_MODE_ASTERIX)
            else:
                # NONE / unknown – try SBS first, then Beast
                lines = raw_bytes.decode("ascii", errors="replace").split("\n")
                for ln in lines:
                    parsed = SBSParser.parse_line(ln)
                    if parsed:
                        feed._merge(parsed, FEED_MODE_SBS)
                        return
                frames, _ = BeastParser.extract_frames(raw_bytes)
                for frm in frames:
                    parsed = BeastParser.parse_frame(frm)
                    if parsed:
                        feed._merge(parsed, FEED_MODE_BEAST)

        try:
            with open(self._path, "rb") as fh:
                # Skip 32-byte header
                fh.seek(32)
                prev_rel   = 0.0
                wall_start = time.time()

                while self._running:
                    # Handle seek
                    if self._seek_target is not None:
                        target = self._seek_target
                        self._seek_target = None
                        fh.seek(32)
                        prev_rel   = 0.0
                        wall_start = time.time() - target
                        self._played_frames = 0
                        # Skip frames until we reach target
                        while True:
                            marker = fh.read(2)
                            if not marker or marker != REPLAY_FRAME_MARKER:
                                break
                            rel_b = fh.read(8)
                            if len(rel_b) < 8:
                                break
                            rel = struct.unpack("<d", rel_b)[0]
                            len_b = fh.read(2)
                            if len(len_b) < 2:
                                break
                            data_len = struct.unpack("<H", len_b)[0]
                            if rel >= target:
                                # Read this frame
                                frame_data = fh.read(data_len)
                                prev_rel = rel
                                self._current_ts = rel
                                break
                            fh.seek(data_len, 1)
                            self._played_frames += 1

                    # Handle pause
                    if self._paused:
                        time.sleep(0.05)
                        continue

                    # Read next frame
                    marker = fh.read(2)
                    if not marker:
                        break
                    if marker != REPLAY_FRAME_MARKER:
                        # Try to resync
                        break
                    rel_b = fh.read(8)
                    if len(rel_b) < 8:
                        break
                    rel = struct.unpack("<d", rel_b)[0]
                    len_b = fh.read(2)
                    if len(len_b) < 2:
                        break
                    data_len = struct.unpack("<H", len_b)[0]
                    frame_data = fh.read(data_len)
                    if len(frame_data) < data_len:
                        break

                    # Timing
                    speed = self._speed
                    if speed > 0.0:
                        elapsed  = time.time() - wall_start
                        expected = rel / speed
                        sleep_t  = expected - elapsed
                        if sleep_t > 0:
                            time.sleep(sleep_t)

                    _parse_and_merge(frame_data)

                    prev_rel            = rel
                    self._current_ts    = rel
                    self._played_frames += 1
                    _call_progress()

        except OSError as exc:
            self.log(f"[REPLAY] File error: {exc}")

        self._running = False
        _call_progress()
        if self._on_complete:
            self._on_complete()
        self.log("[REPLAY] Playback complete.")


# ---------------------------------------------------------------------------
# NAVAIDSApp – Main Tkinter application
# ---------------------------------------------------------------------------
class NAVAIDSApp(tk.Tk):
    """NAVAIDS ADS-B Radar display application."""

    def __init__(self):
        super().__init__()
        self.title("NAVAIDS – ADS-B Radar")
        self.geometry("1100x750")
        self.resizable(True, True)

        # Feed manager
        self.feed = ADSBFeedManager(self._log)

        # Rec/Play state
        self._recorder: Optional[ADSBRecorder] = None
        self._replayer = ADSBReplayer(self._log)
        self._rec_folder_var = tk.StringVar(value=REPLAY_DIR)

        # Log buffer
        self._log_lines: List[str] = []

        self._build_ui()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self._log_lines.append(line)
        # Keep last 500 lines
        if len(self._log_lines) > 500:
            self._log_lines = self._log_lines[-500:]
        if hasattr(self, "_log_text"):
            self._log_text.configure(state="normal")
            self._log_text.insert("end", line + "\n")
            self._log_text.see("end")
            self._log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=4, pady=4)

        self._tab_radar()
        self._tab_adsb_replay()
        self._tab_log()

    # ==================================================================
    # TAB: Radar / Connection
    # ==================================================================
    def _tab_radar(self):
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="\U0001f4e1 Radar")

        # Connection settings
        conn_lf = ttk.LabelFrame(frame, text="ADS-B Connection")
        conn_lf.pack(fill="x", padx=8, pady=6)

        ttk.Label(conn_lf, text="Host:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self._host_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(conn_lf, textvariable=self._host_var, width=18).grid(
            row=0, column=1, padx=4, pady=4)

        ttk.Label(conn_lf, text="Port:").grid(row=0, column=2, sticky="e", padx=4)
        self._port_var = tk.StringVar(value="30003")
        ttk.Entry(conn_lf, textvariable=self._port_var, width=8).grid(
            row=0, column=3, padx=4)

        ttk.Label(conn_lf, text="Mode:").grid(row=0, column=4, sticky="e", padx=4)
        self._mode_var = tk.StringVar(value=FEED_MODE_SBS)
        mode_cb = ttk.Combobox(conn_lf, textvariable=self._mode_var,
                               values=[FEED_MODE_SBS, FEED_MODE_BEAST,
                                       FEED_MODE_AVR, FEED_MODE_ASTERIX],
                               state="readonly", width=10)
        mode_cb.grid(row=0, column=5, padx=4)

        ttk.Button(conn_lf, text="Connect", command=self._connect).grid(
            row=0, column=6, padx=8)
        ttk.Button(conn_lf, text="Disconnect", command=self._disconnect).grid(
            row=0, column=7, padx=4)

        # PPI canvas
        ppi_lf = ttk.LabelFrame(frame, text="PPI (Plan Position Indicator)")
        ppi_lf.pack(fill="both", expand=True, padx=8, pady=4)

        self._canvas = tk.Canvas(ppi_lf, bg="black")
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda _e: self._draw_ppi())

        # Status bar
        self._status_var = tk.StringVar(value="Disconnected")
        ttk.Label(frame, textvariable=self._status_var, anchor="w").pack(
            fill="x", padx=8)

        # Start PPI refresh loop
        self.after(1000, self._ppi_refresh)

    def _connect(self):
        try:
            port = int(self._port_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid port number.")
            return
        mode = self._mode_var.get()
        host = self._host_var.get()
        self.feed.connect(host, port, mode)
        self._status_var.set(f"Connecting \u2192 {host}:{port} [{mode}]")
        self._log(f"Connecting to {host}:{port} mode={mode}")

    def _disconnect(self):
        self.feed.stop()
        self._status_var.set("Disconnected")
        self._log("Disconnected.")

    def _ppi_refresh(self):
        self._draw_ppi()
        n = len(self.feed.tracks)
        self._status_var.set(
            f"{'Connected' if self.feed._running else 'Disconnected'} | Tracks: {n}")
        self.after(1000, self._ppi_refresh)

    def _draw_ppi(self):
        c = self._canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 2 or h < 2:
            return
        cx, cy = w // 2, h // 2
        # Draw range rings
        for r in [0.25, 0.5, 0.75, 1.0]:
            rad = int(min(cx, cy) * r)
            c.create_oval(cx - rad, cy - rad, cx + rad, cy + rad,
                          outline="#003300", width=1)
        # Plot tracks (simple equirectangular, centred on first track with position)
        tracks_with_pos = [t for t in self.feed.tracks.values()
                           if t.lat is not None and t.lon is not None]
        if tracks_with_pos:
            ref_lat = tracks_with_pos[0].lat
            ref_lon = tracks_with_pos[0].lon
            scale   = min(cx, cy) / 2.0
            for trk in tracks_with_pos:
                dx = (trk.lon - ref_lon) * 60 * scale / 30
                dy = -(trk.lat - ref_lat) * 60 * scale / 30
                px, py = int(cx + dx), int(cy + dy)
                c.create_oval(px - 3, py - 3, px + 3, py + 3,
                              fill="#00FF00", outline="#00FF00")
                label = trk.callsign or trk.icao
                c.create_text(px + 6, py - 6, text=label,
                              fill="#00FF00", anchor="w", font=("Courier", 8))

    # ==================================================================
    # TAB: ADS-B Rec/Play
    # ==================================================================
    def _tab_adsb_replay(self):
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="\u23fa ADS-B Rec/Play")

        # Use a scrollable canvas so the tab content doesn't overflow
        outer = ttk.Frame(frame)
        outer.pack(fill="both", expand=True)

        # ── RECORDING section ─────────────────────────────────────────
        rec_lf = ttk.LabelFrame(outer, text="RECORDING")
        rec_lf.pack(fill="x", padx=8, pady=6)

        # Folder row
        ttk.Label(rec_lf, text="Folder:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(rec_lf, textvariable=self._rec_folder_var, width=40).grid(
            row=0, column=1, padx=4, pady=3, sticky="w")
        ttk.Button(rec_lf, text="\U0001f4c2 Browse",
                   command=self._rec_browse_folder).grid(row=0, column=2, padx=4)

        # Auto filename hint
        self._rec_fname_var = tk.StringVar(value="(auto)")
        ttk.Label(rec_lf, text="Filename:").grid(row=1, column=0, sticky="e", padx=4)
        ttk.Label(rec_lf, textvariable=self._rec_fname_var, foreground="gray").grid(
            row=1, column=1, sticky="w", padx=4)

        # Buttons
        ttk.Button(rec_lf, text="\u23fa Start Recording",
                   command=self._rec_start).grid(row=2, column=0, padx=8, pady=4, sticky="w")
        ttk.Button(rec_lf, text="\u23f9 Stop Recording",
                   command=self._rec_stop).grid(row=2, column=1, padx=4, pady=4, sticky="w")

        # Status
        self._rec_status_var = tk.StringVar(value="Idle")
        ttk.Label(rec_lf, textvariable=self._rec_status_var).grid(
            row=3, column=0, columnspan=3, sticky="w", padx=8, pady=2)

        # ── PLAYBACK section ─────────────────────────────────────────
        play_lf = ttk.LabelFrame(outer, text="PLAYBACK")
        play_lf.pack(fill="x", padx=8, pady=6)

        # File row
        ttk.Label(play_lf, text="File:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        self._play_file_var = tk.StringVar()
        ttk.Entry(play_lf, textvariable=self._play_file_var, width=45).grid(
            row=0, column=1, padx=4, pady=3, sticky="w")
        ttk.Button(play_lf, text="\U0001f4c2 Open",
                   command=self._play_open_file).grid(row=0, column=2, padx=4)

        # File info
        self._play_info_var = tk.StringVar(value="No file loaded")
        ttk.Label(play_lf, textvariable=self._play_info_var, foreground="gray").grid(
            row=1, column=0, columnspan=3, sticky="w", padx=8, pady=2)

        # Speed + transport controls
        ctrl_frame = ttk.Frame(play_lf)
        ctrl_frame.grid(row=2, column=0, columnspan=3, sticky="w", padx=4, pady=4)

        ttk.Label(ctrl_frame, text="Speed:").pack(side="left", padx=2)
        self._speed_var = tk.StringVar(value="1\u00d7")
        speed_cb = ttk.Combobox(ctrl_frame, textvariable=self._speed_var,
                                values=ADSBReplayer.SPEED_LABELS,
                                state="readonly", width=7)
        speed_cb.pack(side="left", padx=2)
        speed_cb.bind("<<ComboboxSelected>>", self._play_speed_changed)

        ttk.Button(ctrl_frame, text="\u25b6 Play",
                   command=self._play_start).pack(side="left", padx=4)
        ttk.Button(ctrl_frame, text="\u23f8 Pause",
                   command=self._play_pause).pack(side="left", padx=2)
        ttk.Button(ctrl_frame, text="\u23f9 Stop",
                   command=self._play_stop).pack(side="left", padx=2)

        # Seek bar
        seek_frame = ttk.Frame(play_lf)
        seek_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=4)
        play_lf.columnconfigure(1, weight=1)

        self._seek_var = tk.DoubleVar(value=0.0)
        self._seek_scale = ttk.Scale(seek_frame, variable=self._seek_var,
                                     from_=0.0, to=100.0, orient="horizontal",
                                     command=self._play_seek)
        self._seek_scale.pack(fill="x", expand=True)

        # Progress label
        self._play_progress_var = tk.StringVar(value="00:00 / 00:00")
        ttk.Label(play_lf, textvariable=self._play_progress_var).grid(
            row=4, column=0, columnspan=3, sticky="w", padx=8, pady=2)

        # Checkboxes
        chk_frame = ttk.Frame(play_lf)
        chk_frame.grid(row=5, column=0, columnspan=3, sticky="w", padx=8, pady=2)

        self._feed_to_radar_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(chk_frame, text="Feed to radar",
                        variable=self._feed_to_radar_var).pack(side="left", padx=4)
        self._clear_on_stop_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(chk_frame, text="Clear tracks on stop",
                        variable=self._clear_on_stop_var).pack(side="left", padx=4)

        # ── LIBRARY section ──────────────────────────────────────────
        lib_lf = ttk.LabelFrame(outer, text="RECORDING LIBRARY")
        lib_lf.pack(fill="both", expand=True, padx=8, pady=6)

        lib_btn_frame = ttk.Frame(lib_lf)
        lib_btn_frame.pack(fill="x", padx=4, pady=4)
        ttk.Button(lib_btn_frame, text="\U0001f4c2 Open folder",
                   command=self._lib_open_folder).pack(side="left", padx=2)
        ttk.Button(lib_btn_frame, text="\U0001f504 Refresh",
                   command=self._lib_refresh).pack(side="left", padx=2)
        ttk.Button(lib_btn_frame, text="\U0001f5d1 Delete selected",
                   command=self._lib_delete_selected).pack(side="left", padx=2)

        # Treeview
        cols = ("Filename", "Date", "Duration", "Frames", "Size", "Mode")
        self._lib_tree = ttk.Treeview(lib_lf, columns=cols, show="headings", height=6)
        col_widths = (220, 140, 80, 80, 80, 70)
        for col, w in zip(cols, col_widths):
            self._lib_tree.heading(col, text=col)
            self._lib_tree.column(col, width=w, anchor="w")
        scroll_y = ttk.Scrollbar(lib_lf, orient="vertical",
                                 command=self._lib_tree.yview)
        self._lib_tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")
        self._lib_tree.pack(fill="both", expand=True, padx=4, pady=2)
        self._lib_tree.bind("<Double-1>", self._lib_double_click)

        # Initial library refresh
        self._lib_refresh()

    # ------------------------------------------------------------------
    # Recording helpers
    # ------------------------------------------------------------------
    def _rec_browse_folder(self):
        folder = filedialog.askdirectory(title="Select recording folder")
        if folder:
            self._rec_folder_var.set(folder)

    def _rec_start(self):
        if not self.feed._running:
            messagebox.showwarning(
                "Record",
                "Start an ADS-B feed first (connect on the Radar tab).")
            return
        folder   = self._rec_folder_var.get()
        filename = "navaids_" + time.strftime("%Y%m%d_%H%M%S") + ".adsbrec"
        path     = os.path.join(folder, filename)
        self._rec_fname_var.set(filename)
        self._recorder = ADSBRecorder(self._log)
        self._recorder.start(path, self.feed.mode)
        self.feed.recorder = self._recorder
        self._rec_poll()

    def _rec_stop(self):
        if self._recorder:
            self._recorder.stop()
            self.feed.recorder = None
            self._recorder = None
            self._rec_status_var.set("Stopped")
            self._lib_refresh()

    def _rec_poll(self):
        if not self._recorder or not self._recorder.recording:
            return
        dur_s    = int(self._recorder.duration)
        minutes  = dur_s // 60
        seconds  = dur_s % 60
        size_kb  = self._recorder.file_size // 1024
        frames   = self._recorder.frame_count
        self._rec_status_var.set(
            f"\u25cf Recording  |  Frames: {frames:,}  |  "
            f"Duration: {minutes:02d}:{seconds:02d}  |  Size: {size_kb} KB"
        )
        self.after(1000, self._rec_poll)

    # ------------------------------------------------------------------
    # Playback helpers
    # ------------------------------------------------------------------
    def _play_open_file(self):
        path = filedialog.askopenfilename(
            title="Open ADS-B Recording",
            filetypes=[("ADS-B Recording", "*.adsbrec"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            meta = self._replayer.load(path)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Error", f"Cannot load file:\n{exc}")
            return
        self._play_file_var.set(path)
        dur_s   = int(meta["duration"])
        minutes = dur_s // 60
        seconds = dur_s % 60
        start_dt = datetime.fromtimestamp(meta["start_ts"], tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        self._play_info_var.set(
            f"Feed: {meta['feed_mode']}  |  Frames: {meta['frame_count']:,}"
            f"  |  Duration: {minutes:02d}:{seconds:02d}"
            f"  |  Start: {start_dt}"
        )
        self._seek_scale.configure(to=max(meta["duration"], 1.0))

    def _play_start(self):
        if not self._replayer._path:
            messagebox.showwarning("Playback", "Open a recording file first.")
            return
        speed_label = self._speed_var.get()
        try:
            idx   = ADSBReplayer.SPEED_LABELS.index(speed_label)
            speed = ADSBReplayer.SPEEDS[idx]
        except ValueError:
            speed = 1.0
        self._replayer._feed_to_radar = self._feed_to_radar_var.get()
        self._replayer.start(
            self.feed, speed,
            on_progress=self._play_progress,
            on_complete=self._play_complete,
        )

    def _play_pause(self):
        self._replayer.pause()

    def _play_stop(self):
        self._replayer.stop()
        if self._clear_on_stop_var.get():
            with self.feed._lock:
                self.feed.tracks.clear()
        self._play_progress_var.set("00:00 / 00:00")

    def _play_seek(self, value: str):
        """Called by Scale widget; value is a string."""
        try:
            self._replayer.seek(float(value))
        except ValueError:
            pass

    def _play_speed_changed(self, _event=None):
        speed_label = self._speed_var.get()
        try:
            idx   = ADSBReplayer.SPEED_LABELS.index(speed_label)
            speed = ADSBReplayer.SPEEDS[idx]
        except ValueError:
            speed = 1.0
        self._replayer.set_speed(speed)

    def _play_progress(self, played: int, total: int,
                       current_ts: float, duration: float):
        """Called from replayer thread – marshal to UI thread."""
        def _update():
            cur_s  = int(current_ts)
            dur_s  = int(duration)
            cm, cs = cur_s // 60, cur_s % 60
            dm, ds = dur_s // 60, dur_s % 60
            self._play_progress_var.set(
                f"{cm:02d}:{cs:02d} / {dm:02d}:{ds:02d}"
                f"  ({played}/{total})"
            )
            if duration > 0:
                self._seek_var.set(current_ts)
        self.after(0, _update)

    def _play_complete(self):
        """Called from replayer thread when done."""
        def _update():
            self._play_progress_var.set("Replay complete")
            if self._clear_on_stop_var.get():
                with self.feed._lock:
                    self.feed.tracks.clear()
        self.after(0, _update)

    # ------------------------------------------------------------------
    # Library helpers
    # ------------------------------------------------------------------
    def _lib_refresh(self):
        self._lib_tree.delete(*self._lib_tree.get_children())
        folder = self._rec_folder_var.get()
        if not os.path.isdir(folder):
            return
        mode_names = ADSBReplayer._MODE_NAMES
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith(".adsbrec"):
                continue
            fpath = os.path.join(folder, fname)
            try:
                stat = os.stat(fpath)
                with open(fpath, "rb") as fh:
                    magic = fh.read(8)
                    if magic != REPLAY_MAGIC:
                        raise ValueError("Bad magic")
                    _version     = fh.read(2)
                    mode_idx_b   = fh.read(2)
                    start_ts_b   = fh.read(8)
                    fh.read(12)  # reserved
                    mode_idx  = struct.unpack("<H", mode_idx_b)[0]
                    start_ts  = struct.unpack("<d", start_ts_b)[0]
                    feed_mode = mode_names[mode_idx] if mode_idx < len(mode_names) else "?"
                    # Count frames quickly using shared helper
                    frame_count, last_rel = _scan_adsbrec_frames(fh)

                date_str = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M:%S")
                dur_s    = int(last_rel)
                dur_str  = f"{dur_s // 60:02d}:{dur_s % 60:02d}"
                size_str = f"{stat.st_size // 1024} KB"
                self._lib_tree.insert(
                    "", "end",
                    iid=fpath,
                    values=(fname, date_str, dur_str,
                            str(frame_count), size_str, feed_mode),
                )
            except (OSError, struct.error, ValueError) as exc:
                self._lib_tree.insert(
                    "", "end",
                    iid=fpath + "_err",
                    values=(fname, "ERROR", str(exc), "", "", ""),
                )

    def _lib_open_folder(self):
        folder = self._rec_folder_var.get()
        os.makedirs(folder, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(folder)   # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", folder])

    def _lib_delete_selected(self):
        selected = self._lib_tree.selection()
        if not selected:
            return
        if not messagebox.askyesno("Delete",
                                   f"Delete {len(selected)} file(s)?"):
            return
        for iid in selected:
            if iid.endswith("_err"):
                continue
            try:
                os.remove(iid)
            except OSError as exc:
                messagebox.showerror("Delete error", str(exc))
        self._lib_refresh()

    def _lib_double_click(self, _event):
        selected = self._lib_tree.selection()
        if not selected:
            return
        iid = selected[0]
        if iid.endswith("_err"):
            return
        path = iid
        try:
            meta = self._replayer.load(path)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Error", f"Cannot load file:\n{exc}")
            return
        self._play_file_var.set(path)
        dur_s   = int(meta["duration"])
        start_dt = datetime.fromtimestamp(
            meta["start_ts"], tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
        self._play_info_var.set(
            f"Feed: {meta['feed_mode']}  |  Frames: {meta['frame_count']:,}"
            f"  |  Duration: {dur_s // 60:02d}:{dur_s % 60:02d}"
            f"  |  Start: {start_dt}"
        )
        self._seek_scale.configure(to=max(meta["duration"], 1.0))
        # Switch to playback tab (notebook tab containing play_lf is this same tab)
        self._notebook.select(1)

    # ==================================================================
    # TAB: Log
    # ==================================================================
    def _tab_log(self):
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="\U0001f4cb Log")

        self._log_text = tk.Text(frame, state="disabled", wrap="none",
                                 bg="#1e1e1e", fg="#cccccc",
                                 font=("Courier", 9))
        sb_y = ttk.Scrollbar(frame, orient="vertical",
                              command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=sb_y.set)
        sb_y.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    app = NAVAIDSApp()
    app.mainloop()


if __name__ == "__main__":
    main()
