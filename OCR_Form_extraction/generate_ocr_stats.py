#!/usr/bin/env python3
import os
import sys
import argparse
import importlib
import subprocess
import pkg_resources

def check_and_install_dependencies():
    """Check and install required dependencies"""
    required_packages = {
        'pandas': 'pandas>=1.3.0',
        'matplotlib': 'matplotlib>=3.5.0',
        'jinja2': 'jinja2>=3.0.0',
        'python-dotenv': 'python-dotenv>=0.19.0'
    }
    
    missing_packages = []
    
    for package, requirement in required_packages.items():
        try:
            importlib.import_module(package)
            print(f"✅ {package} is already installed")
        except ImportError:
            missing_packages.append(requirement)
    
    if missing_packages:
        print(f"Installing missing dependencies: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
            print("All dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"Error installing dependencies: {e}")
            sys.exit(1)

# Verify and install dependencies before imports that may fail
check_and_install_dependencies()

# Now import other modules that may require installation
import json
import webbrowser
import re
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime
from jinja2 import Template

def main():
    parser = argparse.ArgumentParser(description="Generate OCR statistics report")
    parser.add_argument("--extractions", type=str, default="./extractions",
                      help="Directory containing extraction JSON files")
    parser.add_argument("--output", type=str, default="ocr_reliability_report.html",
                      help="Output path for the HTML report")
    parser.add_argument("--open", action="store_true",
                      help="Open the report in browser after generation")
    args = parser.parse_args()
    
    print("✅ All dependencies verified and installed")
    
    # Check if the extractions directory exists
    extraction_dir = args.extractions
    if not os.path.isabs(extraction_dir):
        # Get the absolute path
        app_dir = os.path.dirname(os.path.abspath(__file__))
        extraction_dir = os.path.join(app_dir, extraction_dir)
    
    print(f"Extractions directory: {extraction_dir}")
    
    if not os.path.exists(extraction_dir):
        print(f"Extractions directory does not exist: {extraction_dir}")
        sys.exit(1)
    
    # Get all JSON files
    extraction_files = [os.path.join(extraction_dir, f) for f in os.listdir(extraction_dir) 
                       if f.endswith('.json')]
    
    if not extraction_files:
        print(f"No extraction files found in {extraction_dir}")
        sys.exit(1)
    
    print(f"Number of extraction files found: {len(extraction_files)}")
    
    # Analyze the extractions
    stats = analyze_extractions(extraction_files)
    
    # Generate the HTML report
    html_report = generate_html_report(stats)
    
    # Write the report to a file
    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_report)
    
    print(f"Report generated: {output_path}")
    
    # Open the report in browser if requested
    if args.open:
        try:
            webbrowser.open('file://' + os.path.abspath(output_path))
        except Exception as e:
            print(f"Unable to open browser: {e}")

def analyze_extractions(extraction_files):
    """Analyzes extraction files to generate statistics"""
    # List of fields of interest specified with their expected format
    important_fields = {
        'firstName': {'label': 'First Name', 'format': r'^.+$'},
        'lastName': {'label': 'Last Name', 'format': r'^.+$'},
        'idNumber': {'label': 'ID Number (9-digit)', 'format': r'^\d{9}$'},
        'gender': {'label': 'Gender', 'format': r'^(Male|Female|זכר|נקבה)$'},
        'dateOfInjury': {'label': 'Date of Injury', 'format': r'^.+$'},
        'postalCode': {'label': 'Postal Code', 'format': r'^\d{5,7}$'},
        'accidentLocation': {'label': 'Accident Location', 'format': r'^.+$'}
    }
    
    # List of additional fields to monitor
    additional_fields = {
        'dateOfBirth.day': {'format': r'^(0?[1-9]|[12][0-9]|3[01])$'},
        'dateOfBirth.month': {'format': r'^(0?[1-9]|1[0-2])$'},
        'dateOfBirth.year': {'format': r'^(19|20)\d{2}$'}
    }
    
    # Structure to store statistics
    stats = {
        "documents": [],
        "field_stats": {},
        "important_fields": list(important_fields.keys()) + ['age'],
        "unique_documents": set(),  # Set to track unique documents
        "document_fingerprints": {}  # Dictionary to store document fingerprints
    }
    
    # Initialize statistics for all important fields
    for field in important_fields.keys():
        stats["field_stats"][field] = {
            "total": 0,
            "empty": 0,
            "valid": 0,
            "invalid": 0,
            "corrected": 0,
            "original_valid": 0,
            "original_invalid": 0,
            "correction_improved": 0,
            "correction_worsened": 0
        }
    
    # Initialize also for calculated age
    stats["field_stats"]["age"] = {
        "total": 0,
        "empty": 0,
        "valid": 0,
        "invalid": 0,
        "corrected": 0,
        "original_valid": 0,
        "original_invalid": 0,
        "correction_improved": 0,
        "correction_worsened": 0
    }
    
    # Organization of files by real document (not just by file ID)
    document_files = {}
    
    # Read all extraction files
    all_extractions = []
    for file_path in extraction_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                extraction_data = json.load(f)
                extraction_data["_file_path"] = file_path
                all_extractions.append(extraction_data)
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
    
    # Sort extractions by timestamp (most recent first)
    all_extractions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    # Function to create a document fingerprint based on original data
    def get_document_fingerprint(extraction):
        original = extraction.get("original_extraction", {})
        # Use a combination of fields to identify a unique document
        keys = ['firstName', 'lastName', 'dateOfBirth', 'accidentDescription']
        values = []
        for key in keys:
            if key in original:
                if isinstance(original[key], dict):
                    # For nested structures like dateOfBirth
                    nested_values = [str(v) for v in original[key].values() if v]
                    values.append("_".join(nested_values))
                else:
                    values.append(str(original[key]))
        
        # Create a document fingerprint
        fingerprint = "_".join(values)
        return fingerprint
    
    # Group extractions by document fingerprint (real document)
    for extraction in all_extractions:
        fingerprint = get_document_fingerprint(extraction)
        if fingerprint not in document_files:
            document_files[fingerprint] = []
        document_files[fingerprint].append(extraction)
    
    # Process each unique document
    for fingerprint, versions in document_files.items():
        try:
            # Use the most recent version of the document
            extraction_data = versions[0]  # Already sorted by date (most recent first)
            file_path = extraction_data["_file_path"]
            
            # Add the fingerprint to the set of unique documents
            stats["unique_documents"].add(fingerprint)
            
            # Use a more stable ID based on the fingerprint
            doc_id = f"doc_{len(stats['unique_documents'])}"
            has_been_corrected = extraction_data.get("has_been_corrected", False)
            
            # For debugging
            stats["document_fingerprints"][doc_id] = {
                "fingerprint": fingerprint,
                "versions": len(versions),
                "files": [os.path.basename(v["_file_path"]) for v in versions]
            }
            
            # Get original and final extractions
            original_extraction = extraction_data.get("original_extraction", {})
            final_extraction = extraction_data.get("final_extraction", original_extraction)
            
            # Create an entry for this document
            doc_entry = {
                "id": doc_id,
                "file_id": extraction_data.get("id", os.path.basename(file_path)),
                "timestamp": extraction_data.get("timestamp", datetime.now().isoformat()),
                "has_been_corrected": has_been_corrected,
                "versions": len(versions),
                "field_results": {}
            }
            
            # Add missing fields that should be present
            for field in important_fields:
                if field not in original_extraction:
                    original_extraction[field] = ""
                if field not in final_extraction:
                    final_extraction[field] = ""
            
            # Calculate age once for this document
            age_value = ""
            age_valid = False
            try:
                if "dateOfBirth" in original_extraction and all(original_extraction["dateOfBirth"].get(k) for k in ["day", "month", "year"]):
                    dob_day = int(original_extraction["dateOfBirth"]["day"])
                    dob_month = int(original_extraction["dateOfBirth"]["month"])
                    dob_year = int(original_extraction["dateOfBirth"]["year"])
                    
                    # Create a date object for the date of birth
                    dob = datetime(dob_year, dob_month, dob_day)
                    
                    # Calculate age in years (without decimals)
                    now = datetime.now()
                    age = now.year - dob.year - ((now.month, now.day) < (dob.month, dob.day))
                    
                    # Check if age is valid (between 0 and 120)
                    if 0 <= age <= 120:
                        age_value = age
                        age_valid = True
            except Exception as e:
                print(f"Error calculating age: {str(e)}")
            
            # Flatten dictionaries for easier analysis
            flat_original = flatten_dict(original_extraction)
            flat_final = flatten_dict(final_extraction)
            
            # Process important fields first
            for field, field_info in important_fields.items():
                orig_value = flat_original.get(field, "")
                final_value = flat_final.get(field, orig_value)
                
                # Check original and final format
                orig_format_status = check_format(field, orig_value, field_info['format'])
                final_format_status = check_format(field, final_value, field_info['format'])
                
                # Determine if correction improved or worsened the format
                was_corrected = orig_value != final_value
                correction_improved = was_corrected and orig_format_status != "valid" and final_format_status == "valid"
                correction_worsened = was_corrected and orig_format_status == "valid" and final_format_status != "valid"
                
                field_result = {
                    "original_value": orig_value,
                    "final_value": final_value,
                    "original_format": orig_format_status,
                    "final_format": final_format_status,
                    "was_corrected": was_corrected,
                    "correction_improved": correction_improved,
                    "correction_worsened": correction_worsened
                }
                
                doc_entry["field_results"][field] = field_result
                
                # Update global statistics for this field
                stats["field_stats"][field]["total"] += 1
                
                # Final format status
                if final_format_status == "empty":
                    stats["field_stats"][field]["empty"] += 1
                elif final_format_status == "valid":
                    stats["field_stats"][field]["valid"] += 1
                else:
                    stats["field_stats"][field]["invalid"] += 1
                
                # Original format status
                if orig_format_status == "valid":
                    stats["field_stats"][field]["original_valid"] += 1
                elif orig_format_status != "empty":
                    stats["field_stats"][field]["original_invalid"] += 1
                
                # If corrected
                if was_corrected:
                    stats["field_stats"][field]["corrected"] += 1
                    if correction_improved:
                        stats["field_stats"][field]["correction_improved"] += 1
                    elif correction_worsened:
                        stats["field_stats"][field]["correction_worsened"] += 1
            
            # Process age separately (since calculated)
            if age_valid:
                format_status = "valid"
            elif age_value == "":
                format_status = "empty"
            else:
                format_status = "invalid"
            
            doc_entry["field_results"]["age"] = {
                "original_value": age_value,
                "final_value": age_value,  # Age remains the same
                "original_format": format_status,
                "final_format": format_status,
                "was_corrected": False,
                "correction_improved": False,
                "correction_worsened": False
            }
            
            # Update statistics for age
            stats["field_stats"]["age"]["total"] += 1
            stats["field_stats"]["age"][format_status] += 1
            if format_status == "valid":
                stats["field_stats"]["age"]["original_valid"] += 1
            elif format_status != "empty":
                stats["field_stats"]["age"]["original_invalid"] += 1
            
            # Add entry for this document
            stats["documents"].append(doc_entry)
            
        except Exception as e:
            print(f"Error analyzing document (fingerprint: {fingerprint}): {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Add unique document count
    stats["unique_document_count"] = len(stats["unique_documents"])
    # Remove set as it's not serializable in JSON
    del stats["unique_documents"]
    
    return stats

def check_format(field, value, format_pattern):
    """Checks if the value respects the expected format for the field"""
    if not value or str(value).strip() == "":
        return "empty"
    
    try:
        if re.match(format_pattern, str(value)):
            return "valid"
        else:
            return "invalid"
    except:
        return "invalid"

def flatten_dict(d, parent_key=''):
    """Flattens a nested dictionary"""
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key))
        else:
            items[new_key] = v
    return items

def generate_reliability_scores(stats):
    """Generates reliability scores for each field"""
    reliability_scores = {}
    
    for field, field_stats in stats["field_stats"].items():
        total = field_stats["total"]
        if total == 0:
            reliability_scores[field] = 0
            continue
        
        # Score based on final validity and improvement through correction
        valid_rate = field_stats["valid"] / total if total > 0 else 0
        improvement_rate = field_stats["correction_improved"] / total if total > 0 else 0
        worsening_rate = field_stats["correction_worsened"] / total if total > 0 else 0
        
        # Reliability score: final validity + improvements - deteriorations
        reliability = valid_rate + (improvement_rate * 0.1) - (worsening_rate * 0.2)
        reliability_scores[field] = round(max(0, min(100, reliability * 100)), 1)
    
    return reliability_scores

def generate_html_report(stats):
    """Génère un rapport HTML avec les statistiques"""
    reliability_scores = generate_reliability_scores(stats)
    
    # Créer des libellés plus descriptifs pour les champs
    field_labels = {
        'firstName': 'First Name',
        'lastName': 'Last Name',
        'idNumber': 'ID Number (9-digit)',
        'gender': 'Gender',
        'age': 'Age (0-120)',
        'dateOfInjury': 'Date of Injury',
        'postalCode': 'Postal Code',
        'accidentLocation': 'Accident Location'
    }
    
    # Utiliser les champs importants définis
    important_fields = stats.get('important_fields', [])
    filtered_scores = {field: reliability_scores.get(field, 0) for field in important_fields if field in reliability_scores}
    
    # Préparer les données pour les graphiques
    fields = [field_labels.get(field, field) for field in filtered_scores.keys()]
    scores = list(filtered_scores.values())
    
    # Créer des données pour le graphique de validité originale vs finale
    original_valid_rates = []
    final_valid_rates = []
    correction_improved_rates = []
    
    for field in filtered_scores.keys():
        field_stats = stats["field_stats"].get(field, {})
        total = field_stats.get("total", 1)
        
        original_valid = field_stats.get("original_valid", 0) / total * 100
        final_valid = field_stats.get("valid", 0) / total * 100
        improved = field_stats.get("correction_improved", 0) / total * 100
        
        original_valid_rates.append(round(original_valid, 1))
        final_valid_rates.append(round(final_valid, 1))
        correction_improved_rates.append(round(improved, 1))
    
    # Créer le graphique pour la fiabilité
    plt.figure(figsize=(12, 6))
    bars = plt.barh(fields, scores, color='skyblue')
    plt.xlabel('Reliability Score (%)')
    plt.title('OCR Reliability by Field')
    plt.xlim(0, 100)
    
    # Ajouter les valeurs sur les barres
    for bar, score in zip(bars, scores):
        plt.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, f'{score}%',
                va='center')
    
    # Convertir le graphique en image base64 pour l'HTML
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    reliability_chart = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    
    # Créer un graphique comparatif (avant/après correction)
    plt.figure(figsize=(12, 8))
    x = range(len(fields))
    width = 0.35
    
    # Barres pour OCR original et final
    plt.barh([i - width/2 for i in x], original_valid_rates, width, color='lightcoral', label='Original OCR Valid')
    plt.barh([i + width/2 for i in x], final_valid_rates, width, color='mediumseagreen', label='After Correction Valid')
    
    plt.yticks(x, fields)
    plt.xlabel('Valid Rate (%)')
    plt.title('OCR Improvement After Correction')
    plt.xlim(0, 100)
    plt.legend()
    
    # Ajouter les valeurs sur les barres
    for i, (orig, final) in enumerate(zip(original_valid_rates, final_valid_rates)):
        plt.text(orig + 1, i - width/2, f'{orig}%', va='center')
        plt.text(final + 1, i + width/2, f'{final}%', va='center')
    
    # Convertir le graphique en image base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    improvement_chart = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    
    # Créer un graphique pour le taux de correction
    plt.figure(figsize=(12, 6))
    correction_rates = []
    improvement_rates = []
    worsening_rates = []
    
    for field in filtered_scores.keys():
        field_stats = stats["field_stats"].get(field, {})
        total = field_stats.get("total", 1)
        
        correction_rate = field_stats.get("corrected", 0) / total * 100
        improvement_rate = field_stats.get("correction_improved", 0) / total * 100
        worsening_rate = field_stats.get("correction_worsened", 0) / total * 100
        
        correction_rates.append(round(correction_rate, 1))
        improvement_rates.append(round(improvement_rate, 1))
        worsening_rates.append(round(worsening_rate, 1))
    
    x = range(len(fields))
    width = 0.3
    
    plt.barh([i for i in x], correction_rates, width, color='#3498db', label='Correction Rate')
    plt.barh([i + width for i in x], improvement_rates, width, color='#2ecc71', label='Improvement Rate')
    plt.barh([i + width*2 for i in x], worsening_rates, width, color='#e74c3c', label='Worsening Rate')
    
    plt.yticks(x, fields)
    plt.xlabel('Rate (%)')
    plt.title('OCR Correction Analysis')
    plt.xlim(0, 100)
    plt.legend()
    
    for i, rate in enumerate(correction_rates):
        if rate > 5:  # Afficher seulement si assez d'espace
            plt.text(rate + 1, i, f'{rate}%', va='center')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    correction_chart = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    
    # Générer des recommandations
    recommendations = []
    problem_fields = [(field, score) for field, score in filtered_scores.items() if score < 70]
    problem_fields.sort(key=lambda x: x[1])
    
    for field, score in problem_fields:
        field_stats = stats["field_stats"].get(field, {})
        field_label = field_labels.get(field, field)
        
        total = max(field_stats.get("total", 1), 1)
        empty_rate = field_stats.get("empty", 0) / total
        invalid_rate = field_stats.get("invalid", 0) / total
        correction_rate = field_stats.get("corrected", 0) / total
        
        if empty_rate > 0.3:
            recommendations.append(f"🔍 Field '{field_label}' is often empty ({empty_rate*100:.1f}%). Consider improving data capture.")
        
        if invalid_rate > 0.3:
            recommendations.append(f"❌ Field '{field_label}' often has incorrect format ({invalid_rate*100:.1f}%). Review OCR settings for this field type.")
        
        if correction_rate > 0.5:
            recommendations.append(f"✏️ Field '{field_label}' requires frequent manual correction ({correction_rate*100:.1f}%). Consider additional training for this field.")
    
    # Préparer les données de table
    table_data = []
    for field in filtered_scores.keys():
        field_stats = stats["field_stats"].get(field, {})
        if field_stats.get("total", 0) > 0:
            total = field_stats.get("total", 0)
            
            original_valid_rate = (field_stats.get("original_valid", 0) / total) * 100
            final_valid_rate = (field_stats.get("valid", 0) / total) * 100
            empty_rate = (field_stats.get("empty", 0) / total) * 100
            correction_rate = (field_stats.get("corrected", 0) / total) * 100
            improved_rate = (field_stats.get("correction_improved", 0) / total) * 100
            worsened_rate = (field_stats.get("correction_worsened", 0) / total) * 100
            
            # Calculer le changement (amélioration ou détérioration)
            change = final_valid_rate - original_valid_rate
            change_class = "improved" if change > 0 else "worsened" if change < 0 else "unchanged"
            change_icon = "↗️" if change > 0 else "↘️" if change < 0 else "→"
            
            table_data.append({
                "field": field_labels.get(field, field),
                "total": total,
                "reliability": f"{filtered_scores.get(field, 0)}%",
                "original_valid_rate": f"{original_valid_rate:.1f}%",
                "final_valid_rate": f"{final_valid_rate:.1f}%",
                "change": f"{change_icon} {change:.1f}%",
                "change_class": change_class,
                "empty_rate": f"{empty_rate:.1f}%",
                "correction_rate": f"{correction_rate:.1f}%",
                "improved_rate": f"{improved_rate:.1f}%",
                "worsened_rate": f"{worsened_rate:.1f}%"
            })
    
    # Trier par fiabilité (croissante)
    table_data.sort(key=lambda x: float(x["reliability"].replace("%", "")))
    
    # Template HTML pour le rapport
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OCR Reliability Report</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; color: #333; }
            h1, h2 { color: #2a5885; }
            .summary { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            .chart { margin: 20px 0; max-width: 100%; border: 1px solid #ddd; padding: 10px; border-radius: 5px; }
            
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
            th { background-color: #f2f2f2; position: sticky; top: 0; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            
            .recommendations { background-color: #f0f7ff; padding: 15px; border-radius: 5px; border-left: 4px solid #2a5885; }
            .improved { color: green; font-weight: bold; }
            .worsened { color: red; font-weight: bold; }
            .unchanged { color: gray; }
            
            .low-reliability { background-color: #ffebee; }
            .medium-reliability { background-color: #fff8e1; }
            .high-reliability { background-color: #e8f5e9; }
            
            .tooltip { position: relative; display: inline-block; cursor: help; }
            .tooltip .tooltiptext { visibility: hidden; width: 200px; background-color: #555; color: #fff; text-align: center; border-radius: 6px; padding: 5px; position: absolute; z-index: 1; bottom: 125%; left: 50%; margin-left: -100px; opacity: 0; transition: opacity 0.3s; }
            .tooltip:hover .tooltiptext { visibility: visible; opacity: 1; }
            
            .stat-cards { display: flex; justify-content: space-between; margin-bottom: 20px; }
            .stat-card {
                background-color: #fff;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                padding: 15px;
                margin-right: 2%;
                text-align: center;
                width: 30%;
            }
            .stat-value {
                font-size: 24px;
                font-weight: bold;
                color: #2a5885;
                margin: 10px 0;
            }
            .stat-label {
                font-size: 14px;
                color: #666;
            }
        </style>
    </head>
    <body>
        <h1>OCR Reliability Report</h1>
        
        <div class="summary">
            <p><strong>Generated on:</strong> {{ timestamp }}</p>
            
            <div class="stat-cards">
                <div class="stat-card">
                    <div class="stat-label">Unique Documents</div>
                    <div class="stat-value">{{ unique_doc_count }}</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-label">Total Analyses</div>
                    <div class="stat-value">{{ doc_count }}</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-label">Overall Reliability</div>
                    <div class="stat-value">{{ overall_reliability }}%</div>
                </div>
            </div>
            
            <p><strong>Note:</strong> When a document has been corrected multiple times, only the latest version is considered for statistical analysis.</p>
        </div>
        
        <h2>Field Reliability Overview</h2>
        <div class="chart">
            <img src="data:image/png;base64,{{ reliability_chart }}" alt="Reliability Chart" width="100%">
        </div>
        
        <h2>OCR Improvement After Correction</h2>
        <div class="chart">
            <img src="data:image/png;base64,{{ improvement_chart }}" alt="Improvement Chart" width="100%">
        </div>
        
        <h2>Correction Analysis</h2>
        <div class="chart">
            <img src="data:image/png;base64,{{ correction_chart }}" alt="Correction Chart" width="100%">
        </div>
        
        <h2>Detailed Field Statistics</h2>
        <table>
            <tr>
                <th>Field</th>
                <th>Documents</th>
                <th>Reliability</th>
                <th>Original Valid %</th>
                <th>Final Valid %</th>
                <th>Change</th>
                <th>Empty Rate</th>
                <th>Correction Rate</th>
                <th>Improved</th>
                <th>Worsened</th>
            </tr>
            {% for row in table_data %}
            <tr class="
                {% if row.reliability|float < 50 %}low-reliability
                {% elif row.reliability|float < 75 %}medium-reliability
                {% else %}high-reliability{% endif %}">
                <td>{{ row.field }}</td>
                <td>{{ row.total }}</td>
                <td>{{ row.reliability }}</td>
                <td>{{ row.original_valid_rate }}</td>
                <td>{{ row.final_valid_rate }}</td>
                <td class="{{ row.change_class }}">{{ row.change }}</td>
                <td>{{ row.empty_rate }}</td>
                <td>{{ row.correction_rate }}</td>
                <td class="improved">{{ row.improved_rate }}</td>
                <td class="worsened">{{ row.worsened_rate }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <h2>Improvement Recommendations</h2>
        <div class="recommendations">
            {% if recommendations %}
            <ul>
                {% for rec in recommendations %}
                <li>{{ rec }}</li>
                {% endfor %}
            </ul>
            {% else %}
            <p>No specific recommendations at this time.</p>
            {% endif %}
        </div>
        
        <div style="margin-top: 30px; font-size: 12px; color: #777; text-align: center;">
            <p>This report was automatically generated to help improve OCR performance.</p>
        </div>
    </body>
    </html>
    """
    
    # Calculate overall reliability (average of reliabilities)
    overall_reliability = round(sum(filtered_scores.values()) / len(filtered_scores) if filtered_scores else 0, 1)
    
    # Get unique document count if available
    unique_doc_count = stats.get("unique_document_count", len(stats["documents"]))
    
    # Generate HTML
    template = Template(html_template)
    html = template.render(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        doc_count=len(stats["documents"]),
        unique_doc_count=unique_doc_count,
        overall_reliability=overall_reliability,
        reliability_chart=reliability_chart,
        improvement_chart=improvement_chart,
        correction_chart=correction_chart,
        table_data=table_data,
        recommendations=recommendations
    )
    
    return html

if __name__ == "__main__":
    main() 