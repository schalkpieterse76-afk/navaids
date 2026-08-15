from __future__ import annotations

import csv
import io
import json
import math
import os
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    TK_OK = True
except Exception:
    tk = None
    ttk = None
    TK_OK = False

    class _MissingTkModule:
        def __getattr__(self, name):
            raise RuntimeError("tkinter is required to use the NAVAIDS desktop UI.")

    filedialog = _MissingTkModule()
    messagebox = _MissingTkModule()

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    MPL_OK = True
except Exception:
    FigureCanvasTkAgg = None
    Figure = None
    MPL_OK = False


# ─── Constants ────────────────────────────────────────────────────────────────

APP_TITLE = "NAVAIDS v7.0"
APP_VERSION = "7.0"
NOTAM_FILE = "navaids_notams.json"
VOR_TREND_FILE = "navaids_vor_trend.json"
THEME_BG = "#0d1b2a"
THEME_FG = "#e0e8f0"
THEME_ACCENT = "#1e90ff"
THEME_WARN = "#ff6b35"
THEME_OK = "#00c853"
THEME_ERR = "#ff1744"

VOR_STATIONS = ["FAJS", "FACT", "FAGG", "FAWK", "FABM", "FAPE", "FAEL"]

VOR_REPORT_FIELDS = [
    ("RF Power (W)", "power", "?PWR", "W"),
    ("VSWR", "vswr", "?VSWR", ""),
    ("Temperature (°C)", "temp", "?TEMP", "°C"),
    ("PSU Voltage (V)", "psu_v", "?PSUV", "V"),
    ("PSU Current (A)", "psu_i", "?PSUI", "A"),
    ("Ant Current (A)", "ant_i", "?ANTI", "A"),
    ("Monitor Power", "mon_power", "?MONPWR", ""),
    ("AM Depth (%)", "am_depth", "?AMDPTH", "%"),
    ("DPSK Level", "dpsk_lvl", "?DPSK", ""),
]

VOR_ALARM_THRESHOLDS = {
    "power": ("lt", 40.0),
    "vswr": ("gt", 1.5),
    "temp": ("gt", 70.0),
    "psu_v": ("lt", 22.0),
    "psu_i": ("gt", 5.0),
}

NAVAID_POSITIONS = {
    "FAJS": (22, 25),
    "FACT": (62, 226),
    "FAGG": (94, 112),
    "FAWK": (48, 338),
    "FABM": (70, 10),
    "FAPE": (108, 96),
    "FAEL": (128, 80),
}

WEATHER_COLOURS = {
    "LIGHT": "#00aa00",
    "MODERATE": "#aaaa00",
    "HEAVY": "#aa4400",
    "EXTREME": "#aa00aa",
}

TRACK_TYPES = ["B738", "A320", "E190", "B77W", "A359", "DH8D", "CRJ9", "B737"]


class WeatherCell:
    def __init__(self, rho_nm, theta_deg, width_nm, arc_deg, intensity, category):
        self.rho_nm = rho_nm
        self.theta_deg = theta_deg
        self.width_nm = width_nm
        self.arc_deg = arc_deg
        self.intensity = intensity
        self.category = category


class WeatherSimulator:
    def __init__(self, seed=42):
        self._seed = seed
        self._step = 0
        self._cells: list[WeatherCell] = []
        self._generate_base()

    def _generate_base(self):
        rng = random.Random(self._seed)
        self._base_cells = []
        for _ in range(rng.randint(15, 25)):
            rho = rng.uniform(10, 120)
            theta = rng.uniform(0, 360)
            width = rng.uniform(5, 20)
            arc = rng.uniform(10, 40)
            intensity = rng.random()
            if intensity < 0.25:
                cat = "LIGHT"
            elif intensity < 0.50:
                cat = "MODERATE"
            elif intensity < 0.75:
                cat = "HEAVY"
            else:
                cat = "EXTREME"
            self._base_cells.append(WeatherCell(rho, theta, width, arc, intensity, cat))

    def generate(self, range_nm) -> list[WeatherCell]:
        result = []
        drift_rho = self._step * 0.3
        drift_theta = self._step * 0.5
        for bc in self._base_cells:
            rho = bc.rho_nm + drift_rho
            theta = (bc.theta_deg + drift_theta) % 360
            if rho > range_nm * 1.2:
                continue
            cell = WeatherCell(rho, theta, bc.width_nm, bc.arc_deg, bc.intensity, bc.category)
            result.append(cell)
        return result

    def step(self):
        self._step += 1


class WeatherFeedManager:
    MODES = ["Simulated", "OpenWeatherMap (UDP)", "Local UDP"]

    def __init__(self):
        self.mode = "Simulated"
        self._sim = WeatherSimulator()
        self._running = False
        self._host = ""
        self._port = 0

    def start(self, mode, host="", port=0):
        self.mode = mode
        self._host = host
        self._port = port
        self._running = True

    def stop(self):
        self._running = False

    def get_cells(self, range_nm) -> list[WeatherCell]:
        if not self._running:
            return []
        if self.mode == "Simulated":
            return self._sim.generate(range_nm)
        return []

    @property
    def simulator(self) -> WeatherSimulator:
        return self._sim


class NAVAIDSApp:
    def __init__(self, root: tk.Tk):
        self._root = root
        self._root.title(APP_TITLE)
        self._root.configure(bg=THEME_BG)
        self._root.geometry("1280x800")
        self._root.minsize(1080, 720)

        self._notam_path = Path(NOTAM_FILE)
        self._trend_path = Path(VOR_TREND_FILE)

        self._vor_rpt_data: dict = {}
        self._vor_rpt_station = tk.StringVar(value=VOR_STATIONS[0])
        self._vor_rpt_tech = tk.StringVar(value="Technician")
        self._vor_rpt_widgets: dict[str, dict[str, object]] = {}
        self._vor_query_running = False

        self._vor_trend_records: list[dict] = []
        self._trend_param_vars: dict[str, tk.BooleanVar] = {}
        self._trend_normalise_var = tk.BooleanVar(value=False)
        self._trend_auto_var = tk.BooleanVar(value=False)
        self._trend_interval_var = tk.StringVar(value="5")
        self._trend_auto_after_id = None
        self._trend_canvas = None
        self._trend_figure = None
        self._trend_ax = None

        self._radar_running = tk.BooleanVar(value=False)
        self._radar_range_nm = tk.DoubleVar(value=150.0)
        self._radar_show_weather = tk.BooleanVar(value=True)
        self._radar_show_navaids = tk.BooleanVar(value=True)
        self._radar_show_tracks = tk.BooleanVar(value=True)
        self._radar_rotation = 0.0
        self._radar_sweep_angle = 0.0
        self._radar_after_id = None
        self._radar_frame_count = 0
        self._weather_feed = WeatherFeedManager()
        self._weather_src_var = tk.StringVar(value="Simulated")
        self._weather_intensity_var = tk.StringVar(value="ALL")
        self._weather_anim_fast = False
        self._weather_cache = []
        self._weather_cache_range = -1.0
        self._weather_cache_size = (-1, -1)

        self._notams: list[dict] = []
        self._notam_filter = tk.StringVar()

        self._tracks = self._init_tracks()

        self._top_clock_var = tk.StringVar(value="")
        self._top_info_var = tk.StringVar(value="Ready")
        self._bottom_status_var = tk.StringVar(value="System initialised.")
        self._radar_status_var = tk.StringVar(value="Radar standby.")
        self._trend_status_var = tk.StringVar(value="No snapshots loaded.")

        self._load_notams()
        self._load_vor_trend()
        self._configure_styles()
        self._build_ui()
        self._start_status_clock()

    # ─── Persistence ────────────────────────────────────────────────────────

    def _load_notams(self):
        if not self._notam_path.exists():
            self._notams = []
            return
        try:
            self._notams = json.loads(self._notam_path.read_text(encoding="utf-8"))
            if not isinstance(self._notams, list):
                self._notams = []
        except Exception:
            self._notams = []

    def _save_notams(self):
        try:
            text = json.dumps(self._notams, indent=2, ensure_ascii=False)
            self._notam_path.write_text(text, encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Save Error", "Unable to save NOTAM data.\n\n" + str(exc))

    def _load_vor_trend(self):
        if not self._trend_path.exists():
            self._vor_trend_records = []
            return
        try:
            self._vor_trend_records = json.loads(self._trend_path.read_text(encoding="utf-8"))
            if not isinstance(self._vor_trend_records, list):
                self._vor_trend_records = []
        except Exception:
            self._vor_trend_records = []

    def _save_vor_trend(self):
        try:
            text = json.dumps(self._vor_trend_records, indent=2, ensure_ascii=False)
            self._trend_path.write_text(text, encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Save Error", "Unable to save VOR trend data.\n\n" + str(exc))

    # ─── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _try_float(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        filtered = []
        dot_seen = False
        minus_seen = False
        for idx, ch in enumerate(text):
            if ch.isdigit():
                filtered.append(ch)
            elif ch == "." and not dot_seen:
                filtered.append(ch)
                dot_seen = True
            elif ch == "-" and not minus_seen and idx == 0:
                filtered.append(ch)
                minus_seen = True
        cleaned = "".join(filtered)
        if cleaned in {"", "-", ".", "-."}:
            return None
        try:
            return float(cleaned)
        except Exception:
            return None

    def _init_tracks(self):
        rng = random.Random(777)
        tracks = []
        prefixes = ["SA", "MN", "AX", "KT", "VA", "NL", "ZA", "QF"]
        for idx in range(8):
            prefix = prefixes[idx % len(prefixes)]
            callsign = prefix + str(rng.randint(100, 999))
            track = {
                "callsign": callsign,
                "rho": rng.uniform(15.0, 120.0),
                "theta": rng.uniform(0.0, 360.0),
                "alt": rng.choice([9000, 13000, 18500, 24000, 31000, 35000, 39000]),
                "speed": rng.randint(210, 480),
                "hdg": rng.uniform(0.0, 360.0),
                "type": rng.choice(TRACK_TYPES),
            }
            tracks.append(track)
        return tracks

    def _configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=THEME_BG, foreground=THEME_FG, fieldbackground="#10243a")
        style.configure("TFrame", background=THEME_BG)
        style.configure("TLabelframe", background=THEME_BG, foreground=THEME_FG)
        style.configure("TLabelframe.Label", background=THEME_BG, foreground=THEME_FG)
        style.configure("TLabel", background=THEME_BG, foreground=THEME_FG)
        style.configure(
            "TButton",
            background="#17314b",
            foreground=THEME_FG,
            borderwidth=1,
            focuscolor=THEME_BG,
            padding=6,
        )
        style.map("TButton", background=[("active", "#22476a"), ("pressed", "#14304b")])
        style.configure("TCheckbutton", background=THEME_BG, foreground=THEME_FG)
        style.configure("TRadiobutton", background=THEME_BG, foreground=THEME_FG)
        style.configure("TNotebook", background=THEME_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background="#17314b", foreground=THEME_FG, padding=(12, 6))
        style.map("TNotebook.Tab", background=[("selected", "#24476a")], foreground=[("selected", "#ffffff")])
        style.configure("Treeview", background="#11253b", foreground=THEME_FG, fieldbackground="#11253b")
        style.configure("Treeview.Heading", background="#17314b", foreground=THEME_FG)
        style.map("Treeview", background=[("selected", "#285f91")], foreground=[("selected", "#ffffff")])
        style.configure("TCombobox", fieldbackground="#10243a", background="#17314b", foreground=THEME_FG)
        style.configure("TSpinbox", fieldbackground="#10243a", foreground=THEME_FG)
        style.configure("Horizontal.TScale", background=THEME_BG)
        style.configure("Accent.TButton", background=THEME_ACCENT, foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#4aa5ff"), ("pressed", "#1975d1")])

    @staticmethod
    def _polar_to_xy(rho_nm, theta_deg):
        radians_theta = math.radians(theta_deg)
        x = rho_nm * math.sin(radians_theta)
        y = rho_nm * math.cos(radians_theta)
        return x, y

    @staticmethod
    def _xy_to_polar(x, y):
        rho = math.sqrt(x * x + y * y)
        theta = (math.degrees(math.atan2(x, y)) + 360.0) % 360.0
        return rho, theta

    def _overall_vor_status(self, data: dict | None = None):
        src = data if data is not None else self._vor_rpt_data
        for _, key, _, _ in VOR_REPORT_FIELDS:
            value = self._try_float(src.get(key))
            if value is None:
                continue
            if self._is_alarm(key, value):
                return "ALARM"
        return "OK" if src else "NO DATA"

    def _is_alarm(self, key, value):
        if key not in VOR_ALARM_THRESHOLDS:
            return False
        op, threshold = VOR_ALARM_THRESHOLDS[key]
        if op == "lt":
            return value < threshold
        return value > threshold

    def _format_value(self, value, unit=""):
        if value is None:
            return "—"
        if isinstance(value, int):
            text = str(value)
        else:
            text = "{:.2f}".format(float(value))
            if text.endswith("00"):
                text = "{:.0f}".format(float(value))
            elif text.endswith("0"):
                text = "{:.1f}".format(float(value))
        if unit:
            return text + " " + unit
        return text

    # ─── UI shell ───────────────────────────────────────────────────────────

    def _build_ui(self):
        top = tk.Frame(self._root, bg="#08131f", height=34)
        top.pack(side=tk.TOP, fill=tk.X)

        title_lbl = tk.Label(
            top,
            text=APP_TITLE,
            bg="#08131f",
            fg=THEME_FG,
            font=("Segoe UI", 12, "bold"),
            padx=12,
        )
        title_lbl.pack(side=tk.LEFT)

        info_lbl = tk.Label(top, textvariable=self._top_info_var, bg="#08131f", fg="#9cb3c9")
        info_lbl.pack(side=tk.LEFT, padx=(4, 0))

        clock_lbl = tk.Label(top, textvariable=self._top_clock_var, bg="#08131f", fg=THEME_ACCENT, padx=12)
        clock_lbl.pack(side=tk.RIGHT)

        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._tabs: dict[str, ttk.Frame] = {}
        self._tabs["radar"] = ttk.Frame(self._notebook)
        self._tabs["vor_report"] = ttk.Frame(self._notebook)
        self._tabs["notams"] = ttk.Frame(self._notebook)
        self._tabs["vor_trend"] = ttk.Frame(self._notebook)
        self._tabs["about"] = ttk.Frame(self._notebook)

        self._notebook.add(self._tabs["radar"], text="🛩 Radar")
        self._notebook.add(self._tabs["vor_report"], text="📡 VOR Report")
        self._notebook.add(self._tabs["notams"], text="📋 NOTAMs")
        self._notebook.add(self._tabs["vor_trend"], text="📈 VOR Trend")
        self._notebook.add(self._tabs["about"], text="ℹ About")

        self._tab_radar()
        self._tab_vor_report()
        self._tab_notams()
        self._tab_vor_trend()
        self._tab_about()

        bottom = tk.Frame(self._root, bg="#08131f", height=28)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        bottom_lbl = tk.Label(bottom, textvariable=self._bottom_status_var, bg="#08131f", fg="#a9bfd2", anchor="w")
        bottom_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=3)

    # ─── Radar tab ──────────────────────────────────────────────────────────

    def _tab_radar(self):
        parent = self._tabs["radar"]

        controls = ttk.Frame(parent)
        controls.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Button(controls, text="▶ Start", style="Accent.TButton", command=self._radar_start).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="⏹ Stop", command=self._radar_stop).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Checkbutton(
            controls,
            text="🛩 Tracks",
            variable=self._radar_show_tracks,
            command=self._radar_redraw,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(
            controls,
            text="📡 NAVAIDs",
            variable=self._radar_show_navaids,
            command=self._radar_redraw,
        ).pack(side=tk.LEFT, padx=4)

        ttk.Separator(controls, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Checkbutton(
            controls,
            text="🌧 Weather",
            variable=self._radar_show_weather,
            command=self._on_weather_toggle,
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Label(controls, text="Src:").pack(side=tk.LEFT, padx=(8, 2))
        weather_src = ttk.Combobox(
            controls,
            textvariable=self._weather_src_var,
            values=WeatherFeedManager.MODES,
            state="readonly",
            width=20,
        )
        weather_src.pack(side=tk.LEFT, padx=(0, 8))
        weather_src.bind("<<ComboboxSelected>>", lambda _e: self._on_weather_source_change())

        ttk.Label(controls, text="Intensity:").pack(side=tk.LEFT, padx=(0, 2))
        weather_intensity = ttk.Combobox(
            controls,
            textvariable=self._weather_intensity_var,
            values=["ALL", "MODERATE+", "HEAVY+", "EXTREME only"],
            state="readonly",
            width=14,
        )
        weather_intensity.pack(side=tk.LEFT, padx=(0, 10))
        weather_intensity.bind("<<ComboboxSelected>>", lambda _e: self._radar_redraw())

        ttk.Label(controls, text="Range (NM)").pack(side=tk.LEFT, padx=(6, 6))
        rng_scale = ttk.Scale(
            controls,
            from_=25.0,
            to=200.0,
            variable=self._radar_range_nm,
            orient=tk.HORIZONTAL,
            command=lambda _v: self._radar_redraw(),
        )
        rng_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        rng_spin = ttk.Spinbox(
            controls,
            from_=25.0,
            to=200.0,
            increment=5.0,
            textvariable=self._radar_range_nm,
            width=8,
            command=self._radar_redraw,
        )
        rng_spin.pack(side=tk.LEFT)
        rng_spin.bind("<Return>", lambda _e: self._radar_redraw())

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        canvas_frame = ttk.Frame(main)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._radar_canvas = tk.Canvas(
            canvas_frame,
            bg=THEME_BG,
            highlightthickness=1,
            highlightbackground="#21435f",
        )
        self._radar_canvas.pack(fill=tk.BOTH, expand=True)
        self._radar_canvas.bind("<Configure>", self._radar_canvas_resize)

        sidebar = ttk.Frame(main, width=330)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text="Active Tracks", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))

        cols = ("callsign", "range", "bearing", "alt", "type")
        self._track_tree = ttk.Treeview(sidebar, columns=cols, show="headings", height=14)
        self._track_tree.heading("callsign", text="Callsign")
        self._track_tree.heading("range", text="Range")
        self._track_tree.heading("bearing", text="Bearing")
        self._track_tree.heading("alt", text="Alt")
        self._track_tree.heading("type", text="Type")
        self._track_tree.column("callsign", width=92, anchor="w")
        self._track_tree.column("range", width=58, anchor="center")
        self._track_tree.column("bearing", width=62, anchor="center")
        self._track_tree.column("alt", width=70, anchor="e")
        self._track_tree.column("type", width=55, anchor="center")
        self._track_tree.pack(fill=tk.X)

        self._weather_legend_frame = ttk.Frame(sidebar)
        self._weather_legend_frame.pack(fill=tk.X, pady=(12, 8))
        ttk.Label(
            self._weather_legend_frame,
            text="─ Weather Legend ─",
            foreground="#a6bfd6",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        for name, colour in [
            ("LIGHT", WEATHER_COLOURS["LIGHT"]),
            ("MODERATE", WEATHER_COLOURS["MODERATE"]),
            ("HEAVY", WEATHER_COLOURS["HEAVY"]),
            ("EXTREME", WEATHER_COLOURS["EXTREME"]),
        ]:
            row = ttk.Frame(self._weather_legend_frame)
            row.pack(fill=tk.X, pady=1)
            swatch = tk.Label(row, text="■", bg=THEME_BG, fg=colour, font=("Segoe UI", 11, "bold"))
            swatch.pack(side=tk.LEFT)
            ttk.Label(row, text=name).pack(side=tk.LEFT, padx=(6, 0))

        anim_row = ttk.Frame(sidebar)
        anim_row.pack(fill=tk.X, pady=(8, 8))
        ttk.Button(anim_row, text="🌧 Animate", command=self._weather_anim_start).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(anim_row, text="⏹ Stop", command=self._weather_anim_stop).pack(side=tk.LEFT)

        self._radar_status_lbl = tk.Label(
            parent,
            textvariable=self._radar_status_var,
            bg="#08131f",
            fg="#a9bfd2",
            anchor="w",
            padx=10,
            pady=6,
        )
        self._radar_status_lbl.pack(fill=tk.X, padx=8, pady=(0, 8))

        self._update_weather_legend_visibility()
        self._radar_redraw()

    def _radar_canvas_resize(self, _event=None):
        self._radar_redraw()

    def _radar_start(self):
        if self._radar_running.get():
            return
        self._radar_running.set(True)
        self._weather_feed.start(self._weather_src_var.get())
        self._radar_status_var.set("Radar running.")
        self._bottom_status_var.set("Radar scan started.")
        self._top_info_var.set("Monitoring live radar simulation")
        self._radar_loop()

    def _radar_stop(self):
        self._radar_running.set(False)
        self._weather_feed.stop()
        if self._radar_after_id is not None:
            self._root.after_cancel(self._radar_after_id)
            self._radar_after_id = None
        self._radar_status_var.set("Radar stopped.")
        self._bottom_status_var.set("Radar scan stopped.")
        self._top_info_var.set("Standby")
        self._radar_redraw()

    def _on_weather_toggle(self):
        self._update_weather_legend_visibility()
        self._radar_redraw()

    def _on_weather_source_change(self):
        if self._radar_running.get():
            self._weather_feed.start(self._weather_src_var.get())
        self._radar_redraw()

    def _update_weather_legend_visibility(self):
        if self._radar_show_weather.get():
            self._weather_legend_frame.pack(fill=tk.X, pady=(12, 8))
        else:
            self._weather_legend_frame.pack_forget()

    def _radar_loop(self):
        self._radar_render()
        if not self._radar_running.get():
            self._radar_after_id = None
            return
        self._radar_after_id = self._root.after(100, self._radar_loop)

    def _radar_redraw(self):
        self._radar_render()

    def _radar_render(self):
        c = self._radar_canvas
        if c is None:
            return
        c.delete("all")
        width = max(c.winfo_width(), 10)
        height = max(c.winfo_height(), 10)
        cx = width // 2
        cy = height // 2
        radius = max(min(width, height) // 2 - 20, 20)

        self._radar_draw_grid(c, cx, cy, radius)

        if self._radar_show_navaids.get():
            self._radar_draw_navaids(c, cx, cy, radius)

        if self._radar_show_weather.get():
            self._radar_draw_weather(c, cx, cy, radius)
            if self._weather_anim_fast:
                self._weather_feed.simulator.step()
            elif self._radar_frame_count % 10 == 0:
                self._weather_feed.simulator.step()

        self._radar_draw_sweep(c, cx, cy, radius)

        if self._radar_show_tracks.get():
            self._radar_update_tracks()
            self._radar_draw_tracks(c, cx, cy, radius)

        self._refresh_track_tree()
        self._radar_frame_count += 1

    def _radar_draw_grid(self, canvas, cx, cy, radius):
        canvas.create_rectangle(0, 0, canvas.winfo_width(), canvas.winfo_height(), fill=THEME_BG, outline="")
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline="#2b5878", width=2)

        range_nm = float(self._radar_range_nm.get())
        for fraction in (0.25, 0.5, 0.75, 1.0):
            rr = radius * fraction
            canvas.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline="#1d425f", width=1)
            label_nm = int(range_nm * fraction)
            canvas.create_text(cx + 8, cy - rr, text=str(label_nm) + " NM", fill="#6f99b9", anchor="w", font=("Segoe UI", 9))

        canvas.create_line(cx - radius, cy, cx + radius, cy, fill="#17314b")
        canvas.create_line(cx, cy - radius, cx, cy + radius, fill="#17314b")

        canvas.create_text(cx, cy - radius - 12, text="N", fill=THEME_FG, font=("Segoe UI", 11, "bold"))
        canvas.create_text(cx + radius + 12, cy, text="E", fill=THEME_FG, font=("Segoe UI", 11, "bold"))
        canvas.create_text(cx, cy + radius + 12, text="S", fill=THEME_FG, font=("Segoe UI", 11, "bold"))
        canvas.create_text(cx - radius - 12, cy, text="W", fill=THEME_FG, font=("Segoe UI", 11, "bold"))

    def _radar_draw_navaids(self, canvas, cx, cy, radius):
        range_nm = float(self._radar_range_nm.get())
        for station, (rho_nm, theta_deg) in NAVAID_POSITIONS.items():
            if rho_nm > range_nm:
                continue
            scale = radius * (rho_nm / range_nm)
            x = cx + scale * math.sin(math.radians(theta_deg))
            y = cy - scale * math.cos(math.radians(theta_deg))
            points = [x, y - 7, x - 6, y + 5, x + 6, y + 5]
            canvas.create_polygon(points, fill="#66e3ff", outline="#00d8ff")
            canvas.create_text(x + 10, y - 10, text=station, fill="#9be9ff", anchor="w", font=("Consolas", 9))

    def _weather_filter_allows(self, cell: WeatherCell):
        mode = self._weather_intensity_var.get()
        if mode == "ALL":
            return True
        if mode == "MODERATE+":
            return cell.category in {"MODERATE", "HEAVY", "EXTREME"}
        if mode == "HEAVY+":
            return cell.category in {"HEAVY", "EXTREME"}
        if mode == "EXTREME only":
            return cell.category == "EXTREME"
        return True

    def _radar_draw_weather(self, c, cx, cy, r):
        range_nm = float(self._radar_range_nm.get())
        cells = self._weather_feed.get_cells(range_nm)
        self._weather_cache = cells
        self._weather_cache_range = range_nm
        self._weather_cache_size = (c.winfo_width(), c.winfo_height())

        for cell in cells:
            if not self._weather_filter_allows(cell):
                continue
            colour = WEATHER_COLOURS.get(cell.category, "#777777")
            r_outer = r * (cell.rho_nm / range_nm)
            band = max(4.0, r * (cell.width_nm / range_nm))
            bbox = (
                cx - r_outer,
                cy - r_outer,
                cx + r_outer,
                cy + r_outer,
            )
            start_angle = 90.0 - cell.theta_deg - (cell.arc_deg / 2.0)
            c.create_arc(
                bbox,
                start=start_angle,
                extent=cell.arc_deg,
                style="pieslice",
                fill=colour,
                stipple="gray50",
                outline="",
            )
            inner = max(r_outer - band, 0)
            if inner > 0:
                c.create_arc(
                    cx - inner,
                    cy - inner,
                    cx + inner,
                    cy + inner,
                    start=start_angle,
                    extent=cell.arc_deg,
                    style="pieslice",
                    fill=THEME_BG,
                    outline="",
                )

    def _radar_draw_sweep(self, canvas, cx, cy, radius):
        angle = self._radar_sweep_angle % 360.0
        x = cx + radius * math.sin(math.radians(angle))
        y = cy - radius * math.cos(math.radians(angle))
        canvas.create_line(cx, cy, x, y, fill="#00ff95", width=2)
        glow_angle = angle - 3.0
        x2 = cx + radius * math.sin(math.radians(glow_angle))
        y2 = cy - radius * math.cos(math.radians(glow_angle))
        canvas.create_line(cx, cy, x2, y2, fill="#00b96d")
        self._radar_sweep_angle = (self._radar_sweep_angle + 3.0) % 360.0

    def _radar_update_tracks(self):
        dt_seconds = 0.1
        range_nm = float(self._radar_range_nm.get())
        for idx, track in enumerate(self._tracks):
            x, y = self._polar_to_xy(track["rho"], track["theta"])
            distance_nm = track["speed"] * dt_seconds / 3600.0
            hdg = math.radians(track["hdg"])
            x += distance_nm * math.sin(hdg)
            y += distance_nm * math.cos(hdg)
            rho, theta = self._xy_to_polar(x, y)
            if rho > range_nm * 1.05:
                theta = (theta + 180.0) % 360.0
                track["hdg"] = (track["hdg"] + 170.0 + idx * 3.0) % 360.0
                rho = max(range_nm * 0.85, 10.0)
            else:
                track["hdg"] = (track["hdg"] + math.sin(time.time() + idx) * 0.15) % 360.0
            track["rho"] = rho
            track["theta"] = theta

    def _radar_draw_tracks(self, canvas, cx, cy, radius):
        range_nm = float(self._radar_range_nm.get())
        for track in self._tracks:
            if track["rho"] > range_nm:
                continue
            rr = radius * (track["rho"] / range_nm)
            x = cx + rr * math.sin(math.radians(track["theta"]))
            y = cy - rr * math.cos(math.radians(track["theta"]))
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#f2ff66", outline="")
            hdg = math.radians(track["hdg"])
            hx = x + 14 * math.sin(hdg)
            hy = y - 14 * math.cos(hdg)
            canvas.create_line(x, y, hx, hy, fill="#f2ff66", width=1)
            label = "{} {}ft".format(track["callsign"], track["alt"])
            canvas.create_text(x + 8, y - 8, text=label, fill="#fff5a6", anchor="w", font=("Consolas", 8))

    def _refresh_track_tree(self):
        tree = self._track_tree
        for item in tree.get_children():
            tree.delete(item)
        rows = sorted(self._tracks, key=lambda item: item["rho"])
        for track in rows:
            values = (
                track["callsign"],
                "{:.0f}".format(track["rho"]),
                "{:03.0f}°".format(track["theta"]),
                "{:,}".format(track["alt"]),
                track["type"],
            )
            tree.insert("", tk.END, values=values)

    # ─── VOR report tab ─────────────────────────────────────────────────────

    def _tab_vor_report(self):
        parent = self._tabs["vor_report"]

        top = ttk.Frame(parent)
        top.pack(fill=tk.X, padx=12, pady=(12, 6))

        ttk.Label(top, text="Station").pack(side=tk.LEFT)
        station_box = ttk.Combobox(
            top,
            textvariable=self._vor_rpt_station,
            values=VOR_STATIONS,
            state="readonly",
            width=10,
        )
        station_box.pack(side=tk.LEFT, padx=(6, 18))

        ttk.Label(top, text="Technician").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self._vor_rpt_tech, width=24).pack(side=tk.LEFT, padx=(6, 18))

        ttk.Button(top, text="📡 Query Device", style="Accent.TButton", command=self._vor_rpt_query).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top, text="🖨 Print Report", command=self._vor_rpt_print).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top, text="📸 Quick Snapshot", command=self._trend_snapshot).pack(side=tk.LEFT)

        info = ttk.LabelFrame(parent, text="VOR Health Report")
        info.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        hdr = ttk.Frame(info)
        hdr.pack(fill=tk.X, padx=10, pady=(10, 6))
        ttk.Label(hdr, text="Station:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self._vor_station_lbl = ttk.Label(hdr, textvariable=self._vor_rpt_station)
        self._vor_station_lbl.grid(row=0, column=1, sticky="w", padx=(6, 20))
        ttk.Label(hdr, text="Technician:", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, sticky="w")
        self._vor_tech_lbl = ttk.Label(hdr, textvariable=self._vor_rpt_tech)
        self._vor_tech_lbl.grid(row=0, column=3, sticky="w", padx=(6, 20))
        ttk.Label(hdr, text="Status:", font=("Segoe UI", 10, "bold")).grid(row=0, column=4, sticky="w")
        self._vor_status_text = tk.StringVar(value="NO DATA")
        self._vor_status_badge = tk.Label(hdr, textvariable=self._vor_status_text, bg=THEME_BG, fg=THEME_WARN, font=("Segoe UI", 10, "bold"))
        self._vor_status_badge.grid(row=0, column=5, sticky="w", padx=(6, 0))

        grid = ttk.Frame(info)
        grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for col in range(4):
            grid.grid_columnconfigure(col, weight=1)

        for idx, (label, key, command, unit) in enumerate(VOR_REPORT_FIELDS):
            row = idx // 2
            col_block = (idx % 2) * 2
            box = ttk.Frame(grid)
            box.grid(row=row, column=col_block, columnspan=2, sticky="nsew", padx=8, pady=8)

            ttk.Label(box, text=label, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
            ttk.Label(box, text=command, foreground="#7fa6c5").grid(row=1, column=0, sticky="w", pady=(2, 0))

            value_var = tk.StringVar(value="—")
            value_lbl = ttk.Label(box, textvariable=value_var, font=("Consolas", 14, "bold"), foreground="#ffffff")
            value_lbl.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 4))

            status_lbl = tk.Label(box, text="●", bg=THEME_BG, fg="#7f8c99", font=("Segoe UI", 12, "bold"))
            status_lbl.grid(row=0, column=2, rowspan=2, sticky="e", padx=(4, 0))

            self._vor_rpt_widgets[key] = {
                "value_var": value_var,
                "unit": unit,
                "status": status_lbl,
            }

        self._vor_rpt_refresh_fields()

    def _vor_rpt_query(self, callback=None):
        if self._vor_query_running:
            self._bottom_status_var.set("A VOR query is already in progress.")
            return

        station = self._vor_rpt_station.get()
        self._vor_query_running = True
        self._bottom_status_var.set("Querying VOR device at " + station + " ...")
        self._top_info_var.set("Querying " + station)

        def worker():
            time.sleep(0.5)
            seed_base = sum(ord(ch) for ch in station)
            time_bucket = int(time.time() // 30)
            rng = random.Random(seed_base + time_bucket)
            result = {
                "station": station,
                "tech": self._vor_rpt_tech.get().strip() or "Technician",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "power": round(rng.uniform(38.0, 55.0), 2),
                "vswr": round(rng.uniform(1.05, 1.72), 2),
                "temp": round(rng.uniform(34.0, 78.0), 2),
                "psu_v": round(rng.uniform(21.0, 25.5), 2),
                "psu_i": round(rng.uniform(2.1, 5.8), 2),
                "ant_i": round(rng.uniform(0.9, 2.2), 2),
                "mon_power": round(rng.uniform(0.82, 1.08), 2),
                "am_depth": round(rng.uniform(87.0, 98.0), 2),
                "dpsk_lvl": round(rng.uniform(0.72, 1.12), 2),
            }
            self._root.after(0, lambda: self._vor_rpt_query_complete(result, callback))

        threading.Thread(target=worker, daemon=True).start()

    def _vor_rpt_query_complete(self, result, callback=None):
        self._vor_query_running = False
        self._vor_rpt_data = result
        self._vor_rpt_refresh_fields()
        status = self._overall_vor_status()
        msg = "VOR query complete for " + result.get("station", "") + " (" + status + ")"
        self._bottom_status_var.set(msg)
        self._top_info_var.set("Latest device query complete")
        if callable(callback):
            callback()

    def _vor_rpt_refresh_fields(self):
        status = self._overall_vor_status()
        self._vor_status_text.set(status)
        self._vor_status_badge.configure(fg=THEME_OK if status == "OK" else THEME_ERR if status == "ALARM" else THEME_WARN)

        if self._vor_rpt_data:
            if self._vor_rpt_data.get("station"):
                self._vor_rpt_station.set(self._vor_rpt_data.get("station"))
            tech = self._vor_rpt_data.get("tech")
            if tech:
                self._vor_rpt_tech.set(tech)

        for _, key, _, _ in VOR_REPORT_FIELDS:
            widget_meta = self._vor_rpt_widgets.get(key, {})
            value_var = widget_meta.get("value_var")
            unit = widget_meta.get("unit", "")
            status_lbl = widget_meta.get("status")
            raw_value = self._vor_rpt_data.get(key)
            parsed = self._try_float(raw_value)
            display = self._format_value(parsed, unit)
            if isinstance(value_var, tk.StringVar):
                value_var.set(display)
            if isinstance(status_lbl, tk.Label):
                if parsed is None:
                    status_lbl.configure(text="●", fg="#7f8c99")
                elif self._is_alarm(key, parsed):
                    status_lbl.configure(text="●", fg=THEME_ERR)
                else:
                    status_lbl.configure(text="●", fg=THEME_OK)

    def _vor_rpt_make_text(self):
        data = self._vor_rpt_data or {}
        output = io.StringIO()
        output.write(APP_TITLE + " VOR Health Report\n")
        output.write("=" * 40 + "\n")
        output.write("Timestamp : " + data.get("timestamp", datetime.now().isoformat(timespec="seconds")) + "\n")
        output.write("Station   : " + self._vor_rpt_station.get() + "\n")
        output.write("Technician: " + self._vor_rpt_tech.get() + "\n")
        output.write("Status    : " + self._overall_vor_status(data) + "\n")
        output.write("\nParameters\n")
        output.write("-" * 40 + "\n")
        for label, key, command, unit in VOR_REPORT_FIELDS:
            value = self._format_value(self._try_float(data.get(key)), unit)
            line = "{:<20} {:>10}   {}\n".format(label, value, command)
            output.write(line)
        return output.getvalue()

    def _vor_rpt_print(self):
        report_text = self._vor_rpt_make_text()
        path = filedialog.asksaveasfilename(
            title="Save Report",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile="vor_report_" + self._vor_rpt_station.get().lower() + ".txt",
        )
        if not path:
            return
        try:
            Path(path).write_text(report_text, encoding="utf-8")
            self._bottom_status_var.set("Saved VOR report to " + path)
        except Exception as exc:
            messagebox.showerror("Save Error", "Unable to save report.\n\n" + str(exc))

    # ─── NOTAM tab ──────────────────────────────────────────────────────────

    def _tab_notams(self):
        parent = self._tabs["notams"]

        top = ttk.Frame(parent)
        top.pack(fill=tk.X, padx=12, pady=(12, 6))

        ttk.Label(top, text="Filter").pack(side=tk.LEFT)
        entry = ttk.Entry(top, textvariable=self._notam_filter, width=36)
        entry.pack(side=tk.LEFT, padx=(6, 6))
        entry.bind("<Return>", lambda _e: self._notam_refresh_tree())
        ttk.Button(top, text="Apply", command=self._notam_refresh_tree).pack(side=tk.LEFT)

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        cols = ("id", "icao", "type", "effective", "expiry", "summary")
        self._notam_tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        headings = {
            "id": "NOTAM ID",
            "icao": "ICAO",
            "type": "Type",
            "effective": "Effective",
            "expiry": "Expiry",
            "summary": "Summary",
        }
        widths = {"id": 120, "icao": 80, "type": 90, "effective": 145, "expiry": 145, "summary": 420}
        for col in cols:
            self._notam_tree.heading(col, text=headings[col])
            self._notam_tree.column(col, width=widths[col], anchor="w")
        self._notam_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._notam_tree.bind("<Double-1>", lambda _e: self._notam_edit())

        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._notam_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._notam_tree.configure(yscrollcommand=sb.set)

        btns = ttk.Frame(parent)
        btns.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(btns, text="Add", style="Accent.TButton", command=self._notam_add).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btns, text="Edit", command=self._notam_edit).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btns, text="Delete", command=self._notam_delete).pack(side=tk.LEFT)

        self._notam_refresh_tree()

    def _notam_filtered_records(self):
        query = self._notam_filter.get().strip().lower()
        if not query:
            return list(self._notams)
        result = []
        for item in self._notams:
            haystack = " ".join(
                [
                    str(item.get("id", "")),
                    str(item.get("icao", "")),
                    str(item.get("type", "")),
                    str(item.get("effective", "")),
                    str(item.get("expiry", "")),
                    str(item.get("summary", "")),
                ]
            ).lower()
            if query in haystack:
                result.append(item)
        return result

    def _notam_refresh_tree(self):
        for row in self._notam_tree.get_children():
            self._notam_tree.delete(row)
        filtered = self._notam_filtered_records()
        for idx, item in enumerate(filtered):
            values = (
                item.get("id", ""),
                item.get("icao", ""),
                item.get("type", ""),
                item.get("effective", ""),
                item.get("expiry", ""),
                item.get("summary", ""),
            )
            self._notam_tree.insert("", tk.END, iid="notam-" + str(idx), values=values)
        self._bottom_status_var.set("Loaded " + str(len(filtered)) + " NOTAM entries.")

    def _notam_add(self):
        self._notam_open_dialog()

    def _notam_edit(self):
        selected = self._notam_tree.selection()
        if not selected:
            messagebox.showinfo("Edit NOTAM", "Please select a NOTAM entry to edit.")
            return
        values = self._notam_tree.item(selected[0], "values")
        notam_id = values[0]
        record = None
        for item in self._notams:
            if item.get("id") == notam_id:
                record = item
                break
        if record is None:
            messagebox.showwarning("Edit NOTAM", "Unable to resolve the selected NOTAM.")
            return
        self._notam_open_dialog(record)

    def _notam_delete(self):
        selected = self._notam_tree.selection()
        if not selected:
            messagebox.showinfo("Delete NOTAM", "Please select a NOTAM entry to delete.")
            return
        values = self._notam_tree.item(selected[0], "values")
        notam_id = values[0]
        if not messagebox.askyesno("Delete NOTAM", "Delete NOTAM " + str(notam_id) + "?"):
            return
        self._notams = [item for item in self._notams if item.get("id") != notam_id]
        self._save_notams()
        self._notam_refresh_tree()

    def _notam_open_dialog(self, record=None):
        dialog = tk.Toplevel(self._root)
        dialog.title("NOTAM Editor")
        dialog.configure(bg=THEME_BG)
        dialog.transient(self._root)
        dialog.grab_set()
        dialog.resizable(False, False)

        fields = {
            "id": tk.StringVar(value="" if record is None else str(record.get("id", ""))),
            "icao": tk.StringVar(value="" if record is None else str(record.get("icao", ""))),
            "type": tk.StringVar(value="" if record is None else str(record.get("type", "INFO"))),
            "effective": tk.StringVar(value="" if record is None else str(record.get("effective", datetime.now().strftime("%Y-%m-%d %H:%M")))),
            "expiry": tk.StringVar(value="" if record is None else str(record.get("expiry", ""))),
            "summary": tk.StringVar(value="" if record is None else str(record.get("summary", ""))),
        }

        frm = ttk.Frame(dialog)
        frm.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        labels = [
            ("NOTAM ID", "id"),
            ("ICAO", "icao"),
            ("Type", "type"),
            ("Effective", "effective"),
            ("Expiry", "expiry"),
            ("Summary", "summary"),
        ]
        for idx, (label, key) in enumerate(labels):
            ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="w", padx=(0, 10), pady=4)
            width = 48 if key == "summary" else 28
            ttk.Entry(frm, textvariable=fields[key], width=width).grid(row=idx, column=1, sticky="ew", pady=4)

        frm.grid_columnconfigure(1, weight=1)

        btns = ttk.Frame(frm)
        btns.grid(row=len(labels), column=0, columnspan=2, sticky="e", pady=(10, 0))

        def on_save():
            payload = {key: var.get().strip() for key, var in fields.items()}
            if not payload["id"] or not payload["icao"] or not payload["summary"]:
                messagebox.showwarning("Validation", "ID, ICAO and Summary are required.", parent=dialog)
                return
            replaced = False
            for idx2, item in enumerate(self._notams):
                if item.get("id") == payload["id"]:
                    self._notams[idx2] = payload
                    replaced = True
                    break
            if record is not None and not replaced:
                for idx2, item in enumerate(self._notams):
                    if item.get("id") == record.get("id"):
                        self._notams[idx2] = payload
                        replaced = True
                        break
            if not replaced:
                self._notams.append(payload)
            self._save_notams()
            self._notam_refresh_tree()
            dialog.destroy()

        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btns, text="Save", style="Accent.TButton", command=on_save).pack(side=tk.RIGHT)

    # ─── Trend tab ──────────────────────────────────────────────────────────

    def _tab_vor_trend(self):
        parent = self._tabs["vor_trend"]

        top = ttk.Frame(parent)
        top.pack(fill=tk.X, padx=12, pady=(12, 6))

        buttons = [
            ("📸 Snapshot current", self._trend_snapshot),
            ("📂 Load history", self._trend_load_history),
            ("💾 Save history", self._trend_save_history),
            ("🗑 Delete selected", self._trend_delete_selected),
            ("🗑 Clear all", self._trend_clear_all),
            ("📊 Export CSV", self._trend_export_csv),
        ]
        for idx, (text, callback) in enumerate(buttons):
            style = "Accent.TButton" if idx == 0 else "TButton"
            ttk.Button(top, text=text, style=style, command=callback).pack(side=tk.LEFT, padx=(0, 6))

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        left = ttk.LabelFrame(main, text="Series")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        for _, key, _, _ in VOR_REPORT_FIELDS:
            default_on = key in {"power", "vswr", "temp", "psu_v"}
            var = tk.BooleanVar(value=default_on)
            self._trend_param_vars[key] = var
            text = next(label for label, k, _, _ in VOR_REPORT_FIELDS if k == key)
            ttk.Checkbutton(left, text=text, variable=var, command=self._trend_refresh_chart).pack(anchor="w", padx=10, pady=2)

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(left, text="Select All", command=self._trend_select_all).pack(fill=tk.X, padx=10, pady=(0, 4))
        ttk.Button(left, text="Clear All", command=self._trend_clear_selection).pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Checkbutton(left, text="Normalise (0–1)", variable=self._trend_normalise_var, command=self._trend_refresh_chart).pack(anchor="w", padx=10, pady=4)
        ttk.Checkbutton(left, text="Auto-refresh", variable=self._trend_auto_var, command=self._trend_reschedule_auto_refresh).pack(anchor="w", padx=10, pady=4)

        interval_row = ttk.Frame(left)
        interval_row.pack(fill=tk.X, padx=10, pady=(2, 10))
        ttk.Label(interval_row, text="Interval (min)").pack(side=tk.LEFT)
        interval_box = ttk.Combobox(
            interval_row,
            textvariable=self._trend_interval_var,
            values=["1", "5", "10", "15", "30"],
            state="readonly",
            width=8,
        )
        interval_box.pack(side=tk.RIGHT)
        interval_box.bind("<<ComboboxSelected>>", lambda _e: self._trend_reschedule_auto_refresh())

        right = ttk.LabelFrame(main, text="Trend Chart")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        if MPL_OK:
            self._trend_figure = Figure(figsize=(7, 4), dpi=100, facecolor=THEME_BG)
            self._trend_ax = self._trend_figure.add_subplot(111)
            self._trend_canvas = FigureCanvasTkAgg(self._trend_figure, master=right)
            self._trend_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        else:
            err = tk.Label(
                right,
                text="matplotlib not available. Install matplotlib to view charts.",
                bg=THEME_BG,
                fg=THEME_WARN,
                font=("Segoe UI", 11, "bold"),
            )
            err.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        bottom = ttk.Frame(parent)
        bottom.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 12))

        tree_cols = ("timestamp", "station", "tech", "power", "vswr", "temp", "psu_v", "status")
        self._trend_tree = ttk.Treeview(bottom, columns=tree_cols, show="headings", height=10)
        labels = {
            "timestamp": "Timestamp",
            "station": "Station",
            "tech": "Technician",
            "power": "RF Power",
            "vswr": "VSWR",
            "temp": "Temp",
            "psu_v": "PSU V",
            "status": "Status",
        }
        widths = {"timestamp": 160, "station": 70, "tech": 120, "power": 80, "vswr": 70, "temp": 70, "psu_v": 70, "status": 80}
        for col in tree_cols:
            self._trend_tree.heading(col, text=labels[col])
            self._trend_tree.column(col, width=widths[col], anchor="w")
        self._trend_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._trend_tree.bind("<Double-1>", self._trend_on_double_click)

        trend_scroll = ttk.Scrollbar(bottom, orient=tk.VERTICAL, command=self._trend_tree.yview)
        trend_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._trend_tree.configure(yscrollcommand=trend_scroll.set)

        status_lbl = tk.Label(
            parent,
            textvariable=self._trend_status_var,
            bg="#08131f",
            fg="#a9bfd2",
            anchor="w",
            padx=10,
            pady=6,
        )
        status_lbl.pack(fill=tk.X, padx=12, pady=(0, 10))

        self._trend_refresh_tree()
        self._trend_refresh_chart()

    def _trend_select_all(self):
        for var in self._trend_param_vars.values():
            var.set(True)
        self._trend_refresh_chart()

    def _trend_clear_selection(self):
        for var in self._trend_param_vars.values():
            var.set(False)
        self._trend_refresh_chart()

    def _trend_snapshot(self):
        if not self._vor_rpt_data:
            self._bottom_status_var.set("No VOR report loaded; querying device before snapshot.")
            self._vor_rpt_query(callback=self._trend_snapshot_append)
            return
        self._trend_snapshot_append()

    def _trend_snapshot_append(self):
        data = dict(self._vor_rpt_data)
        if not data:
            return
        snapshot = {
            "timestamp": data.get("timestamp", datetime.now().isoformat(timespec="seconds")),
            "station": data.get("station", self._vor_rpt_station.get()),
            "tech": data.get("tech", self._vor_rpt_tech.get()),
            "status": self._overall_vor_status(data),
        }
        for _, key, _, _ in VOR_REPORT_FIELDS:
            snapshot[key] = self._try_float(data.get(key))
        self._vor_trend_records.append(snapshot)
        self._save_vor_trend()
        self._trend_refresh_tree()
        self._trend_refresh_chart()
        self._trend_status_var.set("Snapshot captured at " + snapshot["timestamp"])
        self._bottom_status_var.set("Saved VOR trend snapshot.")

    def _trend_load_history(self):
        path = filedialog.askopenfilename(
            title="Load Trend History",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return
        try:
            records = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise ValueError("The selected file does not contain a JSON list.")
            self._vor_trend_records = records
            self._trend_refresh_tree()
            self._trend_refresh_chart()
            self._trend_status_var.set("Loaded " + str(len(records)) + " snapshots from " + path)
        except Exception as exc:
            messagebox.showerror("Load Error", "Unable to load trend history.\n\n" + str(exc))

    def _trend_save_history(self):
        path = filedialog.asksaveasfilename(
            title="Save Trend History",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile="navaids_vor_trend_export.json",
        )
        if not path:
            return
        try:
            text = json.dumps(self._vor_trend_records, indent=2, ensure_ascii=False)
            Path(path).write_text(text, encoding="utf-8")
            self._trend_status_var.set("Trend history saved to " + path)
        except Exception as exc:
            messagebox.showerror("Save Error", "Unable to save trend history.\n\n" + str(exc))

    def _trend_delete_selected(self):
        selected = self._trend_tree.selection()
        if not selected:
            messagebox.showinfo("Delete Snapshot", "Please select one or more rows.")
            return
        indexes = sorted([int(item.replace("trend-", "")) for item in selected], reverse=True)
        for index in indexes:
            if 0 <= index < len(self._vor_trend_records):
                del self._vor_trend_records[index]
        self._save_vor_trend()
        self._trend_refresh_tree()
        self._trend_refresh_chart()
        self._trend_status_var.set("Deleted " + str(len(indexes)) + " snapshot(s).")

    def _trend_clear_all(self):
        if not self._vor_trend_records:
            return
        if not messagebox.askyesno("Clear Trend History", "Clear all VOR trend snapshots?"):
            return
        self._vor_trend_records = []
        self._save_vor_trend()
        self._trend_refresh_tree()
        self._trend_refresh_chart()
        self._trend_status_var.set("All trend history cleared.")

    def _trend_export_csv(self):
        if not self._vor_trend_records:
            messagebox.showinfo("Export CSV", "There are no records to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile="navaids_vor_trend.csv",
        )
        if not path:
            return
        try:
            headers = ["timestamp", "station", "tech", "status"] + [key for _, key, _, _ in VOR_REPORT_FIELDS]
            with open(path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers)
                writer.writeheader()
                for row in self._vor_trend_records:
                    writer.writerow({name: row.get(name, "") for name in headers})
            self._trend_status_var.set("CSV exported to " + path)
        except Exception as exc:
            messagebox.showerror("Export Error", "Unable to export CSV.\n\n" + str(exc))

    def _trend_refresh_chart(self):
        if not MPL_OK or self._trend_ax is None or self._trend_figure is None or self._trend_canvas is None:
            return

        ax = self._trend_ax
        fig = self._trend_figure
        ax.clear()
        fig.set_facecolor(THEME_BG)
        ax.set_facecolor(THEME_BG)
        ax.tick_params(colors=THEME_FG)
        for spine in ax.spines.values():
            spine.set_color("#44627d")
        ax.grid(True, color="#29465f", linestyle="--", linewidth=0.5, alpha=0.7)
        ax.set_title("VOR Parameter Trend", color=THEME_FG)

        if not self._vor_trend_records:
            ax.text(0.5, 0.5, "No trend snapshots", color=THEME_WARN, ha="center", va="center", transform=ax.transAxes)
            self._trend_canvas.draw()
            return

        selected_keys = [key for key, var in self._trend_param_vars.items() if var.get()]
        if not selected_keys:
            ax.text(0.5, 0.5, "Select at least one parameter", color=THEME_WARN, ha="center", va="center", transform=ax.transAxes)
            self._trend_canvas.draw()
            return

        labels = []
        xs = list(range(len(self._vor_trend_records)))
        for rec in self._vor_trend_records:
            ts_raw = str(rec.get("timestamp", ""))
            try:
                dt = datetime.fromisoformat(ts_raw)
                labels.append(dt.strftime("%H:%M\n%d-%m"))
            except Exception:
                labels.append(ts_raw[:11])

        palette = ["#4cc9f0", "#ffd166", "#ff6b6b", "#72efdd", "#c77dff", "#90be6d", "#f8961e", "#f72585", "#8ecae6"]
        normalise = self._trend_normalise_var.get()

        for idx, key in enumerate(selected_keys):
            ys = [self._try_float(rec.get(key)) for rec in self._vor_trend_records]
            if all(item is None for item in ys):
                continue

            plot_vals = []
            valid = [val for val in ys if val is not None]
            series_min = min(valid) if valid else 0.0
            series_max = max(valid) if valid else 1.0
            denom = series_max - series_min
            for val in ys:
                if val is None:
                    plot_vals.append(float("nan"))
                elif normalise:
                    if denom <= 0:
                        plot_vals.append(1.0)
                    else:
                        plot_vals.append((val - series_min) / denom)
                else:
                    plot_vals.append(val)

            label = next(lbl for lbl, candidate, _, _ in VOR_REPORT_FIELDS if candidate == key)
            colour = palette[idx % len(palette)]
            ax.plot(xs, plot_vals, marker="o", linewidth=1.8, markersize=4, label=label, color=colour)

            if key in VOR_ALARM_THRESHOLDS:
                _, threshold = VOR_ALARM_THRESHOLDS[key]
                if normalise:
                    if denom > 0:
                        thr = (threshold - series_min) / denom
                        ax.axhline(thr, color="#ff6666", linestyle="--", linewidth=0.8, alpha=0.45)
                else:
                    ax.axhline(threshold, color="#ff6666", linestyle="--", linewidth=0.8, alpha=0.45)

        ax.set_xticks(xs)
        ax.set_xticklabels(labels, color=THEME_FG, fontsize=8)
        ax.legend(facecolor="#10243a", edgecolor="#35526c", labelcolor=THEME_FG)
        ax.set_ylabel("Normalised" if normalise else "Measured value", color=THEME_FG)
        fig.tight_layout()
        self._trend_canvas.draw()

    def _trend_refresh_tree(self):
        for row in self._trend_tree.get_children():
            self._trend_tree.delete(row)
        for idx, rec in enumerate(self._vor_trend_records):
            values = (
                rec.get("timestamp", ""),
                rec.get("station", ""),
                rec.get("tech", ""),
                self._format_value(rec.get("power"), "W"),
                self._format_value(rec.get("vswr")),
                self._format_value(rec.get("temp"), "°C"),
                self._format_value(rec.get("psu_v"), "V"),
                rec.get("status", ""),
            )
            self._trend_tree.insert("", tk.END, iid="trend-" + str(idx), values=values)

    def _trend_on_double_click(self, _event):
        selected = self._trend_tree.selection()
        if not selected:
            return
        idx = int(selected[0].replace("trend-", ""))
        if not (0 <= idx < len(self._vor_trend_records)):
            return
        record = dict(self._vor_trend_records[idx])
        self._vor_rpt_data = record
        self._vor_rpt_station.set(record.get("station", self._vor_rpt_station.get()))
        self._vor_rpt_tech.set(record.get("tech", self._vor_rpt_tech.get()))
        self._vor_rpt_refresh_fields()
        self._notebook.select(self._tabs["vor_report"])
        self._trend_status_var.set("Loaded snapshot into VOR report view.")

    def _trend_reschedule_auto_refresh(self):
        if self._trend_auto_after_id is not None:
            self._root.after_cancel(self._trend_auto_after_id)
            self._trend_auto_after_id = None
        if not self._trend_auto_var.get():
            self._trend_status_var.set("Auto-refresh disabled.")
            return
        try:
            minutes = int(self._trend_interval_var.get())
        except Exception:
            minutes = 5
        minutes = max(minutes, 1)
        self._trend_status_var.set("Auto-refresh enabled every " + str(minutes) + " minute(s).")
        self._trend_auto_after_id = self._root.after(minutes * 60 * 1000, self._trend_auto_tick)

    def _trend_auto_tick(self):
        self._trend_auto_after_id = None
        if self._trend_auto_var.get():
            self._trend_snapshot()
            self._trend_reschedule_auto_refresh()

    # ─── About tab ──────────────────────────────────────────────────────────

    def _tab_about(self):
        parent = self._tabs["about"]
        box = ttk.Frame(parent)
        box.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        text = (
            APP_TITLE
            + "\n\n"
            + "Desktop monitoring console for VOR navigation aids and radar simulation.\n"
            + "Features include:\n"
            + "• Live radar PPI with simulated tracks and weather\n"
            + "• VOR device health reporting\n"
            + "• NOTAM management\n"
            + "• Trend capture and historical analysis\n\n"
            + "Python "
            + ".".join(str(part) for part in sys.version_info[:3])
            + "\n"
            + "matplotlib support: "
            + ("Enabled" if MPL_OK else "Unavailable")
        )

        lbl = tk.Label(
            box,
            text=text,
            justify="left",
            anchor="nw",
            bg=THEME_BG,
            fg=THEME_FG,
            font=("Segoe UI", 12),
        )
        lbl.pack(fill=tk.BOTH, expand=True)

    # ─── Status clock ───────────────────────────────────────────────────────

    def _start_status_clock(self):
        now = datetime.now()
        self._top_clock_var.set(now.strftime("%Y-%m-%d %H:%M:%S"))
        if self._top_info_var.get() in {"", "Ready"}:
            self._top_info_var.set("Version " + APP_VERSION)
        self._root.after(1000, self._start_status_clock)

    # ─── Weather animation controls ────────────────────────────────────────

    def _weather_anim_start(self):
        self._weather_anim_fast = True
        self._radar_status_var.set("Weather animation speed: FAST")
        self._bottom_status_var.set("Weather animation enabled.")

    def _weather_anim_stop(self):
        self._weather_anim_fast = False
        self._radar_status_var.set("Weather animation speed: NORMAL")
        self._bottom_status_var.set("Weather animation returned to normal speed.")


def main():
    if not TK_OK:
        raise RuntimeError("tkinter is not available in this Python environment.")
    root = tk.Tk()
    app = NAVAIDSApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
