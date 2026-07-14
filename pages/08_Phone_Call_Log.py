import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import datetime
import pandas as pd

from services.ui_components import apply_custom_css
from db.queries import get_patient_overview, record_phone_call, get_phone_calls_by_patient

st.set_page_config(page_title="Phone Call Log | Anti-Amyloid Tracker", page_icon="📞", layout="wide")
apply_custom_css()

user = {"email": "demo@clinic.local", "username": "demo_user", "name": "Demo User"}

st.title("📞 Follow-up Phone Call Log")
st.caption("Document follow-up phone calls to patients for clinical tracking and audit purposes.")

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

st.markdown("### Patient Info")
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**Drug Therapy:** `{patient['drug'].title()}`")
    st.markdown(f"**Therapy Status:** `{patient['therapy_status'].upper()}`")
with col2:
    st.markdown(f"**Infusion Location:** `{patient['infusion_location']}`")
    st.markdown(f"**Last Infusion #:** `{patient['last_infusion_number'] or 0}`")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

with st.form("phone_call_form"):
    st.markdown("### Log Phone Call")
    
    col_date, col_reason = st.columns(2)
    with col_date:
        call_date = st.date_input("Call Date*", value=datetime.date.today())
    with col_reason:
        call_reason = st.selectbox(
            "Call Reason*",
            options=["ARIA follow-up", "infusion reaction follow-up", "scheduling", "symptom check", "other"],
            format_func=lambda s: s.title()
        )
    
    call_outcome = st.selectbox(
        "Call Outcome*",
        options=["reached - no concerns", "reached - new symptoms", "reached - escalated", "voicemail left", "no answer"],
        format_func=lambda s: s.title()
    )
    
    follow_up_required = st.checkbox("Follow-up Required?", value=False,
                                      help="Check if another follow-up call or action is needed.")
    
    notes = st.text_area("Call Notes", placeholder="Document conversation details, patient-reported symptoms, instructions given...")
    
    submitted = st.form_submit_button("Log Phone Call")

if submitted:
    try:
        call_pk = record_phone_call(
            patient_pk=patient['patient_pk'],
            call_date=call_date,
            call_reason=call_reason,
            call_outcome=call_outcome,
            follow_up_required=follow_up_required,
            notes=notes,
            user_email=user['email']
        )
        
        if call_pk:
            st.success(f"🎉 **Success!** Logged phone call for patient **{selected_mrn}** on **{call_date.strftime('%Y-%m-%d')}**.")
            st.balloons()
            st.query_params.clear()
        else:
            st.error("Error: Failed to save phone call record. Please contact the administrator.")
    except Exception as e:
        st.error(f"Database error while recording phone call: {e}")

# Show recent call history for this patient
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown("### 📋 Recent Call History for This Patient")

try:
    calls = get_phone_calls_by_patient(patient['patient_pk'])
    if not calls:
        st.info("No phone call records found for this patient.")
    else:
        df_calls = pd.DataFrame(calls)
        display_df = pd.DataFrame()
        display_df['Call Date'] = df_calls['call_date'].apply(lambda d: d.strftime('%Y-%m-%d'))
        display_df['Reason'] = df_calls['call_reason'].str.title()
        display_df['Outcome'] = df_calls['call_outcome'].str.title()
        display_df['Follow-up?'] = df_calls['follow_up_required'].apply(lambda b: '⚠️ Yes' if b else 'No')
        display_df['Notes'] = df_calls['notes'].fillna('')
        display_df['Logged By'] = df_calls['created_by']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Failed to load call history: {e}")
