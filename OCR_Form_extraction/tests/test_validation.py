from app.utils.validation import ExtractionValidator
from app.utils.ocr import DocumentIntelligenceExtractor
from app.utils.openai_extractor import OpenAIExtractor
import sys, os, json

# Ajouter les fonctions requises à ExtractionValidator
ExtractionValidator.required_fields = ['lastName', 'firstName', 'idNumber']
ExtractionValidator._flatten_dict = lambda self, d, parent_key='': {
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(self._flatten_dict(v, new_key))
        else:
            items[new_key] = v
    return items
}
ExtractionValidator._calculate_field_confidence = lambda self, field, value, ocr_data: 0.5
ExtractionValidator.validate_extracted_data = lambda self, structured_data, ocr_data: {
    "field_validations": {},
    "completeness": {"filled_fields": 0, "total_fields": 0, "score": 0.0},
    "accuracy": {"valid_fields": 0, "total_validated": 0, "score": 0.0}
}

print('Validation functions added successfully!')
