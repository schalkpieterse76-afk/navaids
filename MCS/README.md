# MCS CVOR Remote Management System
### South African Air Force · Thales ATM Architecture · v2.1

A cross-platform (Windows 11 / Linux) desktop + web application for remotely managing
**CVOR (Conventional VOR)** navigation systems across all SAAF air force bases.

## Quick Start

### 1. Install dependencies
```bash
pip install flask flask-cors flask-sqlalchemy netifaces tkinterweb pillow pystray requests
# Optional – best in-app rendering:
pip install cefpython3
```

### 2. Run (desktop app with system tray)
```bash
python MCS_desktop.py
```

### 3. Run (browser only – no Python needed for frontend)
Open `MCS_CVOR_RMS.html` directly in any browser.

### 4. Run (backend API only)
```bash
python backend/app.py
```

## Project Structure
```
MCS/
├── MCS_CVOR_RMS.html        ← Complete single-file app (HTML/CSS/JS + Leaflet map)
├── MCS_desktop.py           ← Tkinter desktop wrapper with system tray (pystray)
├── MCS.py                   ← Simple browser launcher
├── backend/
│   ├── app.py               ← Flask REST API (25+ endpoints)
│   ├── models.py            ← SQLAlchemy DB models
│   ├── database.py          ← DB init + SAAF base seeding
│   ├── tcp_client.py        ← Thales ATM TCP/IP framing protocol
│   ├── network_detect.py    ← OS subnet/gateway auto-detection
│   ├── file_import.py       ← .ini / config.sys / .LDA parsers
│   └── requirements.txt
├── database/                ← SQLite DB auto-created here
├── scripts/
│   ├── install_windows.bat
│   └── install_linux.sh
└── README.md
```

## Features
| Feature | Detail |
|---|---|
| 🗺️ Dashboard | All 10 SAAF bases with live CVOR status badges |
| 🛰️ Leaflet Map | Dark SA map with animated colour-coded pins per base |
| 🏛️ Base Management | Add / edit / delete / split bases |
| 📡 CVOR Systems | Full CRUD, IP/subnet/gateway config per system |
| 🔌 TCP/IP Remote | Thales ATM STX/ETX JSON framing; ping, poll, commands |
| 📂 File Import | .ini · config.sys · .LDA parsers (browser + backend) |
| 🏗️ Shelter Layout | SVG shelter diagram + per-equipment slot database |
| ⚙️ Remote Settings | Set frequency, power, mode, IDENT, reboot, E-STOP |
| 🔔 Alarms | Live alarm retrieval with severity colouring |
| 💾 Export | Full DB or per-base ZIP download |
| 🪟 Desktop App | Borderless Tkinter window, custom titlebar, sidebar |
| ⊟ System Tray | pystray tray icon, right-click menu, balloon notifications |
| 🎨 Thales ATM theme | Full dark theme throughout |

## TCP/IP Protocol (Thales ATM framing)

Messages are framed with STX (0x02) / ETX (0x03) bytes and contain JSON payloads:

```
STX | length (2 bytes, big-endian) | JSON payload | ETX
```

Example command:
```json
{"cmd": "GET_STATUS", "system_id": 1}
```

Example response:
```json
{"status": "OK", "frequency": 116.3, "power": "HIGH", "mode": "NORMAL"}
```

## SAAF Bases (pre-seeded)
| # | Base | ICAO | Coordinates |
|---|------|------|-------------|
| 1 | AFB Waterkloof | FAWK | -25.8300, 28.2200 |
| 2 | AFB Hoedspruit | FAHS | -24.3700, 31.0500 |
| 3 | AFB Louis Trichardt | FALT | -23.1600, 29.8600 |
| 4 | AFB Makhado | FALM | -23.1600, 29.9100 |
| 5 | AFB Overberg | FAOB | -34.5500, 20.5000 |
| 6 | AFB Langebaanweg | FALA | -32.9700, 18.1600 |
| 7 | AFB Bredasdorp | FABE | -34.5900, 20.0400 |
| 8 | AFB Ysterplaat | FAYP | -33.9000, 18.4980 |
| 9 | AFB Swartkop | FASK | -25.8090, 28.1640 |
| 10 | AFB Bloemspruit | FABL | -29.0920, 26.3020 |

## Environment Variables
| Variable | Default | Description |
|---|---|---|
| `MCS_HOST` | `0.0.0.0` | Flask bind host |
| `MCS_PORT` | `5000` | Flask bind port |
| `MCS_DB_PATH` | `database/mcs.db` | SQLite database path |
| `MCS_DEBUG` | `false` | Enable Flask debug mode |

## License
Internal SAAF / Thales ATM use only.
