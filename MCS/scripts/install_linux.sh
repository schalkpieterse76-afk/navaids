#!/usr/bin/env bash
# MCS CVOR RMS – Linux installer
set -euo pipefail

echo "============================================"
echo " MCS CVOR Remote Management System"
echo " Linux Installer"
echo "============================================"
echo

if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found. Install with: sudo apt install python3"
    exit 1
fi

echo "[1/4] Upgrading pip..."
python3 -m pip install --upgrade pip

echo "[2/4] Installing backend dependencies..."
python3 -m pip install flask flask-cors flask-sqlalchemy netifaces tkinterweb pillow pystray requests

echo "[3/4] Installing system Tk (if missing)..."
if command -v apt &>/dev/null; then
    sudo apt-get install -y python3-tk python3-pil python3-pil.imagetk 2>/dev/null || true
elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3-tkinter 2>/dev/null || true
fi

echo "[4/4] Optional: cefpython3..."
python3 -m pip install cefpython3 2>/dev/null || echo "[INFO] cefpython3 not available – skipping."

echo
echo "============================================"
echo " Installation complete."
echo " Run:  python3 ../MCS_desktop.py"
echo "============================================"
