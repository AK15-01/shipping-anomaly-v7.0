#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
PORT=8503
echo "========================================"
echo "Starting 03_shipping_anomaly_detector"
echo "Entry point: app.py"
echo "Local URL: http://localhost:${PORT}"
echo "========================================"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found. Please install Python 3.10+."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Opening Streamlit in your browser..."
echo "Copy this link if the browser does not open: http://localhost:${PORT}"
python -m streamlit run "app.py" --server.port "${PORT}" --server.address localhost
