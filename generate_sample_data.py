"""
generate_sample_data.py
Generates a realistic satellite telemetry CSV for testing the monitor.
Injects known anomalies and time gaps.
"""

import csv
import random
from datetime import datetime, timedelta

PARAMETERS = {
    "battery_voltage":   (22.0, 28.0, 24.5, 0.3),   # (min, max, nominal, noise)
    "solar_current":     (0.0,  4.0,  2.1,  0.2),
    "bus_temperature":   (-10,  50,   22.0, 1.5),
    "attitude_error":    (0.0,  2.0,  0.4,  0.1),
    "downlink_snr":      (5.0,  30.0, 18.0, 1.0),
    "rx_lock":           (0,    1,    1,    0),       # binary, no noise
}

def generate(output_path: str = "data/telemetry.csv", seed: int = 42):
    random.seed(seed)
    rows = []
    t = datetime(2024, 3, 15, 10, 0, 0)
    step = timedelta(seconds=10)

    for i in range(360):  # 1 hour of 10s cadence
        # Inject a deliberate time gap at ~t+20min (skip 2 minutes)
        if i == 120:
            t += timedelta(seconds=130)

        for param, (lo, hi, nom, noise) in PARAMETERS.items():
            val = nom + random.gauss(0, noise) if noise else nom

            # Inject anomalies
            if i == 60  and param == "battery_voltage":
                val = 20.1   # under-voltage
            if i == 200 and param == "bus_temperature":
                val = 54.0   # over-temp
            if i == 300 and param == "attitude_error":
                val = 2.8    # attitude spike

            if param == "rx_lock":
                val = 1 if random.random() > 0.05 else 0

            rows.append({
                "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S"),
                "parameter": param,
                "value":     round(float(val), 4),
            })

        t += step

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "parameter", "value"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} rows → {output_path}")

if __name__ == "__main__":
    generate()
