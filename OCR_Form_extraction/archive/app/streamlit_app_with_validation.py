import streamlit as st
import json
import tempfile
import os
import sys
from utils.ocr import DocumentIntelligenceExtractor
from utils.openai_extractor import OpenAIExtractor
from utils.validation import ExtractionValidator

# Configuration de la page
st.set_page_config(
    page_title="Form Extractor ביטוח לאומי",
    page_icon="📄",
    layout="wide"
)

# Titre et description
st.title("Form Extractor ביטוח לאומי")
st.markdown("""
This application automatically extracts information from National Insurance Institute forms (ביטוח לאומי).

**Instructions:**
1. Upload a form in PDF or JPG format
2. Wait for the document to be processed
3. View the extracted results
""")

# Initialisation des extracteurs
@st.cache_resource
def get_extractors():
    return DocumentIntelligenceExtractor(), OpenAIExtractor(), ExtractionValidator()

doc_extractor, openai_extractor, validator = get_extractors()

# Zone de téléchargement
uploaded_file = st.file_uploader(
    "Choose a file",
    type=["pdf", "jpg", "jpeg"],
    help="Accepted formats: PDF, JPG"
)

if uploaded_file is not None:
    # Créer deux colonnes
    col1, col2 = st.columns(2)
    
    with st.spinner("Processing..."):
        # Créer un fichier temporaire
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        try:
            # Étape 1: Extraction OCR
            with st.status("OCR extraction in progress...") as status:
                ocr_result = doc_extractor.extract_text(tmp_path)
                status.update(label="OCR completed ✅")
                
                with col1:
                    st.subheader("Extracted Text")
                    extracted_text = "\n".join([span.get("text", "") for span in ocr_result.get("text", [])])
                    st.text_area(
                        "Raw Text",
                        value=extracted_text,
                        height=400,
                        disabled=True
                    )

            # Étape 2: Extraction structurée
            with st.status("Content analysis in progress...") as status:
                text_content = "\n".join([span.get("text", "") for span in ocr_result.get("text", [])])
                structured_result = openai_extractor.extract_structured_data(text_content)
                status.update(label="Analysis completed ✅")
                
                with col2:
                    st.subheader("Structured Data")
                    st.json(structured_result)
                    
                    # Bouton de téléchargement
                    json_str = json.dumps(structured_result, ensure_ascii=False, indent=2)
                    st.download_button(
                        label="📥 Download results (JSON)",
                        data=json_str.encode('utf-8'),
                        file_name="extraction_results.json",
                        mime="application/json"
                    )
            
            # Étape 3: Validation des données
            with st.status("Data validation in progress...") as status:
                validation_result = validator.validate_extracted_data(structured_result, ocr_result)
                status.update(label="Validation completed ✅")
                
                # Afficher les résultats de validation
                st.subheader("Data Validation")
                
                # Définir les métriques et leurs explications
                metrics_explanation = """
                **Metrics explanation:**
                - **Completeness**: Percentage of fields filled out of all possible fields (higher is better)
                - **Accuracy**: Percentage of filled fields that have valid format (higher is better)
                - **OCR Confidence**: Average confidence score of the OCR text extraction (higher is better)
                """
                st.markdown(metrics_explanation)
                
                col_comp, col_acc = st.columns(2)
                with col_comp:
                    st.metric("Completeness", f"{validation_result['completeness']['score']:.2%}")
                    if validation_result['completeness']['missing_required']:
                        st.warning(f"Missing required fields: {', '.join(validation_result['completeness']['missing_required'])}")
                
                with col_acc:
                    st.metric("Accuracy", f"{validation_result['accuracy']['score']:.2%}")
                    st.metric("OCR Confidence", f"{validation_result['confidence']['score']:.2%}")
                    if validation_result['accuracy']['invalid_fields']:
                        # Extraire les noms des champs invalides pour les afficher dans le message
                        invalid_field_names = [field["field"] for field in validation_result['accuracy']['invalid_fields']]
                        st.warning(f"Fields with invalid format ({len(invalid_field_names)}): {', '.join(invalid_field_names)}")
                
                # Afficher les détails des erreurs de format (sans expander imbriqué)
                st.subheader("Error Details")
                tab1, tab2 = st.tabs(["Format Errors", "Recent Logs"])
                
                with tab1:
                    if validation_result['accuracy']['invalid_fields']:
                        st.json(validation_result['accuracy']['invalid_fields'])
                    else:
                        st.success("No format errors detected")
                
                with tab2:
                    # Afficher le fichier de log de validation
                    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "extraction_validation.log")
                    if os.path.exists(log_file_path):
                        with open(log_file_path, 'r') as log_file:
                            log_content = log_file.readlines()
                            
                            # Créer des onglets pour différents types de logs
                            log_tabs = st.tabs(["Summary", "Errors & Warnings", "Detailed Logs"])
                            
                            with log_tabs[0]:
                                # Extraire les informations essentielles pour un résumé vraiment concis
                                
                                # Créer un tableau de métriques
                                metrics_col1, metrics_col2 = st.columns(2)
                                
                                # Trouver les métriques clés
                                completeness = None
                                accuracy = None
                                ocr_confidence = None
                                for line in log_content:
                                    if "COMPLETENESS:" in line:
                                        completeness = line.split("COMPLETENESS:")[1].strip()
                                    elif "ACCURACY:" in line:
                                        accuracy = line.split("ACCURACY:")[1].strip()
                                    elif "OCR CONFIDENCE:" in line:
                                        ocr_confidence = line.split("OCR CONFIDENCE:")[1].strip()
                                
                                # Afficher les métriques sous forme de KPIs
                                with metrics_col1:
                                    if completeness:
                                        st.metric("Completeness", completeness)
                                    if ocr_confidence:
                                        st.metric("OCR Confidence", ocr_confidence)
                                
                                with metrics_col2:
                                    if accuracy:
                                        st.metric("Accuracy", accuracy)
                                
                                # Vérification des champs manquants
                                missing_fields = []
                                for line in log_content:
                                    if "Missing required fields" in line:
                                        missing_fields.append(line)
                                
                                if missing_fields:
                                    st.error("Missing required fields:\n" + "\n".join(missing_fields))
                                # Suppression du message de succès concernant les champs requis
                                
                                # Extraire et afficher les problèmes importants
                                important_issues = []
                                
                                # Trouver l'intervalle de la dernière session si ce n'est pas déjà fait
                                if 'last_start_index' not in locals():
                                    last_start_index = None
                                    for i, line in enumerate(log_content):
                                        if "VALIDATION STARTED" in line:
                                            last_start_index = i
                                
                                if 'last_end_index' not in locals() and last_start_index is not None:
                                    last_end_index = None
                                    for i in range(last_start_index, len(log_content)):
                                        if "VALIDATION FINISHED" in log_content[i]:
                                            last_end_index = i
                                            break
                                    if last_end_index is None:
                                        last_end_index = len(log_content) - 1
                                
                                # N'extraire que les problèmes de la dernière session
                                if last_start_index is not None and last_end_index is not None:
                                    for i in range(last_start_index, last_end_index + 1):
                                        if "INVALID" in log_content[i] and "FORMAT" in log_content[i]:
                                            important_issues.append(log_content[i])
                                        elif "ERROR:" in log_content[i] and any(term in log_content[i] for term in ["LOGIC ERROR", "TYPE SUBSTITUTION", "FORMAT ERROR"]):
                                            important_issues.append(log_content[i])
                                else:
                                    # Comportement de secours - fallback au comportement précédent
                                    for line in log_content:
                                        if "INVALID" in line and "FORMAT" in line:
                                            important_issues.append(line)
                                        elif "ERROR:" in line and any(term in line for term in ["LOGIC ERROR", "TYPE SUBSTITUTION", "FORMAT ERROR"]):
                                            important_issues.append(line)
                                
                                if important_issues:
                                    st.subheader("⚠️ Detected Issues")
                                    st.code("\n".join(important_issues), language="bash")
                                else:
                                    st.success("✅ No major issues detected")
                            
                            with log_tabs[1]:
                                # Filtrer uniquement les erreurs et avertissements de la dernière session
                                error_logs = []
                                
                                # Utiliser les indices de session déjà déterminés ou les déterminer
                                if 'last_start_index' not in locals():
                                    last_start_index = None
                                    for i, line in enumerate(log_content):
                                        if "VALIDATION STARTED" in line:
                                            last_start_index = i
                                
                                if 'last_end_index' not in locals() and last_start_index is not None:
                                    last_end_index = None
                                    for i in range(last_start_index, len(log_content)):
                                        if "VALIDATION FINISHED" in log_content[i]:
                                            last_end_index = i
                                            break
                                    if last_end_index is None:
                                        last_end_index = len(log_content) - 1
                                
                                # N'extraire que les erreurs et avertissements de la dernière session
                                if last_start_index is not None and last_end_index is not None:
                                    for i in range(last_start_index, last_end_index + 1):
                                        if " ERROR:" in log_content[i] or " WARNING:" in log_content[i]:
                                            # Éviter les répétitions de messages similaires
                                            if not any(existing_line.split(":", 3)[3] if len(existing_line.split(":", 3)) > 3 else "" == 
                                                      log_content[i].split(":", 3)[3] if len(log_content[i].split(":", 3)) > 3 else "" 
                                                      for existing_line in error_logs):
                                                error_logs.append(log_content[i])
                                else:
                                    # Comportement de secours
                                    for line in log_content:
                                        if " ERROR:" in line or " WARNING:" in line:
                                            # Éviter les répétitions de messages similaires
                                            if not any(existing_line.split(":", 3)[3] if len(existing_line.split(":", 3)) > 3 else "" == 
                                                      line.split(":", 3)[3] if len(line.split(":", 3)) > 3 else "" 
                                                      for existing_line in error_logs):
                                                error_logs.append(line)
                                
                                if error_logs:
                                    st.code("".join(error_logs), language="bash")
                                else:
                                    st.success("No errors or warnings detected in the logs.")
                            
                            with log_tabs[2]:
                                # Afficher les logs complets organisés par catégories sans utiliser d'expanders dans des tabs
                                sub_tabs = st.tabs(["General Information", "Field Validation", "Technical Logs", "All Logs"])
                                
                                # Logs généraux (démarrage, fin, résumé)
                                general_logs = []
                                
                                # Utiliser les indices de session déjà déterminés ou les déterminer
                                if 'last_start_index' not in locals():
                                    last_start_index = None
                                    for i, line in enumerate(log_content):
                                        if "VALIDATION STARTED" in line:
                                            last_start_index = i
                                
                                if 'last_end_index' not in locals() and last_start_index is not None:
                                    last_end_index = None
                                    for i in range(last_start_index, len(log_content)):
                                        if "VALIDATION FINISHED" in log_content[i]:
                                            last_end_index = i
                                            break
                                    if last_end_index is None:
                                        last_end_index = len(log_content) - 1
                                
                                # N'extraire que les logs généraux de la dernière session
                                if last_start_index is not None and last_end_index is not None:
                                    for i in range(last_start_index, last_end_index + 1):
                                        if any(term in log_content[i] for term in ["VALIDATION STARTED", "VALIDATION FINISHED", "SUMMARY", 
                                                                                "COMPLETENESS:", "ACCURACY:", "OCR CONFIDENCE:"]):
                                            general_logs.append(log_content[i])
                                else:
                                    # Comportement de secours
                                    for line in log_content:
                                        if any(term in line for term in ["VALIDATION STARTED", "VALIDATION FINISHED", "SUMMARY", 
                                                                        "COMPLETENESS:", "ACCURACY:", "OCR CONFIDENCE:"]):
                                            general_logs.append(line)
                                
                                # Logs de validation de champs
                                validation_logs = []
                                
                                # Déterminer l'intervalle de la dernière session si ce n'est pas déjà fait
                                if 'last_start_index' not in locals():
                                    last_start_index = None
                                    for i, line in enumerate(log_content):
                                        if "VALIDATION STARTED" in line:
                                            last_start_index = i
                                
                                if 'last_end_index' not in locals() and last_start_index is not None:
                                    last_end_index = None
                                    for i in range(last_start_index, len(log_content)):
                                        if "VALIDATION FINISHED" in log_content[i]:
                                            last_end_index = i
                                            break
                                    if last_end_index is None:
                                        last_end_index = len(log_content) - 1
                                
                                # N'extraire que les logs de validation de la dernière session
                                if last_start_index is not None and last_end_index is not None:
                                    for i in range(last_start_index, last_end_index + 1):
                                        if (("Checking field" in log_content[i]) or 
                                            ("Format is valid" in log_content[i]) or 
                                            ("Format is invalid" in log_content[i])):
                                            validation_logs.append(log_content[i])
                                else:
                                    # Comportement de secours
                                    for line in log_content:
                                        if (("Checking field" in line) or 
                                            ("Format is valid" in line) or 
                                            ("Format is invalid" in line)):
                                            validation_logs.append(line)
                                
                                # Logs techniques
                                debug_logs = []
                                
                                # Utiliser les indices de session déjà déterminés ou les déterminer
                                if 'last_start_index' not in locals():
                                    last_start_index = None
                                    for i, line in enumerate(log_content):
                                        if "VALIDATION STARTED" in line:
                                            last_start_index = i
                                
                                if 'last_end_index' not in locals() and last_start_index is not None:
                                    last_end_index = None
                                    for i in range(last_start_index, len(log_content)):
                                        if "VALIDATION FINISHED" in log_content[i]:
                                            last_end_index = i
                                            break
                                    if last_end_index is None:
                                        last_end_index = len(log_content) - 1
                                
                                # N'extraire que les logs techniques de la dernière session
                                if last_start_index is not None and last_end_index is not None:
                                    for i in range(last_start_index, last_end_index + 1):
                                        if "DEBUG:" in log_content[i]:
                                            debug_logs.append(log_content[i])
                                else:
                                    # Comportement de secours
                                    debug_logs = [line for line in log_content if "DEBUG:" in line]
                                
                                # Afficher dans les sub_tabs
                                with sub_tabs[0]:
                                    if general_logs:
                                        st.code("".join(general_logs), language="bash")
                                    else:
                                        st.info("No general logs found.")
                                
                                with sub_tabs[1]:
                                    if validation_logs:
                                        st.code("".join(validation_logs), language="bash")
                                    else:
                                        st.info("No validation logs found.")
                                
                                with sub_tabs[2]:
                                    if debug_logs:
                                        st.code("".join(debug_logs), language="bash")
                                    else:
                                        st.info("No technical logs found.")
                                
                                with sub_tabs[3]:
                                    st.code("".join(log_content), language="bash")
                    else:
                        st.warning("Log file not found")

            st.success("Extraction successful! 🎉")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
        
        finally:
            # Nettoyer le fichier temporaire
            os.unlink(tmp_path)
else:
    # Message d'attente
    st.info("👆 Upload a form to start extraction.")

# La barre latérale a été supprimée 