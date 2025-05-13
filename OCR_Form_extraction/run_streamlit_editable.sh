#!/bin/bash

# Check if Python is installed
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    echo "Python n'est pas installé. Veuillez installer Python 3."
    exit 1
fi

# Check if Streamlit is installed
if ! $PYTHON_CMD -c "import streamlit" &>/dev/null; then
    echo "Streamlit n'est pas installé. Installation en cours..."
    $PYTHON_CMD -m pip install streamlit
fi

# Check if pandas is installed
if ! $PYTHON_CMD -c "import pandas" &>/dev/null; then
    echo "Pandas n'est pas installé. Installation en cours..."
    $PYTHON_CMD -m pip install pandas
fi

# Determine the absolute path of the app directory
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/app"

# Launch the Streamlit application with the editable interface without specifying a port
cd "$APP_DIR" && $PYTHON_CMD -m streamlit run streamlit_app_editable.py 