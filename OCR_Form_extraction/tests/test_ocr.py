import pytest
from app.utils.ocr import DocumentIntelligenceExtractor
import os

@pytest.fixture
def document_extractor():
    return DocumentIntelligenceExtractor()

def test_extract_text(document_extractor):
    # Chemin vers un document de test
    test_document = "../phase1_data/283_ex1.pdf"
    
    # Vérifier que le fichier existe
    assert os.path.exists(test_document), f"Le fichier de test {test_document} n'existe pas"
    
    # Extraire le texte
    result = document_extractor.extract_text(test_document)
    
    # Vérifier la structure du résultat
    assert "text" in result
    assert "tables" in result
    assert "layout" in result
    
    # Vérifier que le texte n'est pas vide
    assert len(result["text"]) > 0
    
    # Vérifier que la mise en page contient au moins une page
    assert len(result["layout"]) > 0 