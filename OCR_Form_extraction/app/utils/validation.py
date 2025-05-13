from typing import Dict, Any, List, Tuple
import re
from datetime import datetime
import numpy as np
import logging
import os
import json

# Configuration du logging spécifique pour la validation
logger = logging.getLogger("extraction_validator")
logger.setLevel(logging.DEBUG)

# Créer un handler pour le fichier de log
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)
file_handler = logging.FileHandler(os.path.join(log_dir, "extraction_validation.log"))
file_handler.setLevel(logging.DEBUG)

# Formater les logs
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

class ExtractionValidator:
    def __init__(self):
        self.field_patterns = {
            'idNumber': r'^\d{9}$',  # ID israélien à 9 chiffres
            'mobilePhone': r'^\d{10}$',  # Téléphone mobile israélien
            'landlinePhone': r'^\d{9}$',  # Téléphone fixe israélien
            'postalCode': r'^\d{5,7}$'  # Code postal israélien
        }
        
        # Définition des zones attendues pour chaque champ dans le formulaire
        self.expected_zones = {
            'lastName': {'y_range': (0.2, 0.3), 'x_range': (0.6, 0.8)},
            'firstName': {'y_range': (0.2, 0.3), 'x_range': (0.4, 0.6)},
            'idNumber': {'y_range': (0.2, 0.3), 'x_range': (0.2, 0.4)},
            # Ajouter d'autres champs selon le formulaire
        }

        self.min_confidence_threshold = 0.5
        self.spatial_overlap_threshold = 0.3
        
        # Définir les champs requis (champs qui devraient être remplis)
        self.required_fields = ["lastName", "firstName", "idNumber"]
        
        logger.info("ExtractionValidator initialized with %d patterns and %d required fields", 
                   len(self.field_patterns), len(self.required_fields))

    def validate_format(self, field: str, value: str) -> bool:
        """Valide le format d'un champ selon son pattern."""
        # Log all fields that we're checking, regardless of pattern existence
        logger.debug("Format validation for field '%s' with value '%s'", field, value)
        
        if not value:
            logger.debug("Field %s: Empty value - format validation skipped", field)
            return True  # Les champs vides sont acceptés
        
        # Log specific information for important fields like idNumber
        if field.lower() in ['idnumber', 'id']:
            logger.info("VALIDATING ID NUMBER FORMAT: '%s'", value)
        
        pattern = self.field_patterns.get(field)
        if not pattern:
            logger.debug("Field %s: No pattern defined - format validation skipped", field)
            # Add debug info for important fields even if no pattern
            if field.lower() in ['idnumber', 'id']:
                if value.isdigit():
                    logger.info("ID FORMAT CHECK: ID number '%s' contains only digits (length: %d)", value, len(value))
                    if len(value) == 9:
                        logger.info("ID FORMAT IS VALID: ID number '%s' has correct length (9 digits)", value)
                    else:
                        logger.error("ID FORMAT IS INVALID: ID number '%s' has incorrect length (%d digits instead of 9)", 
                                   value, len(value))
                else:
                    logger.warning("ID FORMAT IS INVALID: ID number '%s' contains non-digit characters", value)
            return True  # Pas de pattern défini pour ce champ
            
        is_valid = bool(re.match(pattern, value))
        if is_valid:
            logger.info("Field %s: Value '%s' matches the expected pattern %s", 
                       field, value, pattern)
            
            # Additional validation details for specific field types
            if field.lower() in ['idnumber', 'id']:
                logger.info("ID FORMAT IS VALID: ID number '%s' matches pattern: %s", value, pattern)
        else:
            logger.warning("Field %s: Value '%s' does not match the expected pattern %s", 
                          field, value, pattern)
            
            # Detailed error information for specific field types
            if field.lower() in ['idnumber', 'id']:
                logger.error("ID FORMAT IS INVALID: ID number '%s' does not match pattern: %s", value, pattern)
                if not value.isdigit():
                    logger.error("ID FORMAT ERROR: ID number contains non-digit characters: '%s'", value)
                elif len(value) != 9:
                    logger.error("ID FORMAT ERROR: ID number has incorrect length: %d (should be 9)", len(value))
            elif field.lower() in ['phone', 'mobilephone', 'landlinephone']:
                if not value.isdigit():
                    logger.error("PHONE FORMAT ERROR: Phone number contains non-digit characters: '%s'", value)
                else:
                    logger.error("PHONE FORMAT ERROR: Phone number has incorrect length: %d", len(value))
        
        return is_valid

    def validate_date(self, date_dict: Dict[str, str]) -> Tuple[bool, str]:
        """Valide une date et retourne (validité, message d'erreur)."""
        try:
            logger.debug("Validating date: %s", json.dumps(date_dict))
            if not all([date_dict.get('day'), date_dict.get('month'), date_dict.get('year')]):
                logger.info("Date validation: Incomplete date accepted - %s", json.dumps(date_dict))
                return True, ""  # Date incomplète acceptée
                
            try:
                date_obj = datetime(
                    int(date_dict['year']),
                    int(date_dict['month']),
                    int(date_dict['day'])
                )
                logger.info("Date validated successfully: %s", date_obj.strftime("%d/%m/%Y"))
                return True, ""
            except ValueError as e:
                error_msg = f"Invalid date format: {str(e)}"
                logger.warning("Date validation error: %s -> %s", date_dict, error_msg)
                return False, error_msg
        except Exception as e:
            logger.error("Unexpected error during date validation: %s", str(e))
            return False, f"Unexpected error: {str(e)}"

    def validate_spatial_position(self, field: str, position: Dict[str, float], page_dims: Dict[str, float]) -> float:
        """
        Valide la position d'un champ dans le document et retourne un score de confiance.
        
        Args:
            field: Nom du champ
            position: Position du texte {x, y, width, height}
            page_dims: Dimensions de la page {width, height}
        
        Returns:
            float: Score de confiance entre 0 et 1
        """
        if field not in self.expected_zones:
            logger.debug("Spatial validation skipped for field %s: no expected zone defined", field)
            return 1.0  # Pas de validation spatiale pour ce champ
            
        expected = self.expected_zones[field]
        
        # Normaliser les coordonnées
        x_norm = position['x'] / page_dims['width']
        y_norm = position['y'] / page_dims['height']
        
        # Vérifier si la position est dans la zone attendue
        x_valid = expected['x_range'][0] <= x_norm <= expected['x_range'][1]
        y_valid = expected['y_range'][0] <= y_norm <= expected['y_range'][1]
        
        if x_valid and y_valid:
            logger.info("Spatial position for field %s is valid: x=%.2f, y=%.2f within expected range", 
                       field, x_norm, y_norm)
            return 1.0
        elif x_valid or y_valid:
            logger.info("Spatial position for field %s is partially valid: x=%.2f (%s), y=%.2f (%s)", 
                       field, x_norm, "valid" if x_valid else "invalid", 
                       y_norm, "valid" if y_valid else "invalid")
            return 0.5
        
        logger.warning("Invalid position for field %s: expected x=%s, y=%s but got x=%.2f, y=%.2f", 
                     field, expected['x_range'], expected['y_range'], x_norm, y_norm)
        return 0.0

    def validate_extraction(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valide les résultats d'extraction en vérifiant la cohérence spatiale et les scores de confiance.
        
        Args:
            extraction_result: Dictionnaire contenant les résultats d'extraction
            
        Returns:
            Dict contenant les résultats de validation
        """
        validation_scores = []
        spatial_validations = []
        
        # Valider les spans de texte
        text_spans = extraction_result.get("text", [])
        logger.info("Validating %d extracted text spans", len(text_spans))
        
        for i, span in enumerate(text_spans[:20]):  # Limiter l'affichage des logs pour les premiers spans
            # Vérifier le score de confiance
            confidence = span.get("confidence", 0)
            confidence_valid = confidence >= self.min_confidence_threshold
            
            if confidence_valid:
                logger.debug("Span #%d: '%s' has sufficient confidence: %.2f >= %.2f", 
                           i, span.get("text", "")[:30], confidence, self.min_confidence_threshold)
            else:
                logger.warning("Span #%d: '%s' has insufficient confidence: %.2f < %.2f", 
                             i, span.get("text", "")[:30], confidence, self.min_confidence_threshold)
            
            # Vérifier la cohérence spatiale avec les autres éléments
            spatial_score = self._validate_spatial_coherence(
                span.get("bounding_box", {}),
                text_spans + extraction_result.get("tables", [])
            )
            
            logger.debug("Span #%d: Spatial coherence score = %.2f", i, spatial_score)
            
            validation_scores.append(span.get("confidence", 0))
            spatial_validations.append(spatial_score)
        
        if len(text_spans) > 20:
            logger.debug("... %d more spans omitted from detailed logging", len(text_spans) - 20)
            
        # Calculer les scores globaux
        avg_confidence = np.mean(validation_scores) if validation_scores else 0.0
        spatial_confidence = np.mean(spatial_validations) if spatial_validations else 0.0
        
        logger.info("OCR validation completed: average confidence=%.2f, spatial coherence=%.2f", 
                   avg_confidence, spatial_confidence)
        
        return {
            "validated_spans": [
                {
                    "text": span.get("text", ""),
                    "confidence_valid": span.get("confidence", 0) >= self.min_confidence_threshold,
                    "spatial_score": self._validate_spatial_coherence(
                        span.get("bounding_box", {}),
                        text_spans
                    )
                }
                for span in text_spans
            ],
            "global_confidence": (avg_confidence + spatial_confidence) / 2,
            "confidence_metrics": {
                "average_confidence": avg_confidence,
                "spatial_confidence": spatial_confidence
            }
        }
    
    def validate_extracted_data(self, structured_data: Dict[str, Any], ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valide l'exactitude et l'exhaustivité des données extraites.
        
        Args:
            structured_data: Données structurées extraites par OpenAI
            ocr_data: Données OCR extraites par Document Intelligence
            
        Returns:
            dict: Résultats de validation
        """
        # Journaliser les données extraites pour référence
        logger.info("==================== VALIDATION STARTED ====================")
        logger.info("Starting validation of ChatGPT extracted data")
        logger.debug("Structured data: %s", json.dumps(structured_data, ensure_ascii=False))
        
        # Initialiser le résultat
        validation_result = {
            "completeness": {
                "filled_fields": 0,
                "total_fields": 0,
                "score": 0.0,
                "missing_required": []
            },
            "accuracy": {
                "valid_format_fields": 0,
                "total_fields": 0,
                "score": 0.0,
                "invalid_fields": []
            },
            "confidence": {
                "score": ocr_data.get("average_confidence", 0),
                "explanation": "Average OCR confidence score"
            }
        }
        
        # Aplatir le dictionnaire pour compter facilement les champs
        flat_data = self._flatten_dict(structured_data)
        logger.debug("Flattened data for validation: %d fields", len(flat_data))
        
        # Log all fields that were extracted
        logger.info("All extracted fields:")
        for key, value in flat_data.items():
            value_str = str(value).strip() if value else ""
            if value_str:
                logger.info("  - %s: '%s'", key, value_str[:50] + ("..." if len(value_str) > 50 else ""))
            else:
                logger.info("  - %s: [EMPTY]", key)
        
        # Calculer les métriques d'exhaustivité
        total_fields = len(flat_data)
        filled_fields = sum(1 for v in flat_data.values() if v and str(v).strip())
        
        logger.info("Completeness check: %d/%d fields filled (%.2f%%)", 
                   filled_fields, total_fields, 
                   filled_fields/total_fields*100 if total_fields > 0 else 0)
        
        # Vérifier les champs requis manquants
        logger.info("Checking required fields:")
        for field in self.required_fields:
            logger.info("Required field check: %s", field)
            field_found = False
            
            for key, value in flat_data.items():
                if key.endswith(field):
                    field_found = True
                    if not (value and str(value).strip()):
                        validation_result["completeness"]["missing_required"].append(key)
                        logger.error("  - Required field missing: %s", key)
                    else:
                        logger.info("  - Required field present: %s = '%s'", key, value)
            
            if not field_found:
                logger.warning("  - Required field '%s' not found in structure", field)
        
        # Calculer les métriques d'exactitude
        logger.info("Format validation for all fields:")
        for key, value in flat_data.items():
            # Ignorer les champs de score de confiance
            if 'confidences' in key or 'confidence' in key:
                logger.debug("  - Skipping confidence field %s - not subject to format validation", key)
                continue
                
            field_name = key.split(".")[-1]
            
            if value and str(value).strip():
                logger.info("Checking field %s = '%s'", key, value)
                validation_result["accuracy"]["total_fields"] += 1
                
                # Vérifier la cohérence avec les données OCR
                self._check_consistency_with_ocr(field_name, value, ocr_data)
                
                # Vérifier le format
                if self.validate_format(field_name, str(value)):
                    validation_result["accuracy"]["valid_format_fields"] += 1
                    logger.info("  - Field %s: Format is valid", key)
                else:
                    validation_result["accuracy"]["invalid_fields"].append({
                        "field": key,
                        "value": value,
                        "reason": "Invalid format"
                    })
                    logger.error("  - Field %s: Format is invalid for value '%s'", key, value)
            else:
                logger.debug("  - Field %s is empty - format validation skipped", key)
        
        # Calculer les scores
        validation_result["completeness"]["filled_fields"] = filled_fields
        validation_result["completeness"]["total_fields"] = total_fields
        validation_result["completeness"]["score"] = filled_fields / total_fields if total_fields > 0 else 0
        
        valid_format = validation_result["accuracy"]["valid_format_fields"]
        total_fields = validation_result["accuracy"]["total_fields"]
        validation_result["accuracy"]["score"] = valid_format / total_fields if total_fields > 0 else 0
        
        # Generate and log a validation summary
        self._log_validation_summary(validation_result)
        
        logger.info("Validation completed: completeness=%.2f%%, accuracy=%.2f%%, OCR confidence=%.2f%%",
                   validation_result["completeness"]["score"]*100,
                   validation_result["accuracy"]["score"]*100,
                   validation_result["confidence"]["score"]*100)
        
        if validation_result["accuracy"]["invalid_fields"]:
            logger.warning("Fields with invalid format: %s", 
                          json.dumps(validation_result["accuracy"]["invalid_fields"], ensure_ascii=False))
            
        logger.info("==================== VALIDATION FINISHED ====================")
        
        # IMPORTANT: Ne pas modifier le dictionnaire structured_data original
        # Nous retournons uniquement les résultats de validation, pas les données modifiées
        return validation_result
        
    def _log_validation_summary(self, validation_result: Dict[str, Any]) -> None:
        """
        Generates and logs a summary of the validation results
        
        Args:
            validation_result: The validation result dictionary
        """
        logger.info("===================== VALIDATION SUMMARY =====================")
        
        # Completeness summary
        logger.info("COMPLETENESS: %.2f%%", validation_result["completeness"]["score"]*100)
        logger.info("  - Total fields: %d", validation_result["completeness"]["total_fields"])
        logger.info("  - Filled fields: %d", validation_result["completeness"]["filled_fields"])
        
        if validation_result["completeness"]["missing_required"]:
            logger.warning("  - Missing required fields: %s", 
                         ", ".join(validation_result["completeness"]["missing_required"]))
        else:
            logger.info("  - All required fields are present")
            
        # Accuracy summary
        logger.info("ACCURACY: %.2f%%", validation_result["accuracy"]["score"]*100)
        logger.info("  - Total non-empty fields: %d", validation_result["accuracy"]["total_fields"])
        logger.info("  - Valid format fields: %d", validation_result["accuracy"]["valid_format_fields"])
        
        if validation_result["accuracy"]["invalid_fields"]:
            logger.warning("  - Fields with invalid format: %d", 
                         len(validation_result["accuracy"]["invalid_fields"]))
            for field in validation_result["accuracy"]["invalid_fields"]:
                logger.warning("    * %s: '%s'", field["field"], field["value"])
        else:
            logger.info("  - All fields have valid format")
            
        # Confidence summary
        logger.info("OCR CONFIDENCE: %.2f%%", validation_result["confidence"]["score"]*100)
        
        logger.info("=============================================================")
    
    def _check_consistency_with_ocr(self, field_name: str, value: Any, ocr_data: Dict[str, Any]) -> None:
        """
        Vérifie la cohérence entre la valeur extraite et les données OCR.
        
        Args:
            field_name: Nom du champ
            value: Valeur extraite
            ocr_data: Données OCR
        """
        value_str = str(value).lower().strip()
        if not value_str or len(value_str) <= 3:  # Ignorer les valeurs vides ou trop courtes
            logger.debug("Field %s: Value too short for OCR consistency check", field_name)
            return
            
        # Rechercher la valeur dans le texte OCR
        ocr_text = " ".join([span.get("text", "").lower() for span in ocr_data.get("text", [])])
        logger.debug("Checking OCR consistency for field %s = '%s'", field_name, value_str)
        
        # Calcul du score de similarité basique (nombre de caractères communs / longueur)
        common_chars = sum(1 for c in value_str if c in ocr_text)
        similarity_score = common_chars / len(value_str) if value_str else 0
        logger.debug("Basic similarity score for %s: %.2f", field_name, similarity_score)
        
        # Pour les objets comme les dates, vérifier chaque composant
        if isinstance(value, dict):
            # Vérifier si au moins un des composants est présent dans l'OCR
            components_found = 0
            components_total = 0
            
            for component_key, component_val in value.items():
                if component_val and str(component_val).strip():
                    components_total += 1
                    component_str = str(component_val).lower().strip()
                    is_found = component_str in ocr_text
                    
                    if is_found:
                        logger.debug("Component %s.%s = '%s' found in OCR", 
                                    field_name, component_key, component_str)
                        components_found += 1
                    else:
                        logger.warning("Component %s.%s = '%s' NOT found in OCR - POSSIBLE INVENTION by ChatGPT", 
                                     field_name, component_key, component_str)
            
            # Vérifier si les composants forment une date valide et cohérente
            if field_name.lower().endswith('date') and all(k in value for k in ["day", "month", "year"]):
                self._check_date_coherence(field_name, value)
            
            if components_total > 0:
                found_ratio = components_found / components_total
                if found_ratio < 0.5:  # Si moins de la moitié des composants sont trouvés
                    logger.warning("Possible inconsistency for field '%s': only %d/%d components found in OCR", 
                                  field_name, components_found, components_total)
                    logger.warning("SUSPECT DATA: Field '%s' may contain INVENTED VALUES by ChatGPT", field_name)
                else:
                    logger.info("Field '%s': %d/%d components found in OCR (%.2f%%)", 
                               field_name, components_found, components_total, found_ratio*100)
            
            return  # Fin du traitement pour les valeurs de type dict
        
        # Détection de substitution de type de valeur
        field_type = self._infer_field_type(field_name)
        if field_type in ['numeric', 'phone'] and not value_str.replace('-', '').replace(' ', '').isdigit():
            logger.error("TYPE SUBSTITUTION DETECTED: Field '%s' should be %s but contains non-digit characters: '%s'", 
                        field_name, self._get_expected_format(field_type), value_str)
        
        if field_type == 'text' and value_str.isdigit():
            logger.error("TYPE SUBSTITUTION DETECTED: Field '%s' (type: text) contains only digits: '%s'", 
                        field_name, value_str)
            
        # Pour les valeurs simples (chaînes, nombres), vérifier la présence dans l'OCR
        # Diviser en tokens pour une recherche plus souple
        value_tokens = value_str.split()
        tokens_found = []
        tokens_not_found = []
        
        for token in value_tokens:
            if len(token) > 3:  # Token significatif
                token_in_ocr = token in ocr_text
                closest_match = ""
                match_score = 0
                
                if not token_in_ocr:
                    # Chercher le token le plus proche dans l'OCR
                    ocr_tokens = ' '.join([span.get("text", "") for span in ocr_data.get("text", [])]).lower().split()
                    for ocr_token in ocr_tokens:
                        if len(ocr_token) > 3:  # Ignorer les tokens trop courts
                            common = sum(1 for c in token if c in ocr_token)
                            score = common / max(len(token), len(ocr_token))
                            if score > 0.6 and score > match_score:  # Seuil de similarité
                                match_score = score
                                closest_match = ocr_token
                
                if token_in_ocr:
                    tokens_found.append(token)
                else:
                    tokens_not_found.append(token)
                    if closest_match:
                        logger.info("Token '%s' not found, but similar to OCR token '%s' (score: %.2f)", 
                                  token, closest_match, match_score)
                    else:
                        logger.warning("Token '%s' not found in OCR and has no similar matches", token)
        
        if tokens_found:
            logger.info("Field %s: %d/%d significant tokens found in OCR", 
                       field_name, len(tokens_found), len(tokens_found) + len(tokens_not_found))
            logger.debug("Tokens found: %s", tokens_found)
            if tokens_not_found:
                logger.debug("Tokens not found: %s", tokens_not_found)
        elif tokens_not_found:  # Aucun token trouvé mais des tokens significatifs existent
            percentage_found = 0
            logger.warning("POSSIBLE INVENTION: '%s' (field %s) not found in OCR text", 
                          value_str, field_name)
            logger.error("SUSPICIOUS DATA: Field '%s' with value '%s' appears to be INVENTED by ChatGPT (0%% found in OCR)", 
                        field_name, value_str)
            
            # Vérifier les contraintes de format basiques
            expected_format = self._get_expected_format(field_type)
            
            if expected_format and not self._matches_expected_format(value_str, expected_format):
                logger.error("Incorrect format for field %s: '%s' does not match expected format %s", 
                            field_name, value_str, expected_format)
            else:
                logger.debug("Format seems correct for '%s', but value not found in OCR", value_str)

    def _check_date_coherence(self, field_name: str, date_dict: Dict[str, str]) -> None:
        """
        Vérifie la cohérence d'une date (valeurs plausibles, date dans le passé pour certains champs)
        
        Args:
            field_name: Nom du champ date
            date_dict: Dictionnaire contenant les composants de la date (day, month, year)
        """
        try:
            if not all(k in date_dict for k in ["day", "month", "year"]):
                logger.debug("Cannot check date coherence for %s: incomplete date", field_name)
                return
                
            # Vérifier si les composants sont numériques
            if not (date_dict["day"].isdigit() and date_dict["month"].isdigit() and date_dict["year"].isdigit()):
                logger.warning("Date components for %s contain non-digit characters", field_name)
                return
                
            day = int(date_dict["day"])
            month = int(date_dict["month"])
            year = int(date_dict["year"])
            
            # Vérifier les plages de valeurs
            if not (1 <= day <= 31):
                logger.error("Invalid day value for %s: %d (should be 1-31)", field_name, day)
            
            if not (1 <= month <= 12):
                logger.error("Invalid month value for %s: %d (should be 1-12)", field_name, month)
                
            current_year = datetime.now().year
            if year < 1900 or year > current_year:
                logger.warning("Unusual year value for %s: %d (outside range 1900-%d)", 
                             field_name, year, current_year)
            
            # Construire la date et vérifier sa validité
            try:
                date_obj = datetime(year, month, day)
                logger.info("Date %s is valid: %s", field_name, date_obj.strftime("%d/%m/%Y"))
                
                # Vérifier si c'est une date future
                if date_obj > datetime.now():
                    if "injury" in field_name.lower() or "receipt" in field_name.lower() or "filling" in field_name.lower():
                        logger.error("LOGIC ERROR: %s is a future date (%s) - this doesn't make sense for this field type", 
                                   field_name, date_obj.strftime("%d/%m/%Y"))
                    else:
                        logger.warning("Future date for %s: %s", field_name, date_obj.strftime("%d/%m/%Y"))
                
                # Vérifier la cohérence entre les dates
                if "injury" in field_name.lower():
                    self.injury_date = date_obj  # Stocker pour comparaison
                    
                if hasattr(self, 'injury_date') and "filling" in field_name.lower():
                    filling_date = date_obj
                    if filling_date < self.injury_date:
                        logger.error("LOGIC ERROR: Form filling date (%s) is before injury date (%s)", 
                                   filling_date.strftime("%d/%m/%Y"), 
                                   self.injury_date.strftime("%d/%m/%Y"))
                
            except ValueError as e:
                logger.error("Invalid date for %s: %s", field_name, str(e))
                
        except Exception as e:
            logger.error("Error checking date coherence for %s: %s", field_name, str(e))
    
    def _infer_field_type(self, field_name: str) -> str:
        """
        Infère le type de champ à partir de son nom.
        
        Args:
            field_name: Nom du champ
            
        Returns:
            Type de champ inféré (numeric, text, date, phone, etc.)
        """
        lower_name = field_name.lower()
        
        if any(term in lower_name for term in ['id', 'number', 'num', 'code']):
            return 'numeric'
        elif any(term in lower_name for term in ['phone', 'tel', 'mobile', 'landline']):
            return 'phone'
        elif any(term in lower_name for term in ['date', 'day', 'month', 'year']):
            return 'date'
        elif any(term in lower_name for term in ['name', 'first', 'last', 'family']):
            return 'text'
        elif any(term in lower_name for term in ['address', 'street', 'city']):
            return 'address'
        else:
            return 'unknown'
    
    def _get_expected_format(self, field_type: str) -> str:
        """
        Retourne le format attendu pour un type de champ.
        
        Args:
            field_type: Type de champ
            
        Returns:
            Description du format attendu
        """
        formats = {
            'numeric': 'sequence of digits',
            'phone': 'phone number (digits only)',
            'date': 'date (day/month/year)',
            'text': 'text (not only digits)',
            'address': 'address (street, number, city, etc.)'
        }
        return formats.get(field_type, '')
    
    def _matches_expected_format(self, value: str, expected_format: str) -> bool:
        """
        Vérifie si une valeur correspond approximativement au format attendu.
        Cette vérification est volontairement permissive pour éviter les faux positifs.
        
        Args:
            value: Valeur à vérifier
            expected_format: Format attendu
            
        Returns:
            True si le format semble respecté, False sinon
        """
        if 'digits only' in expected_format:
            # Pour les téléphones, codes, etc. - devrait contenir principalement des chiffres
            digits_ratio = sum(c.isdigit() for c in value) / len(value) if value else 0
            return digits_ratio > 0.7  # Au moins 70% de chiffres
            
        elif 'sequence of digits' in expected_format:
            # Pour les IDs, numéros, etc. - devrait être presque uniquement des chiffres
            digits_ratio = sum(c.isdigit() for c in value) / len(value) if value else 0
            return digits_ratio > 0.9  # Au moins 90% de chiffres
            
        elif 'not only digits' in expected_format:
            # Pour les noms, etc. - ne devrait pas être que des chiffres
            digits_ratio = sum(c.isdigit() for c in value) / len(value) if value else 0
            return digits_ratio < 0.5  # Moins de 50% de chiffres
            
        return True  # Format inconnu ou pas de contrainte particulière
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
        """
        Aplatit un dictionnaire imbriqué.
        
        Args:
            d: Dictionnaire à aplatir
            parent_key: Préfixe pour les clés
            
        Returns:
            dict: Dictionnaire aplati
        """
        items = {}
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.update(self._flatten_dict(v, new_key))
            else:
                items[new_key] = v
                
        return items
    
    def _validate_spatial_coherence(self, bbox: Dict[str, float], all_elements: List[Dict[str, Any]]) -> float:
        """
        Valide la cohérence spatiale d'un élément par rapport aux autres.
        
        Args:
            bbox: Boîte englobante de l'élément {x, y, width, height}
            all_elements: Liste de tous les éléments à comparer
            
        Returns:
            Score de cohérence spatiale entre 0 et 1
        """
        if not all_elements:
            return 1.0
            
        overlaps = []
        for element in all_elements:
            if element.get("bounding_box") == bbox:
                continue
                
            overlap = self._calculate_overlap(bbox, element.get("bounding_box", {}))
            overlaps.append(overlap)
            
        # Retourner un score basé sur le chevauchement moyen
        avg_overlap = np.mean(overlaps) if overlaps else 0.0
        return 1.0 - min(avg_overlap / self.spatial_overlap_threshold, 1.0)
    
    def _calculate_overlap(self, bbox1: Dict[str, float], bbox2: Dict[str, float]) -> float:
        """
        Calcule le chevauchement entre deux boîtes englobantes.
        
        Args:
            bbox1: Première boîte englobante {x, y, width, height}
            bbox2: Deuxième boîte englobante {x, y, width, height}
            
        Returns:
            Ratio de chevauchement entre 0 et 1
        """
        # Vérifier que les boîtes englobantes sont complètes
        if not all(k in bbox1 for k in ['x', 'y', 'width', 'height']) or \
           not all(k in bbox2 for k in ['x', 'y', 'width', 'height']):
            return 0.0
            
        x1, y1, w1, h1 = bbox1['x'], bbox1['y'], bbox1['width'], bbox1['height']
        x2, y2, w2, h2 = bbox2['x'], bbox2['y'], bbox2['width'], bbox2['height']
        
        # Calculer l'intersection
        x_left = max(x1, x2)
        y_top = max(y1, y2)
        x_right = min(x1 + w1, x2 + w2)
        y_bottom = min(y1 + h1, y2 + h2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
            
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculer l'union
        bbox1_area = w1 * h1
        bbox2_area = w2 * h2
        union_area = bbox1_area + bbox2_area - intersection_area
        
        # Retourner le ratio IoU (Intersection over Union)
        return intersection_area / union_area if union_area > 0 else 0.0 
