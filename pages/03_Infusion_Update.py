import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import datetime

from services.ui_components import apply_custom_css
from services.schedule_logic import get_next_infusion_number, mri_required_before_next_infusion, calculate_next_infusion_date
from services.dashboard_logic import evaluate_patient_status
from db.queries import get_patient_overview, record_infusion

st.set_page_config(page_title="Log Infusion | Anti-Amyloid Tracker", page_icon="💉", layout="wide")
apply_custom_css()

user = {"email": "demo@clinic.local", "username": "demo_user", "name": "Demo User"}

st.title("💉 Log Infusion Event")
st.caption("Record a completed infusion for a patient and track scheduling/reactions.")

# Load active patient list
try:
    patients = get_patient_overview()
except Exception as e:
    st.error(f"Failed to connect to database: {e}")
    st.stop()

# Filter active/on-hold patients (excluding discontinued)
active_patients = [p for p in patients if p['therapy_status'] != 'discontinue']

if not active_patients:
    st.info("No active patients available for infusions.")
    st.stop()

# Get patient list labels
patient_map = {p['mrn']: p for p in active_patients}
mrns = sorted(list(patient_map.keys()))

# Check for MRN in URL parameters
query_mrn = st.query_params.get("mrn", "")
default_index = 0
if query_mrn in mrns:
    default_index = mrns.index(query_mrn)

selected_mrn = st.selectbox("Select Patient by MRN*", options=mrns, index=default_index)
patient = patient_map[selected_mrn]

# Evaluate current schedule & MRI requirements
eval_status = evaluate_patient_status(dict(patient))

last_num = eval_status["last_infusion_number"] or 0
next_num = eval_status["next_infusion_number"]
last_date = eval_status["last_infusion_date"]
drug = eval_status["drug"]

st.markdown("### Patient Information & Safety Check")
col1, col2 = st.columns(2)

with col1:
    st.markdown(f"**Drug Therapy:** `{drug.title()}`")
    st.markdown(f"**Therapy Status:** `{patient['therapy_status'].upper()}`")
    st.markdown(f"**Infusion Count:** {last_num} completed")
    if last_date:
        st.markdown(f"**Last Infusion Date:** `{last_date.strftime('%Y-%m-%d')}`")
    else:
        st.markdown("**Last Infusion Date:** `None`")

with col2:
    st.markdown(f"**Next Infusion Number:** `{next_num}`")
    
    # Calculate next expected date
    expected_due = eval_status["next_infusion_date"]
    if expected_due:
        st.markdown(f"**Scheduled Due Date:** `{expected_due.strftime('%Y-%m-%d')}`")
    else:
        st.markdown("**Scheduled Due Date:** `Immediate` (first infusion)")

# Safety MRI alerts
st.markdown("#### 🛡️ Surveillance MRI Safety Check")
mri_required = eval_status["mri_surveillance_required"]
mri_pending = eval_status["mri_pending"]

if mri_required:
    if mri_pending:
        st.error(f"🚨 **CRITICAL HOLD WARNING**: Infusion #{next_num} requires a surveillance MRI scan. No MRI has been recorded since the last infusion ({last_date or 'N/A'}). Do not administer this infusion until an MRI scan has been completed.")
    else:
        last_mri_date = patient.get("last_mri_date")
        st.success(f"🟢 **Clear to Proceed**: Surveillance MRI for Infusion #{next_num} was recorded on **{last_mri_date.strftime('%Y-%m-%d')}** (after last infusion date).")
else:
    st.info(f"🟢 **Surveillance Check**: No routine surveillance MRI is required prior to Infusion #{next_num}.")

if patient['therapy_status'] == 'hold':
    st.warning("⚠️ **Notice**: This patient's therapy status is currently set to **HOLD**. Ensure clinical clearance is granted before resuming infusions.")

if eval_status["has_prior_reaction"]:
    st.warning("⚠️ **Premedication Alert**: This patient has experienced an infusion reaction in the past. Ensure premedication has been administered prior to this infusion.")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# Form to log infusion
with st.form("infusion_form"):
    st.markdown("### Log Infusion Details")
    
    infusion_date = st.date_input("Infusion Administration Date*", value=datetime.date.today())
    
    reaction_severity = st.selectbox(
        "Infusion Reaction Severity",
        options=["none", "mild", "moderate", "severe", "anaphylaxis"],
        format_func=lambda s: s.title(),
        help="Select the severity of any adverse reaction during or immediately after the infusion."
    )
    
    notes = st.text_area("Infusion Notes", placeholder="Record vitals, reaction details, or clinical observations...")
    
    submitted = st.form_submit_button("Submit Infusion Record")

if submitted:
    # Double-check constraints
    if mri_pending:
        st.error("Submission blocked: You cannot record an infusion when a required surveillance MRI is pending.")
    elif last_date and infusion_date <= last_date:
        st.error(f"Submission blocked: Infusion date ({infusion_date}) must be after the last infusion date ({last_date}).")
    else:
        try:
            # Insert the infusion record
            premedication_reminder = (reaction_severity != 'none')
            infusion_pk = record_infusion(
                patient_pk=patient['patient_pk'],
                infusion_number=next_num,
                infusion_date=infusion_date,
                reaction_severity=reaction_severity,
                premedication_reminder=premedication_reminder,
                notes=notes,
                user_email=user['email']
            )
            
            if infusion_pk:
                st.success(f"🎉 **Success!** Recorded Infusion #{next_num} for patient **{selected_mrn}** on **{infusion_date.strftime('%Y-%m-%d')}**.")
                st.balloons()
                # Clear query parameters and reload to reflect changes
                st.query_params.clear()
            else:
                st.error("Error: Failed to save infusion record. Please contact the administrator.")
        except Exception as e:
            st.error(f"Database error while recording infusion: {e}")
