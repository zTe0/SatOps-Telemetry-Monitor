"""
telemetry_monitor.py
Post-pass satellite telemetry analyser.

Usage:
    python telemetry_monitor.py [csv_file] [--gap-threshold 60] [--json]

Checks each parameter value against defined operational limits,
detects time-series gaps, and prints a structured summary report.
"""

import argparse
import json
import sys, os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Operational limits  {parameter: (min, max)}
# Mirrors what a flight controller would load from a limits file.
# ---------------------------------------------------------------------------
DEFAULT_LIMITS: dict[str, tuple[float, float]] = {
    "battery_voltage": (22.5, 28.0),
    "solar_current":   (0.0,  4.5),
    "bus_temperature": (-15.0, 50.0),
    "attitude_error":  (0.0,  2.0),
    "downlink_snr":    (5.0,  35.0),
    "rx_lock":         (0.0,  1.0),
}

GAP_THRESHOLD_S: int = 60   # seconds — flag any gap larger than this


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class Anomaly:
    timestamp: datetime
    parameter: str
    value: float
    limit_min: float
    limit_max: float

    @property
    def direction(self) -> str:
        return "LOW" if self.value < self.limit_min else "HIGH"

    def __str__(self) -> str:
        return (
            f"  [{self.timestamp}]  {self.parameter:<20s}  "
            f"value={self.value:>8.4f}  "
            f"limit=({self.limit_min}, {self.limit_max})  "
            f"→ OUT-OF-LIMIT {self.direction}"
        )


@dataclass
class TimeGap:
    start: datetime
    end: datetime

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def __str__(self) -> str:
        return (
            f"  {self.start}  →  {self.end}  "
            f"(gap = {self.duration.total_seconds():.0f}s)"
        )


@dataclass
class MonitorResult:
    source_file: str
    total_rows: int
    parameters_found: list[str]
    time_start: Optional[datetime]
    time_end: Optional[datetime]
    anomalies: list[Anomaly] = field(default_factory=list)
    gaps: list[TimeGap] = field(default_factory=list)
    unknown_parameters: list[str] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return self.total_rows - len(self.anomalies)

    @property
    def anomaly_count(self) -> int:
        return len(self.anomalies)

    @property
    def gap_count(self) -> int:
        return len(self.gaps)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def load_telemetry(csv_path: Path) -> pd.DataFrame:
    """Load and validate the telemetry CSV."""
    required = {"timestamp", "parameter", "value"}

    df = pd.read_csv(csv_path)

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    if df["value"].isna().any():
        bad = df["value"].isna().sum()
        print(f"  WARNING: {bad} rows with non-numeric values — skipped.")
        df = df.dropna(subset=["value"])

    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def check_limits(
    df: pd.DataFrame,
    limits: dict[str, tuple[float, float]],
) -> tuple[list[Anomaly], list[str]]:
    """Flag every row whose value falls outside defined limits."""
    anomalies: list[Anomaly] = []
    unknown: list[str] = []

    for param, group in df.groupby("parameter"):
        if param not in limits:
            unknown.append(param)
            continue

        lo, hi = limits[param]
        ool = group[(group["value"] < lo) | (group["value"] > hi)]

        for _, row in ool.iterrows():
            anomalies.append(
                Anomaly(
                    timestamp=row["timestamp"].to_pydatetime(),
                    parameter=param,
                    value=row["value"],
                    limit_min=lo,
                    limit_max=hi,
                )
            )

    anomalies.sort(key=lambda a: a.timestamp)
    return anomalies, unknown


def detect_gaps(
    df: pd.DataFrame,
    threshold_s: int = GAP_THRESHOLD_S,
) -> list[TimeGap]:
    """Find gaps in the combined time series larger than threshold_s seconds."""
    # Use unique timestamps across all parameters
    timestamps = df["timestamp"].drop_duplicates().sort_values().reset_index(drop=True)

    gaps: list[TimeGap] = []
    for i in range(1, len(timestamps)):
        delta = (timestamps[i] - timestamps[i - 1]).total_seconds()
        if delta > threshold_s:
            gaps.append(
                TimeGap(
                    start=timestamps[i - 1].to_pydatetime(),
                    end=timestamps[i].to_pydatetime(),
                )
            )

    return gaps


def analyse(
    csv_path: Path,
    limits: dict[str, tuple[float, float]] = DEFAULT_LIMITS,
    gap_threshold_s: int = GAP_THRESHOLD_S,
) -> MonitorResult:
    """Full analysis pipeline — load, check limits, detect gaps."""
    df = load_telemetry(csv_path)

    anomalies, unknown = check_limits(df, limits)
    gaps = detect_gaps(df, gap_threshold_s)

    return MonitorResult(
        source_file=str(csv_path),
        total_rows=len(df),
        parameters_found=sorted(df["parameter"].unique().tolist()),
        time_start=df["timestamp"].min().to_pydatetime(),
        time_end=df["timestamp"].max().to_pydatetime(),
        anomalies=anomalies,
        gaps=gaps,
        unknown_parameters=unknown,
    )


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------
DIVIDER = "─" * 72

def print_report(result: MonitorResult, gap_threshold_s: int = GAP_THRESHOLD_S) -> None:
    duration = (
        (result.time_end - result.time_start) if result.time_start and result.time_end
        else None
    )

    print()
    print("╔" + "═" * 70 + "╗")
    print("║  SATELLITE TELEMETRY MONITOR — POST-PASS REPORT" + " " * 22 + "║")
    print("╚" + "═" * 70 + "╝")
    print()
    print(f"  Source   : {result.source_file}")
    print(f"  Start    : {result.time_start}")
    print(f"  End      : {result.time_end}")
    print(f"  Duration : {duration}")
    print(f"  Rows     : {result.total_rows}")
    print(f"  Params   : {', '.join(result.parameters_found)}")

    # -- Anomalies -----------------------------------------------------------
    print()
    print(DIVIDER)
    status = "✗ ANOMALIES DETECTED" if result.anomalies else "✓ ALL LIMITS NOMINAL"
    print(f"  LIMIT CHECKS  [{status}]")
    print(DIVIDER)

    if result.anomalies:
        for a in result.anomalies:
            print(a)
    else:
        print("  No out-of-limit values found.")

    if result.unknown_parameters:
        print()
        print(f"  ⚠  Parameters with no defined limits: {result.unknown_parameters}")

    # -- Gaps ----------------------------------------------------------------
    print()
    print(DIVIDER)
    gap_status = f"✗ {result.gap_count} GAP(S) DETECTED" if result.gaps else "✓ TIME SERIES CONTINUOUS"
    print(f"  TIME-GAP ANALYSIS  (threshold = {gap_threshold_s}s)  [{gap_status}]")
    print(DIVIDER)

    if result.gaps:
        for g in result.gaps:
            print(g)
    else:
        print("  No gaps detected.")

    # -- Summary -------------------------------------------------------------
    print()
    print(DIVIDER)
    print("  SUMMARY")
    print(DIVIDER)
    print(f"  Total readings   : {result.total_rows}")
    print(f"  Nominal          : {result.pass_count}")
    print(f"  Out-of-limit     : {result.anomaly_count}")
    print(f"  Time gaps        : {result.gap_count}")
    overall = "NOMINAL" if not result.anomalies and not result.gaps else "ACTION REQUIRED"
    print(f"  Overall status   : {overall}")
    print()


def to_json(result: MonitorResult, gap_threshold_s: int) -> dict:
    return {
        "source_file": result.source_file,
        "time_start": str(result.time_start),
        "time_end": str(result.time_end),
        "total_rows": result.total_rows,
        "parameters_found": result.parameters_found,
        "gap_threshold_s": gap_threshold_s,
        "anomalies": [
            {
                "timestamp": str(a.timestamp),
                "parameter": a.parameter,
                "value": a.value,
                "limit_min": a.limit_min,
                "limit_max": a.limit_max,
                "direction": a.direction,
            }
            for a in result.anomalies
        ],
        "gaps": [
            {
                "start": str(g.start),
                "end": str(g.end),
                "duration_s": g.duration.total_seconds(),
            }
            for g in result.gaps
        ],
        "summary": {
            "nominal_count": result.pass_count,
            "anomaly_count": result.anomaly_count,
            "gap_count": result.gap_count,
            "overall_status": (
                "NOMINAL" if not result.anomalies and not result.gaps
                else "ACTION REQUIRED"
            ),
        },
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Satellite telemetry post-pass analyser"
    )
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "data", "telemetry.csv")
    parser.add_argument(
        "csv_file",
        nargs="?",
        default=config_path,
        help="Path to telemetry CSV (default: data/telemetry.csv)",
    )
    parser.add_argument(
        "--gap-threshold",
        type=int,
        default=GAP_THRESHOLD_S,
        metavar="SECONDS",
        help=f"Flag gaps larger than N seconds (default: {GAP_THRESHOLD_S})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of the human report",
    )

    args = parser.parse_args()
    csv_path = Path(args.csv_file)

    if not csv_path.exists():
        print(f"ERROR: file not found — {csv_path}", file=sys.stderr)
        sys.exit(1)

    result = analyse(csv_path, gap_threshold_s=args.gap_threshold)

    if args.json:
        print(json.dumps(to_json(result, args.gap_threshold), indent=2))
    else:
        print_report(result, gap_threshold_s=args.gap_threshold)


if __name__ == "__main__":
    main()
