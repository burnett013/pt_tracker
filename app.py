import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from services.ui_components import apply_custom_css
from services.auth import verify_access
from db.queries import ensure_schema_migrations

# Page Configuration
st.set_page_config(
    page_title="Anti-Amyloid Patient Tracker",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply styling, enforce Entra ID authentication, and schema sync
apply_custom_css()
user = verify_access()
ensure_schema_migrations()

# Welcome Header
st.title("🧬 Anti-Amyloid Patient Tracking System")
st.subheader("Patient-Centric Clinical Workflow Tracker & Safety Monitor")

st.markdown("""
Welcome to the **Anti-Amyloid Patient Tracking App**. This workflow application is designed for clinical and research staff to manage patients undergoing anti-amyloid therapies (*lecanemab* and *donanemab*).

The tracker is organized around a streamlined **3-page patient-centric workflow** so you can select a patient once and manage their entire treatment schedule, infusions, unified MRI/ARIA surveillance, phone calls, and status in one place.
""")

col1, col2, col3 = st.columns(3)

with col1:
    st.info(
        "📊 **01 Dashboard**  \n"
        "Review the daily clinical worklist, identify patients needing immediate action this week, "
        "and jump directly into any patient's profile."
    )
    st.page_link("pages/01_Dashboard.py", label="Open Dashboard ➔", icon="📊")

with col2:
    st.info(
        "➕ **02 Patient Enrollment**  \n"
        "Enroll a new patient by MRN, record APOE & baseline MRI status, and optionally "
        "auto-generate their initial infusion and MRI schedule."
    )
    st.page_link("pages/02_Patient_Enrollment.py", label="Enroll New Patient ➔", icon="➕")

with col3:
    st.success(
        "👤 **03 Patient Profile**  \n"
        "Unified workspace for each patient: full infusion/MRI schedule ('sticky note' view), "
        "combined MRI & ARIA logging with branching logic, phone call logs, and full CRUD editing."
    )
    st.page_link("pages/03_Patient_Profile.py", label="Open Patient Profile ➔", icon="👤")

st.markdown("""
---
### 🔒 Data Governance & Privacy Reminders
- **No Demographics**: Never enter patient names, dates of birth, phone numbers, or other unnecessary identifiers.
- **MRN Only**: The Medical Record Number (`M00XXXXXXX`) is the **only** patient identifier shown and stored.
- **Auditing**: All creations, edits, and deletions are automatically logged in Central Time (`CT`) with field-level diffs.
""")
