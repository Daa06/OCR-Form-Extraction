import streamlit as st
import json
import tempfile
import os
import sys
from utils.ocr import DocumentIntelligenceExtractor
from utils.openai_extractor import OpenAIExtractor

# Configuration de la page
st.set_page_config(
    page_title="Extracteur de Formulaires ביטוח לאומי",
    page_icon="📄",
    layout="wide"
)

# Titre et description
st.title("Extracteur de Formulaires ביטוח לאומי")
st.markdown("""
Cette application permet d'extraire automatiquement les informations des formulaires de l'Institut National d'Assurance (ביטוח לאומי).

**Instructions :**
1. Téléchargez un formulaire au format PDF ou JPG
2. Attendez le traitement du document
3. Visualisez les résultats extraits
""")

# Initialisation des extracteurs
@st.cache_resource
def get_extractors():
    return DocumentIntelligenceExtractor(), OpenAIExtractor()

doc_extractor, openai_extractor = get_extractors()

# Zone de téléchargement
uploaded_file = st.file_uploader(
    "Choisissez un fichier",
    type=["pdf", "jpg", "jpeg"],
    help="Formats acceptés : PDF, JPG"
)

if uploaded_file is not None:
    # Créer deux colonnes
    col1, col2 = st.columns(2)
    
    with st.spinner("Traitement en cours..."):
        # Créer un fichier temporaire
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        try:
            # Étape 1: Extraction OCR
            with st.status("Extraction OCR en cours...") as status:
                ocr_result = doc_extractor.extract_text(tmp_path)
                status.update(label="OCR terminé ✅")
                
                with col1:
                    st.subheader("Texte extrait")
                    st.text_area(
                        "Texte brut",
                        value=ocr_result["text"],
                        height=400,
                        disabled=True
                    )

            # Étape 2: Extraction structurée
            with st.status("Analyse du contenu en cours...") as status:
                structured_result = openai_extractor.extract_structured_data(ocr_result["text"])
                status.update(label="Analyse terminée ✅")
                
                with col2:
                    st.subheader("Données structurées")
                    st.json(structured_result)
                    
                    # Bouton de téléchargement
                    json_str = json.dumps(structured_result, ensure_ascii=False, indent=2)
                    st.download_button(
                        label="📥 Télécharger les résultats (JSON)",
                        data=json_str.encode('utf-8'),
                        file_name="resultats_extraction.json",
                        mime="application/json"
                    )

            st.success("Extraction réussie ! 🎉")

        except Exception as e:
            st.error(f"Une erreur est survenue : {str(e)}")
        
        finally:
            # Nettoyer le fichier temporaire
            os.unlink(tmp_path)
else:
    # Message d'attente
    st.info("👆 Téléchargez un formulaire pour commencer l'extraction.") 