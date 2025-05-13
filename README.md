# Phase 1: Field Extraction from National Insurance Forms

This component extracts information from ביטוח לאומי (National Insurance Institute) forms using Azure Document Intelligence for OCR and Azure OpenAI for structured data extraction.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Usage](#usage)
  - [Running the Application](#running-the-application)
  - [Generating OCR Statistics](#generating-ocr-statistics)
  - [Resetting Statistics](#resetting-statistics)
- [Implementation Details](#implementation-details)
- [File Structure](#file-structure)
- [Troubleshooting](#troubleshooting)

## Overview

This system extracts information from National Insurance Institute forms using a combination of OCR and NLP technologies. It processes forms in both Hebrew and English, provides an interactive UI for reviewing and editing extracted data, and includes tools for analyzing extraction accuracy.

## Features

- **Document Processing**: Extract text and layout information from PDF and image files
- **Structured Data Extraction**: Convert raw OCR text into structured JSON format
- **Interactive UI**: Review and edit extracted information
- **Bilingual Support**: Handle forms in Hebrew and English
- **Validation**: Verify the accuracy and completeness of extracted data
- **Statistics**: Generate reports on extraction performance and accuracy
- **Self-contained**: All scripts automatically install their dependencies

## System Architecture

The system consists of three main components:

1. **Form Extraction Application**: A Streamlit-based UI for uploading forms, extracting data, and editing results
2. **OCR Statistics Generator**: A tool to analyze extraction accuracy and generate visual reports
3. **Statistics Reset Utility**: A utility to reset statistics and start fresh

### Technologies Used

- **Azure Document Intelligence**: For high-quality OCR and layout analysis
- **Azure OpenAI (GPT-4)**: For structured data extraction from raw text
- **Streamlit**: For the interactive web interface
- **Matplotlib/Pandas**: For data visualization and statistics
- **Python**: Core programming language

## Installation

All scripts in this project automatically check and install their dependencies. You only need Python 3.6+ installed on your system.

### API Keys

You'll need to set up a `.env` file in the `phase1` directory with your Azure credentials:

```
# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=your_endpoint_here
AZURE_DOCUMENT_INTELLIGENCE_KEY=your_key_here

# OpenAI
OPENAI_API_KEY=your_openai_key_here
```

## Usage

### Running the Application

Use the master script that handles everything:

```bash
./FieldExtraction_phase1.sh
```

This script will:
1. Check and install all required dependencies
2. Verify the environment configuration
3. Create necessary directories
4. Launch the Streamlit application

Alternatively, you can run the Streamlit application directly:

```bash
cd phase1
bash run_streamlit_editable.sh
```

Once running, the application will be available at http://localhost:8501 in your browser.

### Generating OCR Statistics

To analyze the performance of the OCR and extraction processes:

```bash
cd phase1
bash generate_ocr_stats.sh
```

This will:
1. Analyze all extraction files in the `extractions` directory
2. Generate a comprehensive HTML report with charts and metrics
3. Open the report in your default browser

The report includes:
- Overall reliability scores
- Comparison of original OCR vs. corrected data
- Field-specific accuracy metrics
- Recommendations for improvement

### Resetting Statistics

To reset the statistics and start fresh:

```bash
cd phase1
bash reset_stats.sh
```

This will:
1. Create a backup of existing extraction files
2. Clear all extraction data
3. Remove the statistics report

## Implementation Details

### OCR Process

The system uses Azure Document Intelligence's Layout model to extract text and positional information from documents. The OCR process:

1. Preprocesses the document to enhance text recognition
2. Analyzes only the first page of multi-page documents
3. Supports Hebrew and English text
4. Retains confidence scores for each extracted text element

### Data Extraction Logic

After OCR, the raw text is processed by Azure OpenAI to extract structured information:

1. The raw text is sent to GPT-4 with a specialized prompt
2. The model identifies relevant fields and their values
3. The structured data is returned in JSON format
4. The user can manually correct any errors

### Statistics Analysis

The statistics component analyzes extraction accuracy by:

1. Comparing original OCR results with corrected values
2. Calculating reliability scores for each field
3. Generating visualizations of key metrics
4. Providing actionable improvement recommendations

## File Structure

```
phase1/
├── app/                      # Main application
│   ├── utils/                # Utility modules
│   │   ├── ocr.py            # OCR extraction logic
│   │   ├── openai_extractor.py # OpenAI integration
│   │   └── validation.py     # Data validation
│   ├── config.py             # Configuration settings
│   └── streamlit_app_editable.py # Streamlit UI
├── extractions/              # Extracted data (JSON)
├── extractions_backup/       # Backup of extracted data
├── generate_ocr_stats.py     # Statistics generation script
├── generate_ocr_stats.sh     # Statistics shell script
├── requirements.txt          # Python dependencies
├── reset_stats.sh            # Reset utility
├── run_streamlit_editable.sh # Application launch script
└── FieldExtraction_phase1.sh # Master script (in parent dir)
```

## Troubleshooting

### Common Issues

- **Missing API Keys**: Ensure you've added the required API keys to the `.env` file
- **OCR Quality Issues**: For better results, use high-quality scans and ensure proper document alignment
- **Language Detection**: If text is not recognized correctly, try specifying the language manually

If you encounter any other issues, please check the application logs for more detailed error messages. 