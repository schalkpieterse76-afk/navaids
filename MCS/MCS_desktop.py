"""MCS CVOR RMS – Tkinter desktop wrapper with pystray system tray.

Features:
  - Borderless Tkinter window with custom titlebar (Thales ATM dark theme)
  - Embedded browser via tkinterweb (falls back to webbrowser module)
  - pystray system tray icon with right-click menu
  - Starts the Flask backend in a background thread
"""

import os
import sys
import json
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

# ---------------------------------------------------------------------------
# Colour palette (Thales ATM dark theme)
# ---------------------------------------------------------------------------
BG_DARK = "#0d1117"
BG_PANEL = "#161b22"
BG_ACCENT = "#1f2937"
FG_PRIMARY = "#e6edf3"
FG_MUTED = "#8b949e"
ACCENT_BLUE = "#388bfd"
ACCENT_GREEN = "#3fb950"
ACCENT_RED = "#f85149"
ACCENT_YELLOW = "#d29922"

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 5000
_HERE = os.path.dirname(os.path.abspath(__file__))
_HTML = os.path.join(_HERE, "MCS_CVOR_RMS.html")
_ICON_PATH = os.path.join(_HERE, "assets", "tray_icon.png")


# ---------------------------------------------------------------------------
# Backend thread
# ---------------------------------------------------------------------------

def _start_backend():
    """Start the Flask backend in a daemon thread."""
    backend_dir = os.path.join(_HERE, "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    try:
        from app import app as flask_app
        flask_app.run(host=BACKEND_HOST, port=BACKEND_PORT, debug=False, use_reloader=False)
    except Exception as exc:
        print(f"[MCS backend] Failed to start: {exc}")


def start_backend_thread():
    t = threading.Thread(target=_start_backend, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
# System tray (pystray)
# ---------------------------------------------------------------------------

def _create_tray_icon(app_window):
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Create a simple coloured icon if no PNG is available
        if os.path.isfile(_ICON_PATH):
            icon_image = Image.open(_ICON_PATH).resize((64, 64))
        else:
            icon_image = Image.new("RGB", (64, 64), color=ACCENT_BLUE)
            draw = ImageDraw.Draw(icon_image)
            draw.ellipse([8, 8, 56, 56], fill=BG_DARK, outline=ACCENT_BLUE, width=4)
            draw.text((20, 20), "MCS", fill=FG_PRIMARY)

        def on_show(_icon, _item):
            app_window.deiconify()
            app_window.lift()

        def on_quit(_icon, _item):
            _icon.stop()
            app_window.destroy()

        menu = pystray.Menu(
            pystray.MenuItem("Show MCS", on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit),
        )
        icon = pystray.Icon("MCS CVOR RMS", icon_image, "MCS CVOR RMS", menu)

        def run_tray():
            icon.run()

        tray_thread = threading.Thread(target=run_tray, daemon=True)
        tray_thread.start()
        return icon
    except ImportError:
        print("[MCS] pystray / Pillow not available; system tray disabled")
        return None


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MCSApp(tk.Tk):
    """Borderless Tkinter main window with custom titlebar."""

    def __init__(self):
        super().__init__()
        self.overrideredirect(True)  # borderless
        self.configure(bg=BG_DARK)
        self.title("MCS CVOR Remote Management System")
        self.geometry("1400x900+60+40")
        self.resizable(True, True)

        self._drag_start_x = 0
        self._drag_start_y = 0
        self._tray_icon = None

        self._build_titlebar()
        self._build_main_area()
        self._bind_resize()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_titlebar(self):
        bar = tk.Frame(self, bg=BG_PANEL, height=38)
        bar.pack(side=tk.TOP, fill=tk.X)
        bar.pack_propagate(False)

        # Logo / title
        tk.Label(
            bar,
            text="  ✈  MCS CVOR Remote Management System",
            bg=BG_PANEL,
            fg=FG_PRIMARY,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(side=tk.LEFT, padx=8)

        # Window controls (right side)
        for symbol, cmd in [("⊟", self._minimise), ("⊞", self._maximise), ("✕", self._close)]:
            tk.Button(
                bar,
                text=symbol,
                bg=BG_PANEL,
                fg=FG_PRIMARY,
                activebackground=ACCENT_RED if symbol == "✕" else BG_ACCENT,
                activeforeground=FG_PRIMARY,
                font=("Segoe UI", 12),
                bd=0,
                padx=10,
                pady=4,
                command=cmd,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(side=tk.RIGHT)

        bar.bind("<ButtonPress-1>", self._start_drag)
        bar.bind("<B1-Motion>", self._do_drag)

    def _build_main_area(self):
        content = tk.Frame(self, bg=BG_DARK)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Sidebar
        sidebar = tk.Frame(content, bg=BG_PANEL, width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        # Browser / content frame
        browser_frame = tk.Frame(content, bg=BG_DARK)
        browser_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_browser(browser_frame)

    def _build_sidebar(self, parent):
        tk.Label(
            parent,
            text="NAVIGATION",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(pady=(16, 4), padx=12, anchor="w")

        nav_items = [
            ("🗺️  Dashboard", "dashboard"),
            ("🏛️  Bases", "bases"),
            ("📡  CVOR Systems", "systems"),
            ("🔔  Alarms", "alarms"),
            ("🏗️  Shelter", "shelter"),
            ("📂  Import", "import"),
            ("💾  Export", "export"),
            ("⚙️  Settings", "settings"),
        ]
        for label, section in nav_items:
            btn = tk.Button(
                parent,
                text=label,
                bg=BG_PANEL,
                fg=FG_PRIMARY,
                activebackground=BG_ACCENT,
                activeforeground=FG_PRIMARY,
                font=("Segoe UI", 10),
                bd=0,
                padx=12,
                pady=6,
                anchor="w",
                width=22,
                relief=tk.FLAT,
                cursor="hand2",
                command=lambda s=section: self._navigate(s),
            )
            btn.pack(fill=tk.X)

    def _build_browser(self, parent):
        try:
            from tkinterweb import HtmlFrame
            self._html_frame = HtmlFrame(parent, horizontal_scrollbar="auto")
            self._html_frame.pack(fill=tk.BOTH, expand=True)
            self._html_frame.load_file(_HTML)
        except ImportError:
            # Fallback label + open-in-browser button
            tk.Label(
                parent,
                text="tkinterweb not installed.\nUse the button below to open in your browser.",
                bg=BG_DARK,
                fg=FG_MUTED,
                font=("Segoe UI", 11),
                justify=tk.CENTER,
            ).pack(expand=True)
            tk.Button(
                parent,
                text="Open in Browser",
                bg=ACCENT_BLUE,
                fg=FG_PRIMARY,
                font=("Segoe UI", 11, "bold"),
                bd=0,
                padx=20,
                pady=10,
                relief=tk.FLAT,
                cursor="hand2",
                command=self._open_browser,
            ).pack(pady=8)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _navigate(self, section: str):
        url = f"http://{BACKEND_HOST}:{BACKEND_PORT}/#section={section}"
        if hasattr(self, "_html_frame"):
            try:
                self._html_frame.load_url(url)
                return
            except Exception:
                pass
        webbrowser.open(url)

    def _open_browser(self):
        webbrowser.open(f"file:///{_HTML.replace(os.sep, '/')}")

    def _minimise(self):
        self.overrideredirect(False)
        self.iconify()
        self.overrideredirect(True)

    def _maximise(self):
        if self.state() == "zoomed":
            self.state("normal")
        else:
            self.state("zoomed")

    def _close(self):
        if messagebox.askokcancel("Quit", "Minimise to system tray?"):
            self.withdraw()
        else:
            self.destroy()

    # ------------------------------------------------------------------
    # Window drag (borderless)
    # ------------------------------------------------------------------

    def _start_drag(self, event):
        self._drag_start_x = event.x_root - self.winfo_x()
        self._drag_start_y = event.y_root - self.winfo_y()

    def _do_drag(self, event):
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Resize (south-east corner grip)
    # ------------------------------------------------------------------

    def _bind_resize(self):
        grip = tk.Label(self, bg=BG_ACCENT, cursor="sizing", width=2, height=1)
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<ButtonPress-1>", self._resize_start)
        grip.bind("<B1-Motion>", self._resize_do)

    def _resize_start(self, event):
        self._resize_x = event.x_root
        self._resize_y = event.y_root
        self._resize_w = self.winfo_width()
        self._resize_h = self.winfo_height()

    def _resize_do(self, event):
        dx = event.x_root - self._resize_x
        dy = event.y_root - self._resize_y
        new_w = max(800, self._resize_w + dx)
        new_h = max(600, self._resize_h + dy)
        self.geometry(f"{new_w}x{new_h}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Start Flask backend
    start_backend_thread()

    # Create and run Tkinter window
    app_window = MCSApp()

    # Attach system tray
    app_window._tray_icon = _create_tray_icon(app_window)

    app_window.mainloop()


if __name__ == "__main__":
    main()
