# SatOps Telemetry Monitor

Post-pass satellite telemetry analyser. Reads a CSV of raw telemetry, checks values against operational limits, detects time-series gaps, and produces a structured report — exactly what a flight controller runs after a contact window.  
Deployed on Render: [https://satops-telemetry-monitor.onrender.com](https://satops-telemetry-monitor.onrender.com)

---

## Features

- **Limit checking** — flags out-of-limit values (LOW / HIGH) per parameter
- **Gap detection** — finds dropouts in the time series above a configurable threshold
- **Summary report** — clean CLI output or machine-readable JSON
- **Web UI** — upload your own CSV or run against built-in sample data
- **Standalone executable** — single binary via PyInstaller, no Python required on target machine

---

## Project Structure

```
satops-telemetry-monitor/
├── telemetry_monitor.py     # Core logic + CLI entry point
├── generate_sample_data.py  # Generates realistic test telemetry with injected anomalies
├── app.py                   # Flask web server (Render deployment)
├── templates/
│   └── index.html           # Ops-console web UI
├── data/
│   └── telemetry.csv        # Auto-generated sample data
├── requirements.txt
├── render.yaml              # Render one-click deploy config
└── build_exe.sh             # PyInstaller build script
```

---

## Quickstart (CLI)

```bash
pip install -r requirements.txt

# Generate sample data with injected anomalies
python generate_sample_data.py

# Run analysis (human report)
python telemetry_monitor.py

# Custom file + gap threshold
python telemetry_monitor.py path/to/telemetry.csv --gap-threshold 30

# Machine-readable JSON output
python telemetry_monitor.py --json
```

---

## CSV Format

```
timestamp,parameter,value
2024-03-15T10:00:00,battery_voltage,24.31
2024-03-15T10:00:00,bus_temperature,21.84
...
```

- `timestamp` — ISO 8601 format
- `parameter` — matches a key in the limits dictionary
- `value`     — numeric

---

## Operational Limits


| Parameter       | Min   | Max  |
| --------------- | ----- | ---- |
| battery_voltage | 22.5  | 28.0 |
| solar_current   | 0.0   | 4.5  |
| bus_temperature | -15.0 | 50.0 |
| attitude_error  | 0.0   | 2.0  |
| downlink_snr    | 5.0   | 35.0 |
| rx_lock         | 0.0   | 1.0  |


To customise, edit `DEFAULT_LIMITS` in `telemetry_monitor.py`.

---

## Web UI (local)

```bash
python app.py
# → http://localhost:5000
```

Upload any conforming CSV or click **Run Analysis** to use the built-in sample data.

---

## Build Standalone Executable

```bash
bash build_exe.sh
# → dist/satops-monitor
```

```bash
./dist/satops-monitor
./dist/satops-monitor data/telemetry.csv --gap-threshold 30
./dist/satops-monitor --json
```

---

## Example Output

```
╔══════════════════════════════════════════════════════════════════════╗
║  SATELLITE TELEMETRY MONITOR — POST-PASS REPORT                      ║
╚══════════════════════════════════════════════════════════════════════╝

  Source   : data/telemetry.csv
  Start    : 2024-03-15 10:00:00
  End      : 2024-03-15 10:59:50
  Duration : 0:59:50
  Rows     : 2160

────────────────────────────────────────────────────────────────────────
  LIMIT CHECKS  [✗ ANOMALIES DETECTED]
────────────────────────────────────────────────────────────────────────
  [2024-03-15 10:10:00]  attitude_error        value=2.8000  limit=(0.0, 2.0)  → OUT-OF-LIMIT HIGH
  [2024-03-15 10:20:00]  battery_voltage       value=20.1000 limit=(22.5, 28.0) → OUT-OF-LIMIT LOW
  [2024-03-15 10:33:20]  bus_temperature       value=54.0000 limit=(-15.0, 50.0) → OUT-OF-LIMIT HIGH

────────────────────────────────────────────────────────────────────────
  TIME-GAP ANALYSIS  (threshold = 60s)  [✗ 1 GAP(S) DETECTED]
────────────────────────────────────────────────────────────────────────
  2024-03-15 10:20:00  →  2024-03-15 10:22:10  (gap = 130s)

────────────────────────────────────────────────────────────────────────
  SUMMARY
────────────────────────────────────────────────────────────────────────
  Total readings   : 2160
  Nominal          : 2157
  Out-of-limit     : 3
  Time gaps        : 1
  Overall status   : ACTION REQUIRED
```

