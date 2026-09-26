import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

from services.ui_components import apply_custom_css, render_badge
from db.queries import get_patient_overview, get_patient_history

st.set_page_config(page_title="Patient Lookup | Anti-Amyloid Tracker", page_icon="🔍", layout="wide")
apply_custom_css()

user = {"email": "demo@clinic.local", "username": "demo_user", "name": "Demo User"}

st.title("🔍 Patient Lookup & History Timeline")
st.caption("Search for a patient by MRN to view their profile, therapy schedule, and chronological event audit trails.")

# Load patient list for search
try:
    patients = get_patient_overview()
except Exception as e:
    st.error(f"Failed to connect to database: {e}")
    st.stop()

if not patients:
    st.info("No patients currently enrolled.")
    st.stop()

mrns = sorted([p['mrn'] for p in patients])

# URL Query Param check
query_mrn = st.query_params.get("mrn", "")
default_index = 0
if query_mrn in mrns:
    default_index = mrns.index(query_mrn)

selected_mrn = st.selectbox("Search Patient by MRN*", options=mrns, index=default_index)

# Fetch current patient overview details
patient = next(p for p in patients if p['mrn'] == selected_mrn)
patient_pk = patient['patient_pk']

# Fetch detailed event histories
history = get_patient_history(patient_pk)

# Layout overview
st.markdown("### 📋 Patient Demographics & Profile")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"**MRN:** `{patient['mrn']}`")
    st.markdown(f"**Drug Therapy:** `{patient['drug'].title()}`")
    st.markdown(f"**APOE Genetic Status:** `{patient['apoe_status'].title()}`")

with col2:
    status_color = {
        "continue": "success",
        "hold": "warning",
        "discontinue": "danger"
    }.get(patient['therapy_status'], "secondary")
    
    st.markdown(f"**Therapy Status:** {render_badge(patient['therapy_status'].upper(), status_color)}", unsafe_allow_html=True)
    st.markdown(f"**Baseline MRI Done:** `{'Yes' if patient['baseline_mri_done'] else 'No'}`")
    st.markdown(f"**Infusion Location:** `{patient['infusion_location']}`")

with col3:
    st.markdown(f"**CMS Registry Number:** `{patient['cms_registry_number'] or 'N/A'}`")
    st.markdown(f"**Enrolled At:** `{patient['enrolled_at'].strftime('%m/%d/%Y %H:%M:%S')}`")
    st.markdown(f"**Enrolled By:** `{patient['created_by'] or 'System'}`")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# Timelines Tabs
tab_inf, tab_mri, tab_aria, tab_discon, tab_calls, tab_audit = st.tabs([
    "💉 Infusions History",
    "🧠 MRI Scans History",
    "⚠️ ARIA Events History",
    "❌ Discontinuation details",
    "📞 Phone Call Log",
    "📋 Audit & Change Logs"
])

# 1. Infusions Tab
with tab_inf:
    st.subheader("Infusions Timeline")
    infusions = history.get("infusions", [])
    
    if not infusions:
        st.info("No infusion logs found for this patient.")
    else:
        df_inf = pd.DataFrame(infusions)
        display_df = pd.DataFrame()
        display_df['Infusion #'] = df_inf['infusion_number']
        display_df['Admin Date'] = df_inf['infusion_date'].apply(lambda d: d.strftime('%m/%d/%Y'))
        display_df['Reaction Severity'] = df_inf['reaction_severity'].apply(lambda s: s.title() if s and s != 'none' else 'None')
        display_df['Premedication Noted?'] = df_inf['premedication_reminder'].apply(lambda b: 'Yes' if b else 'No')
        display_df['Notes'] = df_inf['notes'].fillna('')
        display_df['Logged By'] = df_inf['created_by']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# 2. MRI Tab
with tab_mri:
    st.subheader("MRI Scan Safety Logs")
    mris = history.get("mris", [])
    
    if not mris:
        st.info("No MRI scan records found for this patient.")
    else:
        df_mri = pd.DataFrame(mris)
        display_df = pd.DataFrame()
        display_df['Scan Date'] = df_mri['mri_date'].apply(lambda d: d.strftime('%m/%d/%Y'))
        display_df['Scan Type'] = df_mri['mri_type'].str.title()
        display_df['No ARIA Confirmed'] = df_mri['no_aria_confirmed'].apply(lambda b: '✅ Yes' if b else '-')
        display_df['ARIA-E Findings'] = df_mri['aria_e_present'].apply(lambda b: 'Edema Present' if b else 'None')
        display_df['ARIA-H Findings'] = df_mri['aria_h_present'].apply(lambda b: 'Hemorrhage Present' if b else 'None')
        display_df['Other Findings'] = df_mri['other_findings'].apply(lambda b: 'Yes' if b else 'No')
        display_df['Clearance Status'] = df_mri['proceed_to_next_infusion'].apply(lambda b: '🟢 Cleared' if b else '🔴 Held')
        
        # Add ARIA follow-up fields if they exist
        if 'aria_e_status' in df_mri.columns:
            display_df['ARIA-E Status'] = df_mri['aria_e_status'].fillna('-')
        if 'aria_h_status' in df_mri.columns:
            display_df['ARIA-H Status'] = df_mri['aria_h_status'].fillna('-')

        if 'unscheduled_reason' in df_mri.columns:
            display_df['Unscheduled Reason'] = df_mri['unscheduled_reason'].fillna('-')

        display_df['Notes'] = df_mri['notes'].fillna('')
        display_df['Logged By'] = df_mri['created_by']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# 3. ARIA Tab
with tab_aria:
    st.subheader("ARIA Surveillance Logs")
    arias = history.get("aria_events", [])
    
    if not arias:
        st.info("No ARIA events recorded for this patient.")
    else:
        df_aria = pd.DataFrame(arias)
        display_df = pd.DataFrame()
        display_df['Detection Date'] = df_aria['aria_date'].apply(lambda d: d.strftime('%m/%d/%Y'))
        display_df['ARIA-E?'] = df_aria['aria_e'].apply(lambda b: 'Yes' if b else 'No')
        display_df['ARIA-H?'] = df_aria['aria_h'].apply(lambda b: 'Yes' if b else 'No')
        display_df['ARIA-E Severity'] = df_aria['radiographic_severity_e'].apply(lambda s: s.title() if s else '-')
        display_df['ARIA-H Severity'] = df_aria['radiographic_severity_h'].apply(lambda s: s.title() if s else '-')
        display_df['Clinical Severity'] = df_aria['symptom_severity'].str.title()
        display_df['Event Status'] = df_aria['status'].str.upper()
        display_df['Therapy Status'] = df_aria['therapy_status'].str.upper()
        display_df['Monthly MRI Required?'] = df_aria['monthly_mri_required'].apply(lambda b: 'Yes' if b else 'No')
        display_df['Notes'] = df_aria['notes'].fillna('')
        display_df['Logged By'] = df_aria['created_by']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# 4. Discontinuation Tab
with tab_discon:
    st.subheader("Therapy Discontinuation Records")
    discon = history.get("discontinuations", [])
    
    if not discon:
        st.info("This patient has not been discontinued. Therapy is active or on hold.")
    else:
        df_dis = pd.DataFrame(discon)
        display_df = pd.DataFrame()
        display_df['Discon Date'] = df_dis['discontinuation_date'].apply(lambda d: d.strftime('%m/%d/%Y'))
        display_df['Reason'] = df_dis['reason'].str.upper()
        display_df['Other Reason Details'] = df_dis['other_reason_details'].fillna('-')
        display_df['Follow-up MRI Required?'] = df_dis['follow_up_mri_required'].apply(lambda b: 'Yes' if b else 'No')
        display_df['Notes'] = df_dis['notes'].fillna('')
        display_df['Logged By'] = df_dis['created_by']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# 5. Phone Calls Tab
with tab_calls:
    st.subheader("Follow-up Phone Call Log")
    calls = history.get("phone_calls", [])
    
    if not calls:
        st.info("No phone call records found for this patient.")
    else:
        df_calls = pd.DataFrame(calls)
        display_df = pd.DataFrame()
        display_df['Call ID'] = df_calls['call_number'].apply(lambda n: f"Call #{n}")
        display_df['Call Date'] = df_calls['call_date'].apply(lambda d: d.strftime('%m/%d/%Y'))
        display_df['Call Reason'] = df_calls['call_reason'].str.title()
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

# 6. Audit Tab
with tab_audit:
    st.subheader("Database Operations Audit Trail")
    audit = history.get("audit_logs", [])
    
    if not audit:
        st.info("No audit logs found.")
    else:
        # Helper to format the modified values dynamically
        def get_audit_details(row):
            action = row['action']
            tbl = row['table_name']
            old_val = row['old_value']
            new_val = row['new_value']
            
            if action == 'insert':
                return "Record created."
            elif action == 'delete':
                return "Record deleted."
            elif action == 'update':
                if not old_val or not new_val:
                    return "Record updated."
                changes = []
                for k, v in new_val.items():
                    old_v = old_val.get(k)
                    if old_v != v:
                        # Skip trigger/system noise fields
                        if k in ('updated_at', 'updated_by', 'created_at', 'created_by'):
                            continue
                        changes.append(f"[{k}] '{old_v}' ➔ '{v}'")
                return ", ".join(changes) if changes else "System fields updated."
            return ""

        df_aud = pd.DataFrame(audit)
        display_df = pd.DataFrame()
        display_df['Operation Time'] = df_aud['changed_at'].apply(lambda t: t.strftime('%m/%d/%Y %H:%M:%S'))
        display_df['Table Affected'] = df_aud['table_name'].str.upper()
        display_df['Action'] = df_aud['action'].str.upper()
        display_df['User (Email)'] = df_aud['changed_by']
        display_df['Modifications / Diff'] = df_aud.apply(get_audit_details, axis=1)
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
