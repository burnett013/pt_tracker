import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from services.ui_components import apply_custom_css, render_sidebar_assistant
from services.validation import clean_mrn, is_valid_mrn
from db.queries import enroll_patient, get_patient_overview

st.set_page_config(page_title="Patient Enrollment | Anti-Amyloid Tracker", page_icon="➕", layout="wide")
apply_custom_css()
render_sidebar_assistant()

user = {"email": "demo@clinic.local", "username": "demo_user", "name": "Demo User"}

st.title("➕ Patient Enrollment")
st.caption("Enroll a new patient into the tracking registry using the Medical Record Number (MRN) only.")

# Add security warning
st.warning("🔒 **Compliance reminder**: Do NOT enter patient names, date of birth, phone numbers, or any other demographic identifiers.")

with st.form("enrollment_form", clear_on_submit=False):
    st.markdown("### Patient Details")
    
    mrn_input = st.text_input(
        "Medical Record Number (MRN)*",
        help="Format: uppercase 'M' followed by '00' and 7 digits (e.g. M001234567)"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        drug = st.selectbox(
            "Selected Drug Therapy*",
            options=["lecanemab", "donanemab"],
            format_func=lambda s: s.title()
        )
        
        apoe_status = st.selectbox(
            "APOE Genetic Status*",
            options=["non-carrier", "heterozygote", "homozygote", "unknown"],
            format_func=lambda s: s.title()
        )
        
        baseline_mri = st.checkbox(
            "Baseline MRI Completed*",
            value=False,
            help="A baseline MRI must be completed prior to therapy initiation."
        )
        
    with col2:
        infusion_location = st.selectbox(
            "Infusion Location*",
            options=["Talis", "Vivo", "UT North"]
        )
        
        cms_registry = st.text_input(
            "CMS Registry Number (Optional)",
            help="Enter CMS Registry identifier if available"
        )
        
    st.markdown("<small>* Indicates a required field</small>", unsafe_allow_html=True)
    
    submitted = st.form_submit_value = st.form_submit_button("Enroll Patient")

if submitted:
    cleaned_mrn = clean_mrn(mrn_input)
    
    # 1. Validation
    if not mrn_input:
        st.error("Error: Medical Record Number (MRN) is required.")
    elif not is_valid_mrn(cleaned_mrn):
        st.error(f"Error: Invalid MRN format '{mrn_input}'. Must be an uppercase M followed by 00 and 7 digits (e.g., M001234567).")
    elif not baseline_mri:
        st.error("Error: Baseline MRI must be completed to enroll a patient for therapy.")
    else:
        # 2. Check if MRN already exists in database
        try:
            existing = get_patient_overview(cleaned_mrn)
            if existing:
                st.error(f"Error: A patient with MRN '{cleaned_mrn}' is already enrolled.")
            else:
                # 3. Insert record
                patient_pk = enroll_patient(
                    mrn=cleaned_mrn,
                    drug=drug,
                    apoe_status=apoe_status,
                    baseline_mri_done=baseline_mri,
                    cms_registry_number=cms_registry,
                    infusion_location=infusion_location,
                    user_email=user['email']
                )
                if patient_pk:
                    st.success(f"🎉 **Success!** Patient with MRN **{cleaned_mrn}** has been enrolled for **{drug.title()}** therapy.")
                    st.balloons()
                else:
                    st.error("Error: Failed to insert patient record. Please contact the administrator.")
        except Exception as e:
            st.error(f"Database error during enrollment: {e}")
