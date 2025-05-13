import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.utils.validation import ExtractionValidator

# Ajouter les champs requis
ExtractionValidator.required_fields = ['lastName', 'firstName', 'idNumber']

print('Validation functions added successfully!')
