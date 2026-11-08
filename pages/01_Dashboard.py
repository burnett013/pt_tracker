import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

from services.ui_components import apply_custom_css, render_action_card, render_sidebar_assistant
from services.auth import verify_access
from services.dashboard_logic import evaluate_patient_status
from db.queries import get_patient_overview, update_therapy_status

st.set_page_config(page_title="Dashboard | Anti-Amyloid Tracker", page_icon="📊", layout="wide")
apply_custom_css()
user = verify_access()
render_sidebar_assistant()

st.title("📊 Clinical Worklist & Dashboard")
st.caption("Central landing dashboard for patient surveillance, schedule monitoring, and action planning.")

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
    evaluated["patient_pk"] = p["patient_pk"]
    evaluated["baseline_mri_done"] = p["baseline_mri_done"]
    evaluated["cms_registry_number"] = p["cms_registry_number"]
    evaluated["infusion_location"] = p["infusion_location"]
    evaluated_patients.append(evaluated)

df = pd.DataFrame(evaluated_patients)

# Metrics banner at the top
active_patients = df[df['active'] == True]
total_enrolled = len(df)
total_active = len(active_patients)
on_hold = len(df[df['therapy_status'] == 'hold'])
needs_action_count = len(df[df['needs_action'] == True])

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Enrolled", total_enrolled)
col2.metric("Active on Therapy", max(0, total_active - on_hold))
col3.metric("Therapy Hold", on_hold, delta_color="off")
col4.metric("Needs Action This Week", needs_action_count, delta="-" + str(needs_action_count) if needs_action_count else "0", delta_color="inverse")

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
        st.success("✅ **No patients require action this week.** All surveillance scans, calls, and infusions are up-to-date!")
    else:
        for _, pat in action_df.iterrows():
            mrn = pat['mrn']
            title = f"Patient {mrn} ({pat['drug'].title()} — {pat['infusion_location'] or 'No Location'})"

            badge_text = pat['therapy_status'].upper()
            if pat['therapy_status'] == 'hold':
                badge_type = 'warning'
            elif pat['therapy_status'] == 'discontinue':
                badge_type = 'danger'
            else:
                badge_type = 'success'

            reasons_html = "<ul>"
            for r in pat['action_reasons']:
                reasons_html += f"<li>{r}</li>"
            reasons_html += "</ul>"

            next_inf_str = (
                f"Next Infusion (#{pat['next_infusion_number']}) scheduled/due: <strong>{pat['next_infusion_date'].strftime('%m/%d/%Y')}</strong>"
                if pat["next_infusion_date"]
                else f"Next Infusion (#{pat['next_infusion_number']}): Not yet scheduled"
            )

            body_html = (
                f'<div style="margin-bottom: 0.5rem;">'
                f'<strong>Infusion Progress:</strong> {pat["last_infusion_number"] or 0} completed '
                f'({ "Last: " + pat["last_infusion_date"].strftime("%m/%d/%Y") if pat["last_infusion_date"] else "None completed" }). '
                f'{next_inf_str}.'
                f'</div>'
                f'<div>'
                f'<strong>Action Required Reasons:</strong>'
                f'{reasons_html}'
                f'</div>'
            )

            footer_links = (
                f'<a href="Patient_Profile?mrn={mrn}&section=schedule" target="_self" style="text-decoration:none;">'
                f'<span class="badge badge-info" style="cursor:pointer; margin-right: 5px;">📅 Schedule & Infusions</span>'
                f'</a>'
                f'<a href="Patient_Profile?mrn={mrn}&section=mri_aria" target="_self" style="text-decoration:none;">'
                f'<span class="badge badge-warning" style="cursor:pointer; margin-right: 5px;">🧠 MRI & ARIA</span>'
                f'</a>'
                f'<a href="Patient_Profile?mrn={mrn}&section=calls" target="_self" style="text-decoration:none;">'
                f'<span class="badge badge-success" style="cursor:pointer; margin-right: 5px;">📞 Phone Call Log</span>'
                f'</a>'
                f'<a href="Patient_Profile?mrn={mrn}&section=status" target="_self" style="text-decoration:none;">'
                f'<span class="badge badge-danger" style="cursor:pointer; margin-right: 5px;">⚙️ Status & Profile</span>'
                f'</a>'
                f'<a href="Patient_Profile?mrn={mrn}&section=audit" target="_self" style="text-decoration:none;">'
                f'<span class="badge badge-secondary" style="cursor:pointer;">📋 Audit Log</span>'
                f'</a>'
            )

            # Render the card FIRST, and place any quick-action button directly below THIS card
            render_action_card(title, body_html, badge_text, badge_type, footer_links)

            if pat['therapy_status'] == 'hold':
                col_btn, col_spacer = st.columns([2, 6])
                with col_btn:
                    if st.button(f"▶️ Resume Therapy for {mrn}", key=f"resume_{mrn}", use_container_width=True):
                        try:
                            update_therapy_status(pat['patient_pk'], 'continue', user['email'])
                            st.success(f"Therapy status for {mrn} set to CONTINUE.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating status: {e}")

# -----------------
# TAB 2: Active Roster
# -----------------
with tab_active:
    st.subheader("All Active Patients on Therapy")
    roster_df = df[(df['active'] == True) & (df['therapy_status'] != 'discontinue')].copy()

    if roster_df.empty:
        st.info("No active patients currently on therapy.")
    else:
        display_df = pd.DataFrame()
        display_df['MRN'] = roster_df['mrn']
        display_df['Drug'] = roster_df['drug'].str.title()
        display_df['Location'] = roster_df['infusion_location'].fillna('-')
        display_df['Therapy Status'] = roster_df['therapy_status'].str.upper()
        display_df['Completed Infusions'] = roster_df['last_infusion_number'].fillna(0).astype(int)
        display_df['Last Infusion Date'] = roster_df['last_infusion_date'].apply(lambda d: d.strftime('%m/%d/%Y') if pd.notnull(d) and d else 'None')
        display_df['Next Infusion #'] = roster_df['next_infusion_number']
        display_df['Next Scheduled/Due Date'] = roster_df['next_infusion_date'].apply(lambda d: d.strftime('%m/%d/%Y') if pd.notnull(d) and d else 'Not Scheduled')
        display_df['MRI Pending?'] = roster_df['mri_pending'].apply(lambda b: '⚠️ YES' if b else 'No')
        display_df['Active ARIA?'] = roster_df['has_active_aria'].apply(lambda b: '🔴 YES' if b else 'No')
        display_df['Prior Reaction?'] = roster_df['has_prior_reaction'].apply(lambda b: '⚠️ YES' if b else 'No')
        display_df['Profile Link'] = roster_df['mrn'].apply(lambda m: f"Patient_Profile?mrn={m}&section=schedule")

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Profile Link": st.column_config.LinkColumn("Open Workspace", display_text="👤 Open Profile")
            }
        )

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
            aria_display['ARIA Status'] = aria_watch_df['effective_aria_status'].str.upper()
            aria_display['Therapy Status'] = aria_watch_df['therapy_status'].str.upper()
            aria_display['Monthly MRI Due?'] = aria_watch_df['monthly_mri_due'].apply(lambda b: '🚨 DUE' if b else 'No')
            aria_display['Profile'] = aria_watch_df['mrn'].apply(lambda m: f"Patient_Profile?mrn={m}&section=mri_aria")
            st.dataframe(
                aria_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Profile": st.column_config.LinkColumn("Action", display_text="🧠 MRI / ARIA")
                }
            )

    with col_mri:
        st.markdown("##### 📅 Pending Surveillance MRIs")
        if mri_pending_df.empty:
            st.success("No surveillance MRIs pending!")
        else:
            mri_display = pd.DataFrame()
            mri_display['MRN'] = mri_pending_df['mrn']
            mri_display['Drug'] = mri_pending_df['drug'].str.title()
            mri_display['Before Infusion #'] = mri_pending_df['next_infusion_number']
            mri_display['Scheduled MRI Date'] = mri_pending_df['next_scheduled_mri_date'].apply(lambda d: d.strftime('%m/%d/%Y') if pd.notnull(d) and d else 'Not Scheduled')
            mri_display['Next Infusion Date'] = mri_pending_df['next_infusion_date'].apply(lambda d: d.strftime('%m/%d/%Y') if pd.notnull(d) and d else 'None')
            mri_display['Profile'] = mri_pending_df['mrn'].apply(lambda m: f"Patient_Profile?mrn={m}&section=mri_aria")
            st.dataframe(
                mri_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Profile": st.column_config.LinkColumn("Action", display_text="🧠 Log MRI")
                }
            )

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
            hold_display['Last Infusion Date'] = hold_roster['last_infusion_date'].apply(lambda d: d.strftime('%m/%d/%Y') if pd.notnull(d) and d else 'None')
            hold_display['Profile'] = hold_roster['mrn'].apply(lambda m: f"Patient_Profile?mrn={m}&section=status")
            st.dataframe(
                hold_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Profile": st.column_config.LinkColumn("Action", display_text="👤 Open Profile")
                }
            )

    with col_discon:
        st.markdown("##### ❌ Discontinued Patients")
        if discon_roster.empty:
            st.info("No discontinued patients recorded.")
        else:
            discon_display = pd.DataFrame()
            discon_display['MRN'] = discon_roster['mrn']
            discon_display['Drug'] = discon_roster['drug'].str.title()
            discon_display['Discontinued Date'] = discon_roster['discontinuation_date'].apply(lambda d: d.strftime('%m/%d/%Y') if pd.notnull(d) and d else 'None')
            discon_display['Reason'] = discon_roster['discontinuation_reason'].fillna('-').str.upper()
            discon_display['Follow-up MRI?'] = discon_roster['discontinued_mri_pending'].apply(lambda b: '⚠️ PENDING' if b else 'Completed/No')
            discon_display['Profile'] = discon_roster['mrn'].apply(lambda m: f"Patient_Profile?mrn={m}&section=status")
            st.dataframe(
                discon_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Profile": st.column_config.LinkColumn("Action", display_text="👤 Open Profile")
                }
            )
