# NAVAIDS v7.0 – Navigation Aids Management System

A professional single-file desktop application for managing, calibrating, testing and simulating VOR and ILS navigation aids.

## Integrated Systems
| System | Purpose |
|---|---|
| **Thales VOR** | VOR query, calibration, test, full print report (Thales TRC 6000 format) |
| **Normarc ILS** | Localizer & Glidepath calibration and monitoring |
| **Alcatel LOC** | Localizer initialisation, frequency set, alignment |
| **Thales ATM** | Approach & Terminal calibration controller |
| **ADRACS** | Automatic Distance Ranging And Calibration System |

## Features
- `.LDA` file import with terrain obstacle analysis
- LDA upload to EEPROM / RMM / RAM memory targets
- TCP and COM port auto-connect with baud selection and auto-reconnect (10 s)
- African civil runway database
- South African Air Force (SAAF) ILS runway database
- Calibration panels (ATM, ADRACS, Normarc)
- Live signal charts (VOR bearing, LOC DDM, GP DDM)
- VOR / ILS / Full-ILS simulation with configurable tick rate
- Flight Inspection Log with CSV and PDF export
- NOTAM / Maintenance Scheduler with due-date alerts and popup warnings
- Radar Screen (PPI sweep, tracks, labels, rings, NAVAID overlay)
- ADS-B / ASTERIX live data feed (SBS-1 BaseStation TCP, Beast Binary TCP, AVR/RAW TCP, ASTERIX CAT-048 UDP)
- Hex Viewer (EEPROM / RMM / RAM) with search, jump, export BIN/IHEX
- Memory Compare – side-by-side byte diff with colour coding, navigator, CSV/TXT export
- Binary Patch – generate .navpatch, verify, apply, reverse, upload to device
- Local Self-Test runner for all sub-programs
- TCP Loopback Test (remote and local echo server)
- Serial connect dialog – offers to download config/LDA from device on connect
- **Thales VOR Print Report** – full 32-parameter Thales TRC 6000 format report with print preview, OS print, PDF export, CSV export, TXT save
- Full config save / export / import (JSON)
- Dark / light theme toggle
- Persistent layout (last COM port, TCP host/port, theme, baud)

## Requirements
```bash
pip install -r requirements.txt
```

## Run
```bash
python navaids.py
```

## Tab Guide
| Tab | Description |
|---|---|
| 🔵 Thales VOR | VOR status, control, manual commands (Thales only) |
| 🖨 VOR Report | Full Thales TRC 6000 format print report – query, preview, print, PDF, CSV |
| 🟠 ILS (Normarc/Alcatel) | Localizer & Glidepath (Normarc/Alcatel only) |
| 🌍 African Runways | African airport/runway reference database |
| 🦅 SAAF ILS Runways | South African Air Force ILS runway database |
| ⚙ Calibration | ATM, ADRACS, Normarc calibration panels |
| 💾 LDA Memory | Upload LDA to EEPROM/RMM/RAM, download, verify |
| 🔍 Hex Viewer | Read-only hex dump of EEPROM/RMM/RAM with search |
| ⚖ Mem Compare | Side-by-side byte diff of two memory images |
| 🩹 Patch | Generate/apply/reverse binary patch files |
| 🔬 Local Test | Program self-tests + TCP loopback test |
| 📈 Live Charts | Real-time VOR bearing, LOC DDM, GP DDM strip charts |
| 🖥 Simulation | VOR/ILS simulation playback |
| 📋 Inspection Log | Flight inspection records with CSV/PDF export |
| 📅 NOTAM / Maintenance | NOTAM scheduler with due-date alerts |
| 📡 Radar / ADS-B | PPI radar with live ADS-B/ASTERIX feed |

## Notes
- VOR testing: **Thales commands only**
- Localizer testing: **Normarc / Alcatel commands only**
- VOR Report queries 32 parameters using Thales TRC 6000 command set