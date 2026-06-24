"""
app.py — Flask web interface for the telemetry monitor.
Render will run this via:  gunicorn app:app
"""

import io
import json
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from telemetry_monitor import DEFAULT_LIMITS, GAP_THRESHOLD_S, analyse, to_json
from generate_sample_data import generate

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024   # 10 MB upload cap

UPLOAD_DIR = Path("data")
UPLOAD_DIR.mkdir(exist_ok=True)
SAMPLE_CSV = UPLOAD_DIR / "telemetry.csv"


def _ensure_sample():
    """Generate sample data on first boot if not already present."""
    if not SAMPLE_CSV.exists():
        generate(str(SAMPLE_CSV))


@app.route("/")
def index():
    _ensure_sample()
    return render_template("index.html")


@app.route("/api/analyse", methods=["POST"])
def api_analyse():
    """
    POST /api/analyse
    Body: multipart/form-data with optional 'file' field and 'gap_threshold'.
    If no file is uploaded, runs against the built-in sample data.
    """
    gap_threshold = int(request.form.get("gap_threshold", GAP_THRESHOLD_S))

    if "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        upload_path = UPLOAD_DIR / "uploaded.csv"
        f.save(upload_path)
        csv_path = upload_path
    else:
        _ensure_sample()
        csv_path = SAMPLE_CSV

    try:
        result = analyse(csv_path, limits=DEFAULT_LIMITS, gap_threshold_s=gap_threshold)
        return jsonify(to_json(result, gap_threshold))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/sample")
def api_sample():
    """Return the sample CSV content so the UI can show it."""
    _ensure_sample()
    return SAMPLE_CSV.read_text(), 200, {"Content-Type": "text/plain"}


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
