import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime
from jinja2 import Template
import re

class StatisticsTracker:
    def __init__(self, storage_path="stats_data.json"):
        """Initialise le tracker de statistiques pour l'OCR"""
        # Utiliser un chemin absolu pour le fichier de statistiques
        if not os.path.isabs(storage_path):
            # Obtenir le répertoire racine de l'application (phase1)
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.storage_path = os.path.join(app_dir, storage_path)
        else:
            self.storage_path = storage_path
            
        print(f"Fichier de statistiques: {self.storage_path}")
        self.data = self._load_data()
        
        # Définir les formats attendus pour chaque champ
        self.expected_formats = {
            'idNumber': r'^\d{9}$',  # 9 chiffres
            'mobilePhone': r'^\d{10}$',  # 10 chiffres
            'landlinePhone': r'^\d{9,10}$',  # 9-10 chiffres
            'dateOfBirth.day': r'^(0?[1-9]|[12][0-9]|3[01])$',  # 1-31
            'dateOfBirth.month': r'^(0?[1-9]|1[0-2])$',  # 1-12
            'dateOfBirth.year': r'^(19|20)\d{2}$',  # 1900-2099
            'address.postalCode': r'^\d{5,7}$',  # 5-7 chiffres
            # Ajoutez d'autres formats selon besoin
        }
        
    def _load_data(self):
        """Charge les données de statistiques depuis le fichier"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erreur lors du chargement des statistiques: {e}")
                return {"documents": [], "field_stats": {}}
        return {"documents": [], "field_stats": {}}
    
    def _save_data(self):
        """Sauvegarde les données de statistiques dans le fichier"""
        try:
            # Créer le répertoire parent si nécessaire
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            with open(self.storage_path, 'w') as f:
                json.dump(self.data, f, indent=2)
                
            print(f"Statistiques sauvegardées dans {self.storage_path}")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des statistiques: {e}")
    
    def _check_format(self, field, value):
        """Vérifie si la valeur respecte le format attendu pour le champ"""
        if not value or value == "":
            return "empty"
        
        if field in self.expected_formats:
            pattern = self.expected_formats[field]
            if re.match(pattern, str(value)):
                return "valid"
            else:
                return "invalid"
        return "unverified"
    
    def track_document(self, doc_id, original_extraction, final_extraction):
        """
        Suit les statistiques d'un document
        :param doc_id: Identifiant du document (nom du fichier)
        :param original_extraction: Résultat de l'extraction OCR originale
        :param final_extraction: Résultat après corrections manuelles
        """
        # Aplatir les dictionnaires
        def flatten_dict(d, parent_key=''):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}.{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key))
                else:
                    items.append((new_key, v))
            return dict(items)
        
        flat_original = flatten_dict(original_extraction)
        flat_final = flatten_dict(final_extraction)
        
        # Créer une entrée pour ce document
        doc_entry = {
            "id": doc_id,
            "timestamp": datetime.now().isoformat(),
            "field_results": {}
        }
        
        # Vérifier si ce document existe déjà et récupérer ses statistiques
        existing_doc = None
        existing_doc_index = -1
        for i, doc in enumerate(self.data["documents"]):
            if doc["id"] == doc_id:
                existing_doc = doc
                existing_doc_index = i
                break
        
        # Initialiser un dictionnaire pour suivre les modifications de statistiques globales
        field_stats_diff = {}
        
        # Analyser chaque champ
        for field, orig_value in flat_original.items():
            final_value = flat_final.get(field, orig_value)
            
            format_status = self._check_format(field, orig_value)
            was_corrected = orig_value != final_value
            
            field_result = {
                "original_value": orig_value,
                "final_value": final_value,
                "format_status": format_status,
                "was_corrected": was_corrected
            }
            
            doc_entry["field_results"][field] = field_result
            
            # Initialiser un compteur de différence pour ce champ si nécessaire
            if field not in field_stats_diff:
                field_stats_diff[field] = {
                    "total": 0,
                    "empty": 0,
                    "valid": 0,
                    "invalid": 0,
                    "corrected": 0
                }
            
            # Si le document existe déjà, récupérer les statistiques précédentes pour ce champ
            if existing_doc and field in existing_doc.get("field_results", {}):
                old_field_result = existing_doc["field_results"][field]
                old_format_status = old_field_result.get("format_status", "unverified")
                old_was_corrected = old_field_result.get("was_corrected", False)
                
                # Soustraire les anciennes statistiques
                field_stats_diff[field]["total"] -= 1
                field_stats_diff[field][old_format_status] -= 1
                if old_was_corrected:
                    field_stats_diff[field]["corrected"] -= 1
            
            # Ajouter les nouvelles statistiques
            field_stats_diff[field]["total"] += 1
            field_stats_diff[field][format_status] += 1
            if was_corrected:
                field_stats_diff[field]["corrected"] += 1
            
            # Mettre à jour les statistiques globales
            if field not in self.data["field_stats"]:
                self.data["field_stats"][field] = {
                    "total": 0,
                    "empty": 0,
                    "valid": 0,
                    "invalid": 0,
                    "corrected": 0
                }
            
            # Appliquer les différences aux statistiques globales
            for stat_key, diff_value in field_stats_diff[field].items():
                self.data["field_stats"][field][stat_key] += diff_value
        
        # Remplacer ou ajouter ce document
        if existing_doc_index >= 0:
            self.data["documents"][existing_doc_index] = doc_entry
        else:
            self.data["documents"].append(doc_entry)
        
        # Sauvegarder les données
        self._save_data()
    
    def generate_reliability_scores(self):
        """Génère des scores de fiabilité pour chaque champ"""
        reliability_scores = {}
        
        for field, stats in self.data["field_stats"].items():
            total = stats["total"]
            if total == 0:
                reliability_scores[field] = 0
                continue
            
            # Score basé sur le format valide et le taux de correction
            format_score = stats["valid"] / total if total > 0 else 0
            correction_penalty = stats["corrected"] / total if total > 0 else 0
            
            # Score de fiabilité: format valide moins les corrections nécessaires
            reliability = max(0, format_score - (correction_penalty * 0.5))
            reliability_scores[field] = round(reliability * 100, 2)
        
        return reliability_scores
    
    def generate_html_report(self):
        """Génère un rapport HTML avec les statistiques"""
        reliability_scores = self.generate_reliability_scores()
        
        # Préparer les données pour les graphiques
        fields = list(reliability_scores.keys())
        scores = list(reliability_scores.values())
        
        # Créer un graphique pour la fiabilité
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
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        
        # Générer des recommandations
        recommendations = []
        problem_fields = [(field, score) for field, score in reliability_scores.items() if score < 70]
        problem_fields.sort(key=lambda x: x[1])
        
        for field, score in problem_fields[:5]:  # Top 5 problèmes
            field_stats = self.data["field_stats"][field]
            
            if field_stats["empty"] / field_stats["total"] > 0.3:
                recommendations.append(f"Field '{field}' is often empty (missing data). Consider improving data capture.")
            elif field_stats["invalid"] / field_stats["total"] > 0.3:
                recommendations.append(f"Field '{field}' often has incorrect format. Review OCR settings for this field type.")
            
            if field_stats["corrected"] / field_stats["total"] > 0.5:
                recommendations.append(f"Field '{field}' requires frequent manual correction. Consider additional training.")
        
        # Préparer les données de table
        table_data = []
        for field, stats in self.data["field_stats"].items():
            if stats["total"] > 0:
                valid_rate = (stats["valid"] / stats["total"]) * 100
                empty_rate = (stats["empty"] / stats["total"]) * 100
                correction_rate = (stats["corrected"] / stats["total"]) * 100
                
                table_data.append({
                    "field": field,
                    "total": stats["total"],
                    "reliability": f"{reliability_scores[field]}%",
                    "valid_rate": f"{valid_rate:.1f}%",
                    "empty_rate": f"{empty_rate:.1f}%",
                    "correction_rate": f"{correction_rate:.1f}%"
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
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1, h2 { color: #333; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .chart { margin: 20px 0; max-width: 100%; }
                .recommendations { background-color: #f8f9fa; padding: 15px; border-radius: 5px; }
                .low-reliability { background-color: #ffdddd; }
                .medium-reliability { background-color: #ffffcc; }
                .high-reliability { background-color: #ddffdd; }
            </style>
        </head>
        <body>
            <h1>OCR Reliability Report</h1>
            <p>Generated on: {{ timestamp }}</p>
            <p>Total documents analyzed: {{ doc_count }}</p>
            
            <h2>Reliability Chart</h2>
            <div class="chart">
                <img src="data:image/png;base64,{{ chart_image }}" alt="Reliability Chart">
            </div>
            
            <h2>Field Reliability Statistics</h2>
            <table>
                <tr>
                    <th>Field</th>
                    <th>Documents</th>
                    <th>Reliability</th>
                    <th>Valid Format</th>
                    <th>Empty Rate</th>
                    <th>Correction Rate</th>
                </tr>
                {% for row in table_data %}
                <tr class="
                    {% if row.reliability|float < 50 %}low-reliability
                    {% elif row.reliability|float < 75 %}medium-reliability
                    {% else %}high-reliability{% endif %}">
                    <td>{{ row.field }}</td>
                    <td>{{ row.total }}</td>
                    <td>{{ row.reliability }}</td>
                    <td>{{ row.valid_rate }}</td>
                    <td>{{ row.empty_rate }}</td>
                    <td>{{ row.correction_rate }}</td>
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
        </body>
        </html>
        """
        
        # Générer le HTML
        template = Template(html_template)
        html = template.render(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            doc_count=len(self.data["documents"]),
            chart_image=img_str,
            table_data=table_data,
            recommendations=recommendations
        )
        
        return html 