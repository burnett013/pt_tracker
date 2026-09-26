import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import datetime

from services.ui_components import apply_custom_css, render_sidebar_assistant
from db.queries import get_patient_overview, record_discontinuation

st.set_page_config(page_title="Record Discontinuation | Anti-Amyloid Tracker", page_icon="❌", layout="wide")
apply_custom_css()
render_sidebar_assistant()

user = {"email": "demo@clinic.local", "username": "demo_user", "name": "Demo User"}

st.title("❌ Record Therapy Discontinuation")
st.caption("Permanently halt therapy and record clinical reasons and safety follow-up requirements.")

# Load active patient list
try:
    patients = get_patient_overview()
except Exception as e:
    st.error(f"Failed to connect to database: {e}")
    st.stop()

# We only want to show patients who aren't already discontinued
active_patients = [p for p in patients if p['therapy_status'] != 'discontinue']

if not active_patients:
    st.info("No active patients currently available for discontinuation.")
    st.stop()

patient_map = {p['mrn']: p for p in active_patients}
mrns = sorted(list(patient_map.keys()))

# Query parameter check
query_mrn = st.query_params.get("mrn", "")
default_index = 0
if query_mrn in mrns:
    default_index = mrns.index(query_mrn)

selected_mrn = st.selectbox("Select Patient by MRN*", options=mrns, index=default_index)
patient = patient_map[selected_mrn]

st.markdown("### Patient Current Status")
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**Drug Therapy:** `{patient['drug'].title()}`")
    st.markdown(f"**Current Therapy Status:** `{patient['therapy_status'].upper()}`")
with col2:
    st.markdown(f"**Last Infusion Administered:** Infusion #{patient['last_infusion_number'] or 0}")
    if patient['last_infusion_date']:
        st.markdown(f"**Last Infusion Date:** `{patient['last_infusion_date'].strftime('%m/%d/%Y')}`")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

with st.form("discontinuation_form"):
    st.markdown("### Discontinuation Profile")
    
    col_date, col_reason = st.columns(2)
    with col_date:
        discon_date = st.date_input("Discontinuation Date*", value=datetime.date.today(), format="MM/DD/YYYY")
        
        mri_required = st.checkbox(
            "Is a Post-Discontinuation Follow-up Safety MRI Required?",
            value=True,
            help="Check this if the patient requires follow-up safety scanning (e.g. following severe ARIA) even after stopping therapy."
        )
        
    with col_reason:
        reason = st.selectbox(
            "Primary Clinical Reason*",
            options=[
                "stroke",
                "DVT",
                "MI",
                "pulmonary embolism",
                "non-compliance",
                "disease progression",
                "other"
            ],
            format_func=lambda s: {
                "stroke": "Stroke / CVA",
                "DVT": "Deep Vein Thrombosis (DVT)",
                "MI": "Myocardial Infarction (MI)",
                "pulmonary embolism": "Pulmonary Embolism",
                "non-compliance": "Patient Non-compliance",
                "disease progression": "Disease Progression",
                "other": "Other Reason (Specify Below)"
            }.get(s, s)
        )
        
    other_details = ""
    if reason == "other":
        other_details = st.text_area("Other Reason Details*", placeholder="Please explain the clinical reason for discontinuation...")
        
    notes = st.text_area("Discontinuation Notes", placeholder="Record additional comments, specialist reports, or next steps in the patient's care plan...")
    
    submitted = st.form_submit_button("Record Permanent Discontinuation")

if submitted:
    # Validate other reason
    if reason == "other" and not other_details.strip():
        st.error("Error: Please provide specific details explaining the 'Other Reason'.")
    elif discon_date < patient['enrolled_at'].date():
        st.error(f"Error: Discontinuation date cannot be earlier than enrollment date ({patient['enrolled_at'].strftime('%m/%d/%Y')}).")
    else:
        try:
            discon_pk = record_discontinuation(
                patient_pk=patient['patient_pk'],
                discontinuation_date=discon_date,
                reason=reason,
                other_reason_details=other_details if reason == "other" else None,
                follow_up_mri_required=mri_required,
                notes=notes,
                user_email=user['email']
            )
            
            if discon_pk:
                st.success(f"🎉 **Success!** Recorded permanent discontinuation for patient **{selected_mrn}** on **{discon_date.strftime('%m/%d/%Y')}**.")
                st.info("The patient status has been set to **DISCONTINUED** and marked inactive in the registry.")
                st.balloons()
                st.query_params.clear()
            else:
                st.error("Error: Failed to save discontinuation record. Please contact the administrator.")
        except Exception as e:
            st.error(f"Database error while recording discontinuation: {e}")
