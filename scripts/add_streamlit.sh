#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# add_streamlit.sh — Adds Streamlit dashboard dependencies and Makefile target
# Run from the retail-analytics-platform root directory.
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

echo "── Step 1: Adding Streamlit + Plotly to requirements.txt ──"

# Only append if not already present
grep -q "streamlit" requirements.txt 2>/dev/null || cat >> requirements.txt << 'DEPS'

# Dashboard
streamlit>=1.31.0
plotly>=5.18.0
db-dtypes>=1.2.0
DEPS

echo "   ✅ requirements.txt updated"

echo ""
echo "── Step 2: Adding dashboard target to Makefile ──"

# Only append if not already present
if ! grep -q "dashboard" Makefile 2>/dev/null; then
    cat >> Makefile << 'MK'

# ── Dashboard ──
dashboard:  ## Launch the Streamlit analytics dashboard
	streamlit run app/dashboard.py

dashboard-dev:  ## Launch dashboard in dev mode (auto-reload)
	streamlit run app/dashboard.py --server.runOnSave true
MK
    echo "   ✅ Makefile updated"
else
    echo "   ⏭  Makefile already has dashboard target"
fi

echo ""
echo "── Step 3: Installing new dependencies ──"
pip install streamlit plotly db-dtypes --quiet

echo ""
echo "── Done! ──"
echo ""
echo "Launch the dashboard:"
echo "  export GCP_PROJECT=nifty-quanta-486115-d6"
echo "  make dashboard"
echo ""
echo "Or directly:"
echo "  streamlit run app/dashboard.py"
