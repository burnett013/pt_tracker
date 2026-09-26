import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from services.ui_components import apply_custom_css, render_sidebar_assistant

# Page Configuration
st.set_page_config(
    page_title="Anti-Amyloid Patient Tracker",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply styling and persistent assistant drawer
apply_custom_css()
render_sidebar_assistant()

# Welcome Header
st.title("🧬 Anti-Amyloid Patient Tracking System")
st.subheader("Clinical Workflow Tracker & Safety Monitor")

# Introduction and Information
st.markdown("""
Welcome to the **Anti-Amyloid Patient Tracking App**. This workflow application is designed for clinical and research staff to track patients undergoing anti-amyloid therapies (*lecanemab* and *donanemab*).

This application manages the structured clinical workflow, including infusion schedule monitoring, surveillance MRI reminders, ARIA event surveillance, and discontinuation tracking.

### 📋 Key Workflows
Select a page from the sidebar to begin:
""")

# Setup grid of actions
col1, col2 = st.columns(2)

with col1:
    st.info("📊 **01 Dashboard**  \nReview the active patient roster and identify patients requiring immediate action, surveillance MRIs, or holds this week.")
    st.info("➕ **02 Patient Enrollment**  \nEnroll new patients by entering their MRN, APOE status, selected therapy, baseline MRI completion, and infusion location.")
    st.info("💉 **03 Infusion Update**  \nLog a newly administered infusion. The system automatically increments infusion numbers and tracks interval dates.")
    st.info("🧠 **04 MRI Update**  \nDocument scheduled surveillance scans or ARIA follow-up MRIs, noting safety outcomes and proceed/hold status.")

with col2:
    st.warning("⚠️ **05 ARIA Event**  \nLog ARIA-E or ARIA-H events, including separate radiographic severities for each type, and initiate hold or monthly surveillance logic.")
    st.warning("❌ **06 Discontinuation Event**  \nDocument discontinuation reason (e.g., adverse events, progression) and flag if follow-up safety MRIs are required.")
    st.success("🔍 **07 Patient Lookup**  \nSearch any patient by MRN to view their full chronological timeline of infusions, MRIs, ARIA logs, phone calls, and audit logs.")
    st.success("📞 **08 Phone Call Log**  \nDocument follow-up phone calls to patients, tracking call reason, outcome, and whether additional follow-up is required.")

st.markdown("""
---
### 🔒 Data Governance & Privacy Reminders
- **No Demographics**: Never enter patient names, date of birth, phone numbers, or other identifiers.
- **MRN Only**: The Medical Record Number (MRN) is the **only** patient identifier shown and stored.
- **Auditing**: All database transactions are automatically audited, logging the authenticated user and timestamp.
""")
