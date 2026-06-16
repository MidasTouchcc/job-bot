#!/bin/bash
echo ""
echo "══════════════════════════════════════════════"
echo "   🔍  Andre's Job Bot — Starting..."
echo "══════════════════════════════════════════════"
cd "$(dirname "$0")"
if ! command -v python3 &>/dev/null; then
  echo "❌  Python 3 not found. Install from python.org"
  exit 1
fi
echo "✅  Python: $(python3 --version)"
python3 -c "import flask, requests" 2>/dev/null || {
  echo "📦  Installing packages..."
  pip3 install -r requirements.txt --break-system-packages 2>/dev/null \
    || pip3 install -r requirements.txt
}
echo "🚀  Opening at http://localhost:5001"
echo "    Press Ctrl+C to stop."
echo "══════════════════════════════════════════════"
echo ""
python3 app.py
