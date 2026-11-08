import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import streamlit as st

from services.ui_components import apply_custom_css
from services.auth import verify_access
from services.validation import clean_mrn, is_valid_mrn
from db.queries import enroll_patient, get_patient_overview, generate_patient_schedule

st.set_page_config(page_title="Patient Enrollment | Anti-Amyloid Tracker", page_icon="➕", layout="wide")
apply_custom_css()
user = verify_access()

st.title("➕ Patient Enrollment")
st.caption("Enroll a new patient into the tracking registry using the Medical Record Number (MRN) only.")

st.warning("🔒 **Compliance reminder**: Do NOT enter patient names, date of birth, phone numbers, or any other demographic identifiers.")

st.markdown("### Patient Details")

mrn_input = st.text_input(
    "Medical Record Number (MRN)*",
    placeholder="M001234567",
    help="Format: uppercase 'M' followed by '00' and 7 digits (e.g. M001234567)"
)

col1, col2 = st.columns(2)
with col1:
    drug = st.selectbox(
        "Selected Drug Therapy*",
        options=["lecanemab", "donanemab"],
        format_func=lambda s: s.title()
    )

    apoe_status = st.selectbox(
        "APOE Genetic Status*",
        options=["non-carrier", "heterozygote", "homozygote", "unknown"],
        format_func=lambda s: s.title()
    )

    baseline_mri = st.checkbox(
        "Baseline MRI Completed*",
        value=False,
        help="A baseline MRI must be completed prior to therapy initiation."
    )

with col2:
    infusion_location = st.selectbox(
        "Infusion Location*",
        options=["Talis", "Vivo", "UT North"]
    )

    cms_registry = st.text_input(
        "CMS Registry Number (Optional)",
        help="Enter CMS Registry identifier if available"
    )

st.markdown("---")
st.markdown("### 📅 Optional: Initial Treatment Schedule Setup")
auto_sched = st.checkbox(
    "Auto-generate initial Infusion & Surveillance MRI schedule from 1st Infusion Date",
    value=True,
    help="Pre-populates the patient's upcoming infusion and required safety MRI dates in their profile (you can edit any individual date later)."
)

col_s1, col_s2 = st.columns(2)
if auto_sched:
    with col_s1:
        first_infusion_date = st.date_input(
            "Planned 1st Infusion Date",
            value=datetime.date.today() + datetime.timedelta(days=7),
            format="MM/DD/YYYY"
        )
    with col_s2:
        num_planned_infusions = st.number_input(
            "Number of Infusions to Pre-Schedule",
            min_value=1,
            max_value=36,
            value=14 if drug == "lecanemab" else 8,
            step=1
        )

st.markdown("<small>* Indicates a required field</small>", unsafe_allow_html=True)

submitted = st.button("Enroll Patient", type="primary")

if submitted:
    cleaned_mrn = clean_mrn(mrn_input)

    if not mrn_input:
        st.error("Error: Medical Record Number (MRN) is required.")
    elif not is_valid_mrn(cleaned_mrn):
        st.error(f"Error: Invalid MRN format '{mrn_input}'. Must be an uppercase M followed by 00 and 7 digits (e.g., M001234567).")
    elif not baseline_mri:
        st.error("Error: Baseline MRI must be completed to enroll a patient for therapy.")
    else:
        try:
            existing = get_patient_overview(cleaned_mrn)
            if existing:
                st.error(f"Error: A patient with MRN '{cleaned_mrn}' is already enrolled.")
            else:
                patient_pk = enroll_patient(
                    mrn=cleaned_mrn,
                    drug=drug,
                    apoe_status=apoe_status,
                    baseline_mri_done=baseline_mri,
                    cms_registry_number=cms_registry,
                    infusion_location=infusion_location,
                    user_email=user['email']
                )
                if patient_pk:
                    if auto_sched:
                        generate_patient_schedule(
                            patient_pk=patient_pk,
                            drug=drug,
                            start_date=first_infusion_date,
                            num_infusions=int(num_planned_infusions),
                            user_email=user['email']
                        )
                    st.session_state["selected_patient_mrn"] = cleaned_mrn
                    st.session_state["last_enrolled_mrn"] = cleaned_mrn
                    st.success(
                        f"🎉 **Success!** Patient **{cleaned_mrn}** has been enrolled for **{drug.title()}** therapy"
                        + (f" with {int(num_planned_infusions)} scheduled infusions." if auto_sched else ".")
                    )
                    st.balloons()
                else:
                    st.error("Error: Failed to insert patient record. Please contact the administrator.")
        except Exception as e:
            st.error(f"Database error during enrollment: {e}")

if st.session_state.get("last_enrolled_mrn"):
    enrolled_mrn = st.session_state["last_enrolled_mrn"]
    st.info(f"Ready to view or customize **{enrolled_mrn}**'s schedule and clinical profile:")
    st.page_link(
        "pages/03_Patient_Profile.py",
        label=f"👤 Open {enrolled_mrn} in Patient Profile & Workspace ➔",
        icon="👤"
    )
