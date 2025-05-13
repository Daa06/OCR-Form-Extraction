#!/bin/bash

# Get the script path
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
EXTRACTIONS_DIR="$SCRIPT_DIR/extractions"
REPORT_FILE="$SCRIPT_DIR/ocr_reliability_report.html"

# Activate virtual environment if needed
# source venv/bin/activate

echo "Generating OCR statistics report..."
echo "Extractions directory: $EXTRACTIONS_DIR"
echo "Output report: $REPORT_FILE"

# Run the statistics generation script
python3 "$SCRIPT_DIR/generate_ocr_stats.py" --extractions "$EXTRACTIONS_DIR" --output "$REPORT_FILE" --open

# Display a message
echo "Completed!" 