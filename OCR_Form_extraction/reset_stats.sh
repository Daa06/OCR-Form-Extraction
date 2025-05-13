#!/bin/bash

# Script to reset OCR statistics and HTML report

# Get the script path
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
EXTRACTIONS_DIR="$SCRIPT_DIR/extractions"
REPORT_FILE="$SCRIPT_DIR/ocr_reliability_report.html"

# Check if Python is installed
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    echo "Error: Python is not installed. Please install Python 3."
    exit 1
fi

# Function to install required packages
install_requirements() {
    echo "Checking required dependencies..."
    REQUIRED_PACKAGES="pandas matplotlib jinja2 python-dotenv"
    
    for package in $REQUIRED_PACKAGES; do
        if ! $PYTHON_CMD -c "import $package" &>/dev/null; then
            echo "Installing $package..."
            $PYTHON_CMD -m pip install $package
        else
            echo "✅ $package is already installed"
        fi
    done
    
    echo "All dependencies verified and installed ✅"
}

# Install required packages
install_requirements

echo "Resetting OCR statistics..."

# 1. Backup existing extractions (optional)
BACKUP_DIR="$SCRIPT_DIR/extractions_backup/backup_$(date +%Y%m%d_%H%M%S)"
if [ -d "$EXTRACTIONS_DIR" ] && [ "$(ls -A $EXTRACTIONS_DIR)" ]; then
    echo "Backing up existing extractions to $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    cp "$EXTRACTIONS_DIR"/*.json "$BACKUP_DIR/" 2>/dev/null
fi

# 2. Delete extraction files
echo "Deleting extraction files..."
rm -f "$EXTRACTIONS_DIR"/*.json

# 3. Delete HTML report if it exists
if [ -f "$REPORT_FILE" ]; then
    echo "Deleting HTML report..."
    rm -f "$REPORT_FILE"
fi

echo "✅ Reset completed successfully!"
echo "You can now restart the application and upload new documents." 