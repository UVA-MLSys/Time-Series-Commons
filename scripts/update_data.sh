#!/bin/bash
# Quick update script for Time Series Commons data
# Converts CSV to JSON format for the website

set -e  # Exit on error

echo "🚀 Time Series Commons - Data Update Script"
echo "============================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Check if CSV file exists
CSV_FILE="Time-Series Common_Data_1-5-2026_COMBINED2 - Combinedv10.csv"
if [ ! -f "$CSV_FILE" ]; then
    echo "❌ Error: CSV file not found: $CSV_FILE"
    echo "   Please ensure the CSV file is in the project root directory."
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "❌ Error: Python not found. Please install Python 3."
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

echo "Using Python: $PYTHON_CMD"
echo ""

# Run the conversion script
$PYTHON_CMD scripts/csv_to_json.py

echo ""
echo "✅ Update complete!"
echo ""
echo "Next steps:"
echo "  1. Refresh your website to see the changes"
echo "  2. If running locally, restart your web server (if needed)"
echo ""
