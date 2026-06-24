#!/usr/bin/env bash
# build_exe.sh — produces a standalone CLI executable via PyInstaller
# Usage: bash build_exe.sh
set -e

echo "── Installing dependencies ──────────────────────────"
pip install -r requirements.txt --quiet

echo "── Generating sample data ───────────────────────────"
python generate_sample_data.py

echo "── Building executable ──────────────────────────────"
pyinstaller \
  --onefile \
  --name satops-monitor \
  --add-data "data;data" \
  --add-data "templates;templates" \
  telemetry_monitor.py app.py

echo ""
echo "✓ Executable ready: dist/satops-monitor"
echo ""
echo "Usage examples:"
echo "  ./dist/satops-monitor"
echo "  ./dist/satops-monitor data/telemetry.csv --gap-threshold 30"
echo "  ./dist/satops-monitor data/telemetry.csv --json"
