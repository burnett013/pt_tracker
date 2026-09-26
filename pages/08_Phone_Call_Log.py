import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import datetime
import pandas as pd

from services.ui_components import apply_custom_css, render_sidebar_assistant
from db.queries import get_patient_overview, record_phone_call, get_phone_calls_by_patient, confirm_phone_call_follow_up

st.set_page_config(page_title="Phone Call Log | Anti-Amyloid Tracker", page_icon="📞", layout="wide")
apply_custom_css()
render_sidebar_assistant()

user = {"email": "demo@clinic.local", "username": "demo_user", "name": "Demo User"}

st.title("📞 Follow-up Phone Call Log")
st.caption("Document follow-up phone calls to patients for clinical tracking, follow-up linkage, and audit purposes.")

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

# Load calls for this patient early to support call numbering and linking
try:
    calls = get_phone_calls_by_patient(patient['patient_pk'])
except Exception as e:
    calls = []
    st.error(f"Failed to load patient call history: {e}")

next_call_num = (calls[0]['call_number'] + 1) if calls else 1

st.markdown("### Patient Info")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"**Drug Therapy:** `{patient['drug'].title()}`")
    st.markdown(f"**Therapy Status:** `{patient['therapy_status'].upper()}`")
with col2:
    st.markdown(f"**Infusion Location:** `{patient['infusion_location']}`")
    st.markdown(f"**Last Infusion #:** `{patient['last_infusion_number'] or 0}`")
with col3:
    st.markdown(f"**Total Calls Logged:** `{len(calls)}`")
    st.markdown(f"**Next Call ID:** `Call #{next_call_num}`")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

st.markdown(f"### Log Phone Call (Call #{next_call_num})")

# Linking to prior call
query_parent = st.query_params.get("parent_call", "")

parent_options = ["None (Initial / Standalone Call)"]
parent_map = {}
default_parent_index = 0

for c in calls:
    label = f"Call #{c['call_number']} ({c['call_date'].strftime('%m/%d/%Y')} - {c['call_reason'].title()} - {c['call_outcome'].title()})"
    if c['follow_up_required'] and not c['follow_up_confirmed']:
        label += " [⚠️ Pending Follow-up]"
    parent_options.append(label)
    parent_map[label] = c['phone_call_pk']
    if query_parent and str(c['phone_call_pk']) == query_parent:
        default_parent_index = len(parent_options) - 1

selected_parent_label = st.selectbox(
    "Is this call a follow-up to a previous call?",
    options=parent_options,
    index=default_parent_index,
    help="Select an existing call if this call is following up on a previous conversation or symptom check."
)

selected_parent_pk = parent_map.get(selected_parent_label)

if selected_parent_pk:
    parent_call_obj = next((c for c in calls if c['phone_call_pk'] == selected_parent_pk), None)
    parent_num = parent_call_obj['call_number'] if parent_call_obj else '?'
    st.info(f"🔗 **Linked Follow-up**: This call will be tied back to **Call #{parent_num}**. Submitting this log will automatically mark Call #{parent_num}'s follow-up as confirmed!")

col_date, col_reason = st.columns(2)
with col_date:
    call_date = st.date_input("Call Date*", value=datetime.date.today(), format="MM/DD/YYYY")
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

st.markdown("---")
st.markdown("#### Follow-up Tracking")

follow_up_req_str = st.radio(
    "Follow-up Required*",
    options=["No", "Yes"],
    index=0,
    horizontal=True,
    help="Indicate if a subsequent follow-up phone call or check is needed."
)

follow_up_required = (follow_up_req_str == "Yes")
follow_up_date = None
follow_up_confirmed = False

if follow_up_required:
    col_fdate, col_fconf = st.columns(2)
    with col_fdate:
        follow_up_date = st.date_input(
            "Follow-up Date*",
            value=datetime.date.today() + datetime.timedelta(days=7),
            format="MM/DD/YYYY",
            help="Specify when this follow-up call should happen."
        )
    with col_fconf:
        follow_up_conf_str = st.radio(
            "Follow-up Confirmed*",
            options=["No", "Yes"],
            index=0,
            horizontal=True,
            help="Indicate whether this follow-up call did happen."
        )
        follow_up_confirmed = (follow_up_conf_str == "Yes")

st.markdown("---")
notes = st.text_area("Call Notes", placeholder="Document conversation details, patient-reported symptoms, instructions given...")

submitted = st.button("Log Phone Call", type="primary")

if submitted:
    try:
        call_pk = record_phone_call(
            patient_pk=patient['patient_pk'],
            call_date=call_date,
            call_reason=call_reason,
            call_outcome=call_outcome,
            follow_up_required=follow_up_required,
            follow_up_date=follow_up_date,
            follow_up_confirmed=follow_up_confirmed,
            parent_call_pk=selected_parent_pk,
            notes=notes,
            user_email=user['email']
        )
        
        if call_pk:
            st.success(f"🎉 **Success!** Logged Call #{next_call_num} for patient **{selected_mrn}** on **{call_date.strftime('%m/%d/%Y')}**.")
            if selected_parent_pk:
                st.info(f"✅ Prior call successfully marked as confirmed.")
            st.balloons()
            st.query_params.clear()
            st.rerun()
        else:
            st.error("Error: Failed to save phone call record. Please contact the administrator.")
    except Exception as e:
        st.error(f"Database error while recording phone call: {e}")

# Show recent call history for this patient
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown("### 📋 Recent Call History for This Patient")

if not calls:
    st.info("No phone call records found for this patient.")
else:
    # Check for pending follow-ups that need to be closed out
    pending_calls = [c for c in calls if c.get('follow_up_required') and not c.get('follow_up_confirmed')]
    if pending_calls:
        st.warning(f"⚠️ **This patient has {len(pending_calls)} pending phone call follow-up(s).**")
        for pc in pending_calls:
            target_str = pc['follow_up_date'].strftime('%m/%d/%Y') if pc['follow_up_date'] else 'Date not specified'
            c_info, c_action1, c_action2 = st.columns([3, 1, 1])
            with c_info:
                st.markdown(f"**Call #{pc['call_number']} on {pc['call_date'].strftime('%m/%d/%Y')}** ({pc['call_reason'].title()}) — Scheduled Follow-up: `{target_str}`")
                if pc.get('notes'):
                    st.caption(f"Notes: {pc['notes']}")
            with c_action1:
                if st.button("📞 Log Follow-up", key=f"follow_btn_{pc['phone_call_pk']}", help="Fill out form above linked directly to this call"):
                    st.query_params["mrn"] = selected_mrn
                    st.query_params["parent_call"] = str(pc['phone_call_pk'])
                    st.rerun()
            with c_action2:
                if st.button("Follow-up Call Occurred", key=f"conf_btn_{pc['phone_call_pk']}", type="secondary", help="Quickly mark that this follow-up call occurred without logging a new separate call note"):
                    confirm_phone_call_follow_up(pc['phone_call_pk'], follow_up_confirmed=True, user_email=user['email'])
                    st.success(f"Call #{pc['call_number']} follow-up marked as occurred!")
                    st.rerun()
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    df_calls = pd.DataFrame(calls)
    display_df = pd.DataFrame()
    display_df['Call ID'] = df_calls['call_number'].apply(lambda n: f"Call #{n}")
    display_df['Call Date'] = df_calls['call_date'].apply(lambda d: d.strftime('%m/%d/%Y'))
    display_df['Reason'] = df_calls['call_reason'].str.title()
    display_df['Outcome'] = df_calls['call_outcome'].str.title()
    display_df['Linked To'] = df_calls.apply(
        lambda r: f"Follow-up to Call #{r['parent_call_number']}" if pd.notnull(r.get('parent_call_number')) and r.get('parent_call_number') else 'Initial Call',
        axis=1
    )
    display_df['Follow-up Required'] = df_calls['follow_up_required'].apply(lambda b: 'Yes' if b else 'No')
    display_df['Follow-up Date'] = df_calls['follow_up_date'].apply(lambda d: d.strftime('%m/%d/%Y') if pd.notnull(d) and d else '-')
    display_df['Follow-up Confirmed'] = df_calls.apply(
        lambda r: 'Yes' if r['follow_up_confirmed'] else ('No' if r['follow_up_required'] else '-'), axis=1
    )
    display_df['Notes'] = df_calls['notes'].fillna('')
    display_df['Logged By'] = df_calls['created_by']
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
