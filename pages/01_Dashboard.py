import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import datetime

from services.ui_components import apply_custom_css, render_badge, render_action_card
from services.dashboard_logic import evaluate_patient_status
from db.queries import get_patient_overview, update_therapy_status

st.set_page_config(page_title="Dashboard | Anti-Amyloid Tracker", page_icon="📊", layout="wide")
apply_custom_css()

user = {"email": "demo@clinic.local", "username": "demo_user", "name": "Demo User"}

st.title("📊 Clinical Worklist & Dashboard")
st.caption("Central landing dashboard for patient surveillance and action planning.")

# Load patient data
try:
    patients_raw = get_patient_overview()
except Exception as e:
    st.error(f"Failed to connect to database: {e}")
    st.stop()

if not patients_raw:
    st.info("💡 **No patients enrolled yet.** Go to **Patient Enrollment** in the sidebar to add your first patient.")
    st.stop()

# Evaluate status of all patients
evaluated_patients = []
for p in patients_raw:
    evaluated = evaluate_patient_status(dict(p))
    # Add extra raw details needed for display
    evaluated["patient_pk"] = p["patient_pk"]
    evaluated["baseline_mri_done"] = p["baseline_mri_done"]
    evaluated["cms_registry_number"] = p["cms_registry_number"]
    evaluated["infusion_location"] = p["infusion_location"]
    evaluated_patients.append(evaluated)

# Convert to DataFrames for easier filtering
df = pd.DataFrame(evaluated_patients)

# Metrics banner at the top
active_patients = df[df['active'] == True]
total_enrolled = len(df)
total_active = len(active_patients)
on_hold = len(df[df['therapy_status'] == 'hold'])
needs_action_count = len(df[df['needs_action'] == True])

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Enrolled", total_enrolled)
col2.metric("Active on Therapy", total_active - on_hold)
col3.metric("Therapy Hold", on_hold, delta_color="off")
col4.metric("Needs Action This Week", needs_action_count, delta="-"+str(needs_action_count), delta_color="inverse")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# Organize Dashboard Tabs
tab_action, tab_active, tab_mri, tab_inactive = st.tabs([
    "🚨 Action Items This Week",
    "📋 Active Patient Roster",
    "🧠 ARIA & MRI Watchlist",
    "⏸️ Holds & Discontinued"
])

# -----------------
# TAB 1: Action Items
# -----------------
with tab_action:
    st.subheader("Patients Requiring Attention")
    action_df = df[df['needs_action'] == True]
    
    if action_df.empty:
        st.success("✅ **No patients require action this week.** All surveillance and infusions are up-to-date!")
    else:
        # Loop through patients requiring action
        for _, pat in action_df.iterrows():
            title = f"Patient {pat['mrn']} ({pat['drug'].title()})"
            
            # Format status badge
            badge_text = pat['therapy_status'].upper()
            if pat['therapy_status'] == 'hold':
                badge_type = 'warning'
            elif pat['therapy_status'] == 'discontinue':
                badge_type = 'danger'
            else:
                badge_type = 'success'
                
            # Render action reasons
            reasons_html = "<ul>"
            for r in pat['action_reasons']:
                reasons_html += f"<li>{r}</li>"
            reasons_html += "</ul>"
            
            body_html = (
                f'<div style="margin-bottom: 0.5rem;">'
                f'<strong>Infusion Status:</strong> Infusion #{pat["last_infusion_number"] or 0} completed. '
                f'{"Next Infusion due: " + pat["next_infusion_date"].strftime("%m/%d/%Y") if pat["next_infusion_date"] else "No infusions recorded."}'
                f'</div>'
                f'<div>'
                f'<strong>Action Required Reasons:</strong>'
                f'{reasons_html}'
                f'</div>'
            )
            
            footer_links = (
                f'<a href="Infusion_Update?mrn={pat["mrn"]}" target="_self" style="text-decoration:none;">'
                f'<span class="badge badge-info" style="cursor:pointer; margin-right: 5px;">💉 Update Infusion</span>'
                f'</a>'
                f'<a href="MRI_Update?mrn={pat["mrn"]}" target="_self" style="text-decoration:none;">'
                f'<span class="badge badge-warning" style="cursor:pointer; margin-right: 5px;">🧠 Record MRI</span>'
                f'</a>'
                f'<a href="ARIA_Event?mrn={pat["mrn"]}" target="_self" style="text-decoration:none;">'
                f'<span class="badge badge-danger" style="cursor:pointer; margin-right: 5px;">⚠️ Log ARIA</span>'
                f'</a>'
                f'<a href="Phone_Call_Log?mrn={pat["mrn"]}" target="_self" style="text-decoration:none;">'
                f'<span class="badge badge-success" style="cursor:pointer; margin-right: 5px;">📞 Log Call</span>'
                f'</a>'
                f'<a href="Patient_Lookup?mrn={pat["mrn"]}" target="_self" style="text-decoration:none;">'
                f'<span class="badge badge-secondary" style="cursor:pointer;">🔍 Lookup History</span>'
                f'</a>'
            )
            
            # If on hold, add a button to quick-resume therapy
            if pat['therapy_status'] == 'hold':
                if st.button(f"Resume Therapy for {pat['mrn']}", key=f"resume_{pat['mrn']}"):
                    try:
                        update_therapy_status(pat['patient_pk'], 'continue', user['email'])
                        st.success(f"Therapy status for {pat['mrn']} set to CONTINUE.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error updating status: {e}")
            
            render_action_card(title, body_html, badge_text, badge_type, footer_links)

# -----------------
# TAB 2: Active Roster
# -----------------
with tab_active:
    st.subheader("All Active Patients on Therapy")
    roster_df = df[(df['active'] == True) & (df['therapy_status'] != 'discontinue')].copy()
    
    if roster_df.empty:
        st.info("No active patients currently on therapy.")
    else:
        # Prepare display columns
        display_df = pd.DataFrame()
        display_df['MRN'] = roster_df['mrn']
        display_df['Drug'] = roster_df['drug'].str.title()
        display_df['Therapy Status'] = roster_df['therapy_status'].str.upper()
        display_df['Last Infusion #'] = roster_df['last_infusion_number'].fillna(0).astype(int)
        display_df['Last Infusion Date'] = roster_df['last_infusion_date'].apply(lambda d: d.strftime('%m/%d/%Y') if d else 'None')
        display_df['Next Infusion Date'] = roster_df['next_infusion_date'].apply(lambda d: d.strftime('%m/%d/%Y') if d else 'None')
        display_df['MRI Pending?'] = roster_df['mri_pending'].apply(lambda b: '⚠️ YES' if b else 'No')
        display_df['Active ARIA?'] = roster_df['has_active_aria'].apply(lambda b: '🔴 YES' if b else 'No')
        display_df['Prior Reaction?'] = roster_df['has_prior_reaction'].apply(lambda b: '⚠️ YES' if b else 'No')
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# -----------------
# TAB 3: ARIA & MRI Watchlist
# -----------------
with tab_mri:
    st.subheader("Active ARIA & MRI Monitoring Watchlist")
    
    aria_watch_df = df[df['has_active_aria'] == True].copy()
    mri_pending_df = df[df['mri_pending'] == True].copy()
    
    col_aria, col_mri = st.columns(2)
    
    with col_aria:
        st.markdown("##### 🔴 Active ARIA Cases")
        if aria_watch_df.empty:
            st.success("No active ARIA cases under monitoring!")
        else:
            aria_display = pd.DataFrame()
            aria_display['MRN'] = aria_watch_df['mrn']
            aria_display['Drug'] = aria_watch_df['drug'].str.title()
            aria_display['Status'] = aria_watch_df['therapy_status'].str.upper()
            aria_display['Monthly MRI Due?'] = aria_watch_df['monthly_mri_due'].apply(lambda b: '🚨 DUE' if b else 'No')
            st.dataframe(aria_display, use_container_width=True, hide_index=True)
            
    with col_mri:
        st.markdown("##### 📅 Pending Surveillance MRIs")
        if mri_pending_df.empty:
            st.success("No surveillance MRIs pending!")
        else:
            mri_display = pd.DataFrame()
            mri_display['MRN'] = mri_pending_df['mrn']
            mri_display['Drug'] = mri_pending_df['drug'].str.title()
            mri_display['Next Infusion #'] = mri_pending_df['next_infusion_number']
            mri_display['Next Infusion Date'] = mri_pending_df['next_infusion_date'].apply(lambda d: d.strftime('%m/%d/%Y') if d else 'None')
            st.dataframe(mri_display, use_container_width=True, hide_index=True)

# -----------------
# TAB 4: Holds & Discontinued
# -----------------
with tab_inactive:
    st.subheader("Holds & Inactive Patients")
    
    hold_roster = df[df['therapy_status'] == 'hold'].copy()
    discon_roster = df[df['therapy_status'] == 'discontinue'].copy()
    
    col_hold, col_discon = st.columns(2)
    
    with col_hold:
        st.markdown("##### ⏸️ Patients on HOLD")
        if hold_roster.empty:
            st.info("No patients currently on hold.")
        else:
            hold_display = pd.DataFrame()
            hold_display['MRN'] = hold_roster['mrn']
            hold_display['Drug'] = hold_roster['drug'].str.title()
            hold_display['Last Infusion #'] = hold_roster['last_infusion_number'].fillna(0).astype(int)
            hold_display['Last Infusion Date'] = hold_roster['last_infusion_date'].apply(lambda d: d.strftime('%m/%d/%Y') if d else 'None')
            st.dataframe(hold_display, use_container_width=True, hide_index=True)
            
    with col_discon:
        st.markdown("##### ❌ Discontinued Patients")
        if discon_roster.empty:
            st.info("No discontinued patients recorded.")
        else:
            discon_display = pd.DataFrame()
            discon_display['MRN'] = discon_roster['mrn']
            discon_display['Drug'] = discon_roster['drug'].str.title()
            discon_display['Discontinued Date'] = discon_roster['discontinuation_date'].apply(lambda d: d.strftime('%m/%d/%Y') if d else 'None')
            discon_display['Reason'] = discon_roster['discontinuation_reason'].str.upper()
            discon_display['Follow-up MRI?'] = discon_roster['discontinued_mri_pending'].apply(lambda b: '⚠️ PENDING' if b else 'Completed/No')
            st.dataframe(discon_display, use_container_width=True, hide_index=True)
