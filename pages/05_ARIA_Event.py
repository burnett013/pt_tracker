import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import datetime
from services.auth import render_auth_sidebar, get_logged_in_user, verify_access
from services.ui_components import apply_custom_css
from db.queries import get_patient_overview, record_aria_event

st.set_page_config(page_title="Record ARIA Event | Anti-Amyloid Tracker", page_icon="⚠️", layout="wide")
apply_custom_css()
render_auth_sidebar()
verify_access()

user = get_logged_in_user()

st.title("⚠️ Record ARIA Event")
st.caption("Log a new ARIA detection, change in radiographic severity, symptom presentation, or resolution.")

# Load patient list
try:
    patients = get_patient_overview()
except Exception as e:
    st.error(f"Failed to connect to database: {e}")
    st.stop()

if not patients:
    st.info("No patients currently enrolled.")
    st.stop()

patient_map = {p['mrn']: p for p in patients}
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
    st.markdown(f"**Prior ARIA Event:** `{'Yes' if patient['last_aria_date'] else 'No'}`")
    if patient['last_aria_date']:
        st.markdown(f"**Prior ARIA Status:** `{patient['last_aria_status'].upper()}` (on {patient['last_aria_date'].strftime('%Y-%m-%d')})")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

with st.form("aria_form"):
    st.markdown("### Log ARIA Details")
    
    aria_date = st.date_input("ARIA Detection Date*", value=datetime.date.today())
    
    col_types, col_severities = st.columns(2)
    with col_types:
        st.markdown("**ARIA Classification**")
        aria_e = st.checkbox("ARIA-E Present (vasogenic edema/effusion)", value=False)
        aria_h = st.checkbox("ARIA-H Present (microhemorrhage/hemosiderosis)", value=False)
        
    with col_severities:
        st.markdown("**Radiographic & Symptom Severity**")
        radio_severity = st.selectbox(
            "Radiographic Severity*",
            options=["mild", "moderate", "severe"],
            format_func=lambda s: s.title()
        )
        symptom_severity = st.selectbox(
            "Clinical Symptom Severity*",
            options=["none", "mild", "moderate", "severe"],
            format_func=lambda s: s.title()
        )
        
    st.markdown("---")
    st.markdown("#### Clinical Action & Monitoring Plan")
    
    col_action1, col_action2 = st.columns(2)
    with col_action1:
        aria_status = st.selectbox(
            "ARIA Event Status*",
            options=["active", "inactive"],
            format_func=lambda s: s.title(),
            help="Select 'Active' for new/ongoing occurrences, or 'Inactive' if resolved."
        )
        
        therapy_status = st.selectbox(
            "Recommended Therapy Action*",
            options=["continue", "hold", "discontinue"],
            format_func=lambda s: s.title(),
            help="Select clinical action for drug therapy. This updates patient profile automatically."
        )
        
    with col_action2:
        monthly_mri = st.checkbox(
            "Require Monthly Safety MRI Monitoring?",
            value=True,
            help="Check this if safety guidelines require repeat monthly MRIs until ARIA resolution."
        )
        
    notes = st.text_area("ARIA Notes", placeholder="Record anatomical location, size, quantity of findings, or clinical justification...")
    
    submitted = st.form_submit_button("Submit ARIA Event")

if submitted:
    if not (aria_e or aria_h):
        st.error("Error: You must select at least one ARIA type (ARIA-E or ARIA-H).")
    else:
        try:
            event_pk = record_aria_event(
                patient_pk=patient['patient_pk'],
                aria_date=aria_date,
                aria_e=aria_e,
                aria_h=aria_h,
                radiographic_severity=radio_severity,
                symptom_severity=symptom_severity,
                status=aria_status,
                therapy_status=therapy_status,
                monthly_mri_required=monthly_mri,
                notes=notes,
                user_email=user['email']
            )
            
            if event_pk:
                st.success(f"🎉 **Success!** Recorded ARIA event for patient **{selected_mrn}** on **{aria_date.strftime('%Y-%m-%d')}**.")
                st.info(f"Clinical action taken: **{therapy_status.upper()}**. Database patient profile updated.")
                st.balloons()
                st.query_params.clear()
            else:
                st.error("Error: Failed to save ARIA event record. Please contact the administrator.")
        except Exception as e:
            st.error(f"Database error while recording ARIA event: {e}")
