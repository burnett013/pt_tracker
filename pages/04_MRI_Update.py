import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import datetime

from services.ui_components import apply_custom_css
from db.queries import get_patient_overview, record_mri

st.set_page_config(page_title="Record MRI | Anti-Amyloid Tracker", page_icon="🧠", layout="wide")
apply_custom_css()

user = {"email": "demo@clinic.local", "username": "demo_user", "name": "Demo User"}

st.title("🧠 Record MRI Scan")
st.caption("Record outcomes of a surveillance MRI or ARIA follow-up scan, and log clinical clearance.")

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
    st.markdown(f"**Therapy Status:** `{patient['therapy_status'].upper()}`")
with col2:
    st.markdown(f"**Baseline MRI Done:** `{'Yes' if patient['baseline_mri_done'] else 'No'}`")
    st.markdown(f"**Last Infusion Number:** `{patient['last_infusion_number'] or 0}`")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

with st.form("mri_form"):
    st.markdown("### Log MRI Findings")
    
    col_type, col_date = st.columns(2)
    with col_type:
        mri_type = st.selectbox("MRI Type*", options=["scheduled surveillance", "ARIA follow-up"])
    with col_date:
        mri_date = st.date_input("MRI Scan Date*", value=datetime.date.today())
        
    st.markdown("---")
    st.markdown("#### Radiographic Findings")
    col_findings1, col_findings2 = st.columns(2)
    with col_findings1:
        aria_e = st.checkbox("ARIA-E Present (vasogenic edema/sulcal effusion)", value=False)
        aria_h = st.checkbox("ARIA-H Present (microhemorrhages/hemosiderosis)", value=False)
    with col_findings2:
        other_findings = st.checkbox("Other Findings Present", value=False)
        
    other_details = ""
    if other_findings:
        other_details = st.text_area("Details of Other Findings*", placeholder="Enter details of other findings here...")
        
    st.markdown("---")
    
    # Conditional fields for ARIA follow-up MRI
    aria_e_status = None
    aria_h_status = None
    revert_schedule = None
    restart_schedule = None
    
    if mri_type == "ARIA follow-up":
        st.markdown("#### ARIA Follow-up Specifics")
        col_aria1, col_aria2 = st.columns(2)
        with col_aria1:
            aria_e_status = st.selectbox("ARIA-E Status*", options=["stable", "improved", "worsened", "resolved"])
            aria_h_status = st.selectbox("ARIA-H Status*", options=["stable", "worsened", "resolved"])
        
        with col_aria2:
            st.markdown("**Scheduler Instructions**")
            # If both ARIA-E and ARIA-H are resolved (or if the user selects resolved)
            resolved_options = ["resolved"]
            is_resolved = (aria_e_status == "resolved" and aria_h_status == "resolved")
            
            revert_schedule = st.checkbox("Revert to original MRI schedule?", value=False, 
                                          help="Check this if the patient has resolved ARIA and should return to their regular surveillance track.")
            restart_schedule = st.checkbox("Restart MRI schedule from the beginning?", value=False,
                                           help="Check this if therapy is resuming and the safety MRI sequence should reset.")
            
        st.markdown("---")
        
    st.markdown("#### Safety Clearance")
    proceed = st.checkbox("Clear patient to proceed to next infusion?*", value=True,
                          help="Uncheck this if the patient must be placed on HOLD due to new ARIA or other safety findings.")
    
    notes = st.text_area("Scan Notes", placeholder="Record radiographic details, sizes, locations of findings, or clinical advice...")
    
    submitted = st.form_submit_button("Record MRI scan")

if submitted:
    # Validate other findings details
    if other_findings and not other_details.strip():
        st.error("Error: Please provide details for the 'Other Findings Present' selection.")
    else:
        try:
            mri_pk = record_mri(
                patient_pk=patient['patient_pk'],
                mri_date=mri_date,
                mri_type=mri_type,
                aria_e_present=aria_e,
                aria_h_present=aria_h,
                other_findings=other_findings,
                other_findings_details=other_details if other_findings else None,
                proceed_to_next_infusion=proceed,
                aria_e_status=aria_e_status,
                aria_h_status=aria_h_status,
                revert_to_original_mri_schedule=revert_schedule,
                restart_mri_schedule=restart_schedule,
                notes=notes,
                user_email=user['email']
            )
            
            if mri_pk:
                st.success(f"🎉 **Success!** Recorded MRI scan for patient **{selected_mrn}** on **{mri_date.strftime('%Y-%m-%d')}**.")
                if not proceed:
                    st.warning("⚠️ **Notice**: Patient has NOT been cleared to proceed. Therapy status has been automatically updated to **HOLD**.")
                st.balloons()
                st.query_params.clear()
            else:
                st.error("Error: Failed to save MRI record. Please contact the administrator.")
        except Exception as e:
            st.error(f"Database error while recording MRI scan: {e}")
            
