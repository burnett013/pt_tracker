import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import streamlit as st
import pandas as pd

from services.ui_components import (
    apply_custom_css,
    render_badge,
    format_date,
    format_timestamp_local,
    render_sidebar_assistant
)
from services.schedule_logic import (
    MRI_REQUIREMENTS,
    get_infusion_interval_days,
    mri_required_before_next_infusion
)
from services.dashboard_logic import evaluate_patient_status
from db.queries import (
    get_patient_overview,
    get_patient_history,
    update_patient_profile,
    update_therapy_status,
    record_infusion,
    update_infusion,
    delete_infusion,
    generate_patient_schedule,
    record_mri_and_aria,
    delete_mri,
    record_discontinuation,
    update_discontinuation,
    delete_discontinuation,
    record_phone_call,
    update_phone_call,
    delete_phone_call,
    confirm_phone_call_follow_up
)

st.set_page_config(page_title="Patient Profile | Anti-Amyloid Tracker", page_icon="👤", layout="wide")
apply_custom_css()
render_sidebar_assistant()

user = {"email": "demo@clinic.local", "username": "demo_user", "name": "Demo User"}

st.title("👤 Patient Profile & Clinical Workspace")
st.caption("Select a patient once to manage their treatment schedule, infusions, unified MRI & ARIA surveillance, phone calls, and audit history.")

# Load all patients
try:
    patients = get_patient_overview()
except Exception as e:
    st.error(f"Failed to connect to database: {e}")
    st.stop()

if not patients:
    st.info("No patients currently enrolled. Go to **Patient Enrollment** to add a patient.")
    st.stop()

patient_map = {p["mrn"]: p for p in patients}
mrns = sorted(list(patient_map.keys()))

# Determine selected MRN from query_params or session_state
query_mrn = st.query_params.get("mrn", "")
if query_mrn and query_mrn in mrns:
    st.session_state["selected_patient_mrn"] = query_mrn
elif "selected_patient_mrn" not in st.session_state or st.session_state["selected_patient_mrn"] not in mrns:
    st.session_state["selected_patient_mrn"] = mrns[0]

default_mrn_index = mrns.index(st.session_state["selected_patient_mrn"])

col_sel, col_nav_hint = st.columns([2, 3])
with col_sel:
    selected_mrn = st.selectbox(
        "Select Patient by MRN*",
        options=mrns,
        index=default_mrn_index,
        key="profile_mrn_selector"
    )
    if selected_mrn != st.session_state.get("selected_patient_mrn"):
        st.session_state["selected_patient_mrn"] = selected_mrn
        st.query_params["mrn"] = selected_mrn

patient = patient_map[selected_mrn]
patient_pk = patient["patient_pk"]
eval_status = evaluate_patient_status(dict(patient))
history = get_patient_history(patient_pk)

infusions_list = history.get("infusions", [])
mris_list = history.get("mris", [])
arias_list = history.get("aria_events", [])
discon_list = history.get("discontinuations", [])
calls_list = history.get("phone_calls", [])
audit_list = history.get("audit_logs", [])

# ==============================================================================
# PERSISTENT PATIENT SUMMARY HEADER
# ==============================================================================
status_color = {
    "continue": "success",
    "hold": "warning",
    "discontinue": "danger"
}.get(patient["therapy_status"], "secondary")

aria_badge_color = "danger" if eval_status["has_active_aria"] else "success"
aria_badge_label = eval_status["effective_aria_status"].upper() if eval_status["has_active_aria"] else "NONE / RESOLVED"

with st.container(border=True):
    h_col1, h_col2, h_col3, h_col4 = st.columns([1.3, 1.3, 1.5, 1.2])

    with h_col1:
        st.markdown(f"#### 🪪 `{patient['mrn']}`")
        st.markdown(f"**Drug Therapy:** `{patient['drug'].title()}`")
        st.markdown(f"**APOE Status:** `{(patient['apoe_status'] or 'unknown').title()}`")
        st.markdown(f"**Infusion Site:** `{patient['infusion_location'] or 'N/A'}`")

    with h_col2:
        st.markdown("#### 🩺 Clinical Status")
        st.markdown(
            f"**Therapy Status:** {render_badge(patient['therapy_status'].upper(), status_color)}",
            unsafe_allow_html=True
        )
        st.markdown(
            f"**ARIA Status:** {render_badge(aria_badge_label, aria_badge_color)}",
            unsafe_allow_html=True
        )
        st.markdown(f"**Baseline MRI:** `{'Completed' if patient['baseline_mri_done'] else 'Incomplete'}`")
        st.markdown(f"**CMS Registry #:** `{patient['cms_registry_number'] or 'N/A'}`")

    with h_col3:
        st.markdown("#### 💉 Schedule & Safety Summary")
        last_num = eval_status["last_infusion_number"] or 0
        next_num = eval_status["next_infusion_number"]
        st.markdown(f"**Completed Infusions:** `{last_num}` (Last: `{format_date(eval_status['last_infusion_date'], 'None')}`)")
        st.markdown(f"**Next Infusion (#{next_num}) Due:** `{format_date(eval_status['next_infusion_date'], 'Not Scheduled')}`")
        if eval_status["mri_pending"]:
            st.markdown(
                f"**Surveillance MRI:** {render_badge(f'REQUIRED BEFORE INF #{next_num}', 'danger')}",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"**Surveillance MRI:** {render_badge('CLEAR', 'success')}",
                unsafe_allow_html=True
            )
        if eval_status["has_prior_reaction"]:
            st.markdown(
                f"**Premedication:** {render_badge('PRIOR REACTION - PREMED REQUIRED', 'warning')}",
                unsafe_allow_html=True
            )

    with h_col4:
        st.markdown("#### ⚡ Quick Status Actions")
        if patient["therapy_status"] == "hold":
            if st.button("▶️ Resume Therapy (Set Continue)", key=f"hdr_resume_{selected_mrn}", type="primary", use_container_width=True):
                update_therapy_status(patient_pk, "continue", user["email"])
                st.success(f"Therapy resumed (`CONTINUE`) for {selected_mrn}.")
                st.rerun()
        elif patient["therapy_status"] == "continue":
            if st.button("⏸️ Place Therapy on HOLD", key=f"hdr_hold_{selected_mrn}", use_container_width=True):
                update_therapy_status(patient_pk, "hold", user["email"])
                st.warning(f"Therapy placed on `HOLD` for {selected_mrn}.")
                st.rerun()

        if eval_status["has_active_aria"]:
            if st.button("✅ Mark Active ARIA Resolved & Resume", key=f"hdr_resolve_aria_{selected_mrn}", use_container_width=True):
                update_therapy_status(patient_pk, "continue", user["email"], resolve_active_aria=True)
                st.success(f"ARIA marked resolved and therapy set to `CONTINUE` for {selected_mrn}.")
                st.rerun()

        st.caption(f"Enrolled: {format_timestamp_local(patient['enrolled_at'])}")

# Active Action Reasons Banner (if any)
if eval_status["needs_action"]:
    reasons_inline = "  •  ".join(eval_status["action_reasons"])
    st.warning(f"🚨 **Active Action Items for {selected_mrn}:**  {reasons_inline}")

# ==============================================================================
# WORKSPACE SECTION NAVIGATION (Synced with URL ?section=...)
# ==============================================================================
SECTION_MAP = {
    "schedule": "📅 Schedule & Infusions",
    "mri_aria": "🧠 MRI & ARIA Surveillance",
    "calls": "📞 Phone Call Log",
    "status": "⚙️ Profile, Hold & Discontinuation",
    "audit": "📋 Audit & Change Log"
}
REVERSE_SECTION_MAP = {v: k for k, v in SECTION_MAP.items()}
SECTION_LABELS = list(SECTION_MAP.values())

query_section = st.query_params.get("section", "")
if query_section in SECTION_MAP:
    st.session_state["active_profile_section"] = SECTION_MAP[query_section]
elif "active_profile_section" not in st.session_state or st.session_state["active_profile_section"] not in SECTION_LABELS:
    st.session_state["active_profile_section"] = SECTION_LABELS[0]

selected_section = st.radio(
    "Workspace Section",
    options=SECTION_LABELS,
    index=SECTION_LABELS.index(st.session_state["active_profile_section"]),
    horizontal=True,
    label_visibility="collapsed"
)

if selected_section != st.session_state.get("active_profile_section"):
    st.session_state["active_profile_section"] = selected_section
    st.query_params["mrn"] = selected_mrn
    st.query_params["section"] = REVERSE_SECTION_MAP[selected_section]

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ==============================================================================
# SECTION 1: SCHEDULE & INFUSIONS ("Sticky Note" Schedule + Check-Off + CRUD)
# ==============================================================================
if selected_section == "📅 Schedule & Infusions":
    st.subheader(f"📅 Treatment Schedule & Infusions — {selected_mrn} ({patient['drug'].title()})")

    mri_req_list = MRI_REQUIREMENTS.get(patient["drug"].lower(), [])
    interval_days = get_infusion_interval_days(patient["drug"])
    st.caption(
        f"**Protocol Schedule ({patient['drug'].title()}):** Infusions every **{interval_days} days**. "
        f"Mandatory Surveillance MRIs required prior to **Infusions #{', #'.join(map(str, mri_req_list))}**."
    )

    col_left, col_right = st.columns([1.4, 1.1])

    # ---- LEFT COLUMN: Full Sticky-Note Schedule View & Builder ----
    with col_left:
        st.markdown("#### 🗒️ Complete Patient Schedule (Infusions & Required MRIs)")

        # Build unified timeline combining infusions and required surveillance MRIs
        schedule_items = []
        completed_mri_dates = [m["mri_date"] for m in mris_list if m.get("status", "completed") == "completed"]
        scheduled_mris_by_target = {
            m["target_before_infusion"]: m
            for m in mris_list
            if m.get("target_before_infusion")
        }

        for inf in infusions_list:
            inf_no = inf["infusion_number"]
            inf_dt = inf["infusion_date"]
            sched_dt = inf.get("scheduled_date") or inf_dt
            st_val = inf.get("status", "completed")

            # Check if a surveillance MRI is required prior to this infusion
            if inf_no in mri_req_list:
                linked_mri = scheduled_mris_by_target.get(inf_no)
                # Check if any completed MRI occurred before/around this infusion (and after the prior infusion)
                prior_inf_dt = next(
                    (i["infusion_date"] for i in infusions_list if i["infusion_number"] == inf_no - 1 and i.get("status") == "completed"),
                    None
                )
                matching_completed_mri = next(
                    (
                        m for m in mris_list
                        if m.get("status", "completed") == "completed"
                        and (prior_inf_dt is None or m["mri_date"] >= prior_inf_dt)
                        and (st_val != "completed" or m["mri_date"] <= inf_dt)
                    ),
                    None
                )
                if matching_completed_mri:
                    schedule_items.append({
                        "Step": f"🧠 MRI (Before Inf #{inf_no})",
                        "Planned Date": format_date(matching_completed_mri.get("scheduled_date") or matching_completed_mri["mri_date"]),
                        "Completed Date": format_date(matching_completed_mri["mri_date"]),
                        "Status": "✅ Completed" if matching_completed_mri.get("proceed_to_next_infusion") else "🔴 Held",
                        "Reaction / Findings": "No ARIA" if matching_completed_mri.get("no_aria_confirmed") else (
                            "ARIA-E/H Present" if (matching_completed_mri.get("aria_e_present") or matching_completed_mri.get("aria_h_present")) else "Cleared"
                        ),
                        "Notes": matching_completed_mri.get("notes") or ""
                    })
                elif linked_mri:
                    schedule_items.append({
                        "Step": f"🧠 MRI (Before Inf #{inf_no})",
                        "Planned Date": format_date(linked_mri.get("scheduled_date") or linked_mri["mri_date"]),
                        "Completed Date": "-",
                        "Status": "🗓️ Scheduled (Required)",
                        "Reaction / Findings": "Pending Scan",
                        "Notes": linked_mri.get("notes") or f"Required prior to Infusion #{inf_no}"
                    })
                else:
                    est_mri_dt = sched_dt - datetime.timedelta(days=5) if sched_dt else None
                    schedule_items.append({
                        "Step": f"🧠 MRI (Before Inf #{inf_no})",
                        "Planned Date": format_date(est_mri_dt),
                        "Completed Date": "-",
                        "Status": "🚨 Required Before Inf #" + str(inf_no),
                        "Reaction / Findings": "Not Yet Logged",
                        "Notes": f"Mandatory safety MRI before Infusion #{inf_no}"
                    })

            status_display = {
                "completed": "✅ Completed",
                "scheduled": "🗓️ Scheduled",
                "missed": "⚠️ Missed",
                "cancelled": "❌ Cancelled"
            }.get(st_val, st_val.title())

            rx_sev = inf.get("reaction_severity") or "none"
            rx_display = f"⚠️ {rx_sev.title()}" if rx_sev != "none" else ("None" if st_val == "completed" else "-")

            schedule_items.append({
                "Step": f"💉 Infusion #{inf_no}",
                "Planned Date": format_date(sched_dt),
                "Completed Date": format_date(inf_dt) if st_val == "completed" else "-",
                "Status": status_display,
                "Reaction / Findings": rx_display,
                "Notes": inf.get("notes") or ""
            })

        if not schedule_items:
            st.info("No scheduled or completed infusions recorded yet. Use the Schedule Generator below or log an infusion on the right.")
        else:
            sched_df = pd.DataFrame(schedule_items)
            st.dataframe(sched_df, use_container_width=True, hide_index=True)

        # Schedule Generator / Bulk Builder Expander
        with st.expander("🗓️ Generate or Add Scheduled Infusions (Sticky-Note Builder)", expanded=not bool(infusions_list)):
            st.caption("Pre-populate upcoming scheduled infusion and mandatory MRI dates from a start date, or add a single scheduled infusion date.")
            g_col1, g_col2 = st.columns(2)
            with g_col1:
                gen_start_date = st.date_input(
                    "1st Infusion Start Date",
                    value=eval_status["last_infusion_date"] or datetime.date.today(),
                    format="MM/DD/YYYY",
                    key=f"gen_start_{selected_mrn}"
                )
            with g_col2:
                gen_count = st.number_input(
                    "Total Infusions in Schedule",
                    min_value=1,
                    max_value=36,
                    value=14 if patient["drug"] == "lecanemab" else 8,
                    step=1,
                    key=f"gen_count_{selected_mrn}"
                )
            if st.button("🗓️ Auto-Generate / Update Planned Schedule", key=f"btn_gen_sched_{selected_mrn}"):
                try:
                    generate_patient_schedule(
                        patient_pk=patient_pk,
                        drug=patient["drug"],
                        start_date=gen_start_date,
                        num_infusions=int(gen_count),
                        user_email=user["email"]
                    )
                    st.success(f"Generated {int(gen_count)}-infusion schedule and MRI checkpoints for {selected_mrn}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate schedule: {e}")

    # ---- RIGHT COLUMN: Check Off / Log Infusion + Edit/Delete Existing Infusions ----
    with col_right:
        st.markdown("#### ✅ Check Off / Log Infusion")

        next_num = eval_status["next_infusion_number"]
        mri_pending = eval_status["mri_pending"]
        last_date = eval_status["last_infusion_date"]

        # Safety check banner
        if eval_status["mri_surveillance_required"]:
            if mri_pending:
                st.error(
                    f"🚨 **CRITICAL HOLD WARNING**: Infusion #{next_num} requires a surveillance MRI scan. "
                    f"No completed MRI has been recorded since the last infusion ({format_date(last_date, 'N/A')}). "
                    f"Switch to **🧠 MRI & ARIA Surveillance** to log and clear the MRI before recording this completed infusion."
                )
            else:
                st.success(
                    f"🟢 **Clear to Proceed**: Surveillance MRI prior to Infusion #{next_num} was recorded on **{format_date(patient.get('last_mri_date'))}**."
                )
        else:
            st.info(f"🟢 **Surveillance Check**: No routine surveillance MRI is required prior to Infusion #{next_num}.")

        if patient["therapy_status"] == "hold":
            st.warning("⚠️ **Therapy on HOLD**: Ensure clinical clearance is granted before administering an infusion.")

        if eval_status["has_prior_reaction"]:
            st.warning("⚠️ **Premedication Alert**: Patient had a prior infusion reaction. Confirm premedication before infusion.")

        # Determine default infusion number & date from next scheduled infusion
        scheduled_infusions = [i for i in infusions_list if i.get("status") == "scheduled"]
        default_inf_num = scheduled_infusions[0]["infusion_number"] if scheduled_infusions else next_num
        default_inf_date = (
            (scheduled_infusions[0].get("scheduled_date") or scheduled_infusions[0]["infusion_date"])
            if scheduled_infusions
            else (eval_status["next_infusion_date"] or datetime.date.today())
        )

        f_col1, f_col2 = st.columns(2)
        with f_col1:
            log_inf_num = st.number_input(
                "Infusion Number*",
                min_value=1,
                max_value=100,
                value=int(default_inf_num),
                step=1,
                key=f"log_inf_num_{selected_mrn}"
            )
        with f_col2:
            log_inf_status = st.selectbox(
                "Entry Status*",
                options=["completed", "scheduled"],
                format_func=lambda s: "✅ Completed (Administered)" if s == "completed" else "🗓️ Scheduled (Planned Date)",
                key=f"log_inf_status_{selected_mrn}"
            )

        log_inf_date = st.date_input(
            "Infusion Date (Completed or Scheduled)*",
            value=default_inf_date,
            format="MM/DD/YYYY",
            key=f"log_inf_date_{selected_mrn}"
        )

        if log_inf_status == "completed":
            log_reaction = st.selectbox(
                "Infusion Reaction Severity",
                options=["none", "mild", "moderate", "severe", "anaphylaxis"],
                format_func=lambda s: s.title(),
                key=f"log_inf_rx_{selected_mrn}"
            )
        else:
            log_reaction = "none"

        log_notes = st.text_area(
            "Infusion / Schedule Notes",
            placeholder="Record vitals, reaction details, premedication given, or scheduling notes...",
            key=f"log_inf_notes_{selected_mrn}"
        )

        if st.button("💾 Save Infusion Record", type="primary", use_container_width=True, key=f"btn_save_inf_{selected_mrn}"):
            # Check if a mandatory MRI before this specific completed infusion is still pending
            req_mri_for_this = mri_required_before_next_infusion(patient["drug"], int(log_inf_num))
            if log_inf_status == "completed" and req_mri_for_this and mri_pending and int(log_inf_num) == next_num:
                st.error(f"Submission blocked: Surveillance MRI required before Infusion #{int(log_inf_num)} is still pending.")
            else:
                try:
                    premed = (log_reaction != "none")
                    record_infusion(
                        patient_pk=patient_pk,
                        infusion_number=int(log_inf_num),
                        infusion_date=log_inf_date,
                        reaction_severity=log_reaction,
                        premedication_reminder=premed,
                        notes=log_notes,
                        user_email=user["email"],
                        status=log_inf_status,
                        scheduled_date=log_inf_date
                    )
                    st.success(
                        f"🎉 Saved Infusion #{int(log_inf_num)} as **{log_inf_status.upper()}** ({format_date(log_inf_date)}) for **{selected_mrn}**!"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Database error saving infusion: {e}")

        # ---- EDIT / DELETE EXISTING INFUSION RECORD ----
        if infusions_list:
            with st.expander("✏️ Edit or Delete an Existing Infusion / Scheduled Date"):
                inf_options = {
                    f"Infusion #{i['infusion_number']} ({i.get('status', 'completed').title()} — {format_date(i['infusion_date'])})": i
                    for i in infusions_list
                }
                sel_inf_label = st.selectbox(
                    "Select Infusion Row to Modify",
                    options=list(inf_options.keys()),
                    key=f"edit_inf_sel_{selected_mrn}"
                )
                sel_inf = inf_options[sel_inf_label]

                e_col1, e_col2 = st.columns(2)
                with e_col1:
                    edit_inf_num = st.number_input(
                        "Infusion #",
                        min_value=1,
                        max_value=100,
                        value=int(sel_inf["infusion_number"]),
                        key=f"e_inf_num_{sel_inf['infusion_pk']}"
                    )
                    edit_sched_dt = st.date_input(
                        "Scheduled Date",
                        value=sel_inf.get("scheduled_date") or sel_inf["infusion_date"],
                        format="MM/DD/YYYY",
                        key=f"e_sched_dt_{sel_inf['infusion_pk']}"
                    )
                with e_col2:
                    status_opts = ["scheduled", "completed", "missed", "cancelled"]
                    cur_st = sel_inf.get("status", "completed")
                    edit_status = st.selectbox(
                        "Status",
                        options=status_opts,
                        index=status_opts.index(cur_st) if cur_st in status_opts else 1,
                        format_func=lambda s: s.title(),
                        key=f"e_inf_st_{sel_inf['infusion_pk']}"
                    )
                    edit_actual_dt = st.date_input(
                        "Actual / Effective Date",
                        value=sel_inf["infusion_date"],
                        format="MM/DD/YYYY",
                        key=f"e_act_dt_{sel_inf['infusion_pk']}"
                    )

                rx_opts = ["none", "mild", "moderate", "severe", "anaphylaxis"]
                cur_rx = sel_inf.get("reaction_severity") or "none"
                edit_rx = st.selectbox(
                    "Reaction Severity",
                    options=rx_opts,
                    index=rx_opts.index(cur_rx) if cur_rx in rx_opts else 0,
                    format_func=lambda s: s.title(),
                    key=f"e_inf_rx_{sel_inf['infusion_pk']}"
                )
                edit_premed = st.checkbox(
                    "Premedication Reminder Flag",
                    value=bool(sel_inf.get("premedication_reminder")) or (edit_rx != "none"),
                    key=f"e_inf_pre_{sel_inf['infusion_pk']}"
                )
                edit_inf_notes = st.text_area(
                    "Notes",
                    value=sel_inf.get("notes") or "",
                    key=f"e_inf_notes_{sel_inf['infusion_pk']}"
                )

                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("💾 Update Infusion", key=f"btn_upd_inf_{sel_inf['infusion_pk']}", type="primary", use_container_width=True):
                        try:
                            update_infusion(
                                infusion_pk=sel_inf["infusion_pk"],
                                infusion_number=int(edit_inf_num),
                                scheduled_date=edit_sched_dt,
                                infusion_date=edit_actual_dt,
                                status=edit_status,
                                reaction_severity=edit_rx,
                                premedication_reminder=edit_premed,
                                notes=edit_inf_notes,
                                user_email=user["email"]
                            )
                            st.success(f"Updated Infusion #{int(edit_inf_num)}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Update failed: {e}")
                with b_col2:
                    if st.button("🗑️ Delete Infusion", key=f"btn_del_inf_{sel_inf['infusion_pk']}", use_container_width=True):
                        try:
                            delete_infusion(sel_inf["infusion_pk"], user["email"])
                            st.warning(f"Deleted Infusion #{sel_inf['infusion_number']}.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Delete failed: {e}")

# ==============================================================================
# SECTION 2: UNIFIED MRI & ARIA SURVEILLANCE (Branching Logic + Atomic Sync)
# ==============================================================================
elif selected_section == "🧠 MRI & ARIA Surveillance":
    st.subheader(f"🧠 Unified MRI & ARIA Surveillance — {selected_mrn}")
    st.caption(
        "MRI scans and ARIA events are combined into one workflow. "
        "Logging or updating an MRI automatically synchronizes ARIA status and the patient's therapy status."
    )

    col_form, col_hist = st.columns([1.15, 1.35])

    with col_form:
        with st.container(border=True):
            st.markdown("#### 🧠 Log or Update MRI & ARIA Findings")

            # Check if there are scheduled MRIs to complete or existing MRIs to edit
            mri_mode_options = ["➕ Log New Completed MRI Scan", "🗓️ Schedule Future MRI Scan"]
            if mris_list:
                mri_mode_options.append("✏️ Edit Existing MRI / ARIA Record")

            mri_mode = st.radio(
                "Action Mode",
                options=mri_mode_options,
                horizontal=True,
                key=f"mri_mode_{selected_mrn}"
            )

            editing_mri = None
            if mri_mode == "✏️ Edit Existing MRI / ARIA Record" and mris_list:
                mri_edit_map = {
                    f"{format_date(m['mri_date'])} — {m['mri_type'].title()} ({m.get('status', 'completed').title()})": m
                    for m in mris_list
                }
                sel_mri_label = st.selectbox(
                    "Select MRI Scan to Edit",
                    options=list(mri_edit_map.keys()),
                    key=f"sel_edit_mri_{selected_mrn}"
                )
                editing_mri = mri_edit_map[sel_mri_label]

            m_col1, m_col2 = st.columns(2)
            mri_type_opts = ["scheduled surveillance", "ARIA follow-up", "unscheduled surveillance"]
            default_type_idx = 0
            if editing_mri and editing_mri.get("mri_type") in mri_type_opts:
                default_type_idx = mri_type_opts.index(editing_mri["mri_type"])
            elif eval_status["has_active_aria"]:
                default_type_idx = 1  # Default to ARIA follow-up when patient has active ARIA

            with m_col1:
                mri_type = st.selectbox(
                    "MRI Type*",
                    options=mri_type_opts,
                    index=default_type_idx,
                    format_func=lambda s: s.title() if s != "ARIA follow-up" else "ARIA Follow-up",
                    key=f"mri_type_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                )
            with m_col2:
                mri_date = st.date_input(
                    "MRI Scan Date*",
                    value=editing_mri["mri_date"] if editing_mri else datetime.date.today(),
                    format="MM/DD/YYYY",
                    key=f"mri_dt_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                )

            target_before_inf = None
            if mri_type == "scheduled surveillance":
                req_infs = MRI_REQUIREMENTS.get(patient["drug"].lower(), [])
                target_opts = [None] + req_infs
                cur_target = editing_mri.get("target_before_infusion") if editing_mri else (
                    eval_status["next_infusion_number"] if eval_status["next_infusion_number"] in req_infs else None
                )
                target_before_inf = st.selectbox(
                    "Surveillance Checkpoint (Before Infusion #)",
                    options=target_opts,
                    index=target_opts.index(cur_target) if cur_target in target_opts else 0,
                    format_func=lambda x: f"Prior to Infusion #{x}" if x else "General / Unspecified Checkpoint",
                    key=f"mri_target_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                )

            unscheduled_reason = None
            if mri_type == "unscheduled surveillance":
                unscheduled_reason = st.text_input(
                    "Reason for Unscheduled Scan (Symptoms)*",
                    value=(editing_mri.get("unscheduled_reason") or "") if editing_mri else "",
                    placeholder="e.g., headache, confusion, dizziness, gait disturbance, visual change...",
                    key=f"mri_unsched_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                )

            # If only scheduling a future scan, show notes and save button
            if mri_mode == "🗓️ Schedule Future MRI Scan":
                sched_notes = st.text_area(
                    "Scheduling Notes",
                    placeholder="Imaging center, appointment notes...",
                    key=f"mri_sched_notes_{selected_mrn}"
                )
                if st.button("🗓️ Save Scheduled MRI", type="primary", use_container_width=True):
                    try:
                        record_mri_and_aria(
                            patient_pk=patient_pk,
                            mri_date=mri_date,
                            scheduled_date=mri_date,
                            mri_type=mri_type,
                            status="scheduled",
                            target_before_infusion=target_before_inf,
                            unscheduled_reason=unscheduled_reason,
                            notes=sched_notes,
                            user_email=user["email"]
                        )
                        st.success(f"Scheduled {mri_type.title()} MRI on {format_date(mri_date)} for {selected_mrn}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error scheduling MRI: {e}")
            else:
                st.markdown("---")
                st.markdown("##### 🔬 Radiographic Findings (Branching Logic)")

                # NOTE: Removed the green check emoji from "No ARIA on this scan" per user feedback!
                default_no_aria = bool(editing_mri.get("no_aria_confirmed")) if editing_mri else False
                no_aria = st.checkbox(
                    "No ARIA on this scan",
                    value=default_no_aria,
                    help="Check this to confirm no ARIA was found on this scan.",
                    key=f"mri_no_aria_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                )

                aria_e = False
                aria_h = False
                radio_severity_e = None
                radio_severity_h = None
                aria_e_status = None
                aria_h_status = None

                if not no_aria:
                    f_c1, f_c2 = st.columns(2)
                    with f_c1:
                        aria_e = st.checkbox(
                            "ARIA-E Present (Edema / Effusion)",
                            value=bool(editing_mri.get("aria_e_present")) if editing_mri else False,
                            key=f"mri_ae_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                        )
                        if aria_e:
                            sev_opts = ["mild", "moderate", "severe"]
                            cur_se = (editing_mri.get("radiographic_severity_e") or "mild") if editing_mri else "mild"
                            radio_severity_e = st.selectbox(
                                "ARIA-E Radiographic Severity*",
                                options=sev_opts,
                                index=sev_opts.index(cur_se) if cur_se in sev_opts else 0,
                                format_func=lambda s: s.title(),
                                key=f"mri_seve_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                            )
                            e_st_opts = ["active", "stable", "improved", "worsened", "resolved"]
                            cur_est = (editing_mri.get("aria_e_status") or "active") if editing_mri else "active"
                            aria_e_status = st.selectbox(
                                "ARIA-E Finding Status",
                                options=e_st_opts,
                                index=e_st_opts.index(cur_est) if cur_est in e_st_opts else 0,
                                format_func=lambda s: s.title(),
                                key=f"mri_ste_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                            )

                    with f_c2:
                        aria_h = st.checkbox(
                            "ARIA-H Present (Microhemorrhage / Hemosiderosis)",
                            value=bool(editing_mri.get("aria_h_present")) if editing_mri else False,
                            key=f"mri_ah_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                        )
                        if aria_h:
                            sev_opts = ["mild", "moderate", "severe"]
                            cur_sh = (editing_mri.get("radiographic_severity_h") or "mild") if editing_mri else "mild"
                            radio_severity_h = st.selectbox(
                                "ARIA-H Radiographic Severity*",
                                options=sev_opts,
                                index=sev_opts.index(cur_sh) if cur_sh in sev_opts else 0,
                                format_func=lambda s: s.title(),
                                key=f"mri_sevh_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                            )
                            h_st_opts = ["active", "stable", "improved", "worsened", "resolved"]
                            cur_hst = (editing_mri.get("aria_h_status") or "active") if editing_mri else "active"
                            aria_h_status = st.selectbox(
                                "ARIA-H Finding Status",
                                options=h_st_opts,
                                index=h_st_opts.index(cur_hst) if cur_hst in h_st_opts else 0,
                                format_func=lambda s: s.title(),
                                key=f"mri_sth_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                            )

                other_findings = st.checkbox(
                    "Other Findings Present",
                    value=bool(editing_mri.get("other_findings")) if editing_mri else False,
                    key=f"mri_oth_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                )
                other_details = ""
                if other_findings:
                    other_details = st.text_area(
                        "Details of Other Findings*",
                        value=(editing_mri.get("other_findings_details") or "") if editing_mri else "",
                        placeholder="Describe other radiographic findings...",
                        key=f"mri_oth_det_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                    )

                # Branching section when ARIA is present OR scan is ARIA follow-up
                symptom_severity = "none"
                overall_aria_status = None
                monthly_mri_req = False
                revert_schedule = False
                restart_schedule = False

                if aria_e or aria_h or mri_type == "ARIA follow-up":
                    st.markdown("---")
                    st.markdown("##### ⚠️ ARIA Clinical Assessment & Follow-up Tracking")
                    a_c1, a_c2 = st.columns(2)
                    with a_c1:
                        sym_opts = ["none", "mild", "moderate", "severe"]
                        cur_sym = (editing_mri.get("symptom_severity") or "none") if editing_mri else "none"
                        symptom_severity = st.selectbox(
                            "Clinical Symptom Severity*",
                            options=sym_opts,
                            index=sym_opts.index(cur_sym) if cur_sym in sym_opts else 0,
                            format_func=lambda s: s.title(),
                            key=f"mri_sym_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                        )

                        # Smart default for overall ARIA status
                        ov_opts = ["active", "improved", "worsened", "resolved"]
                        if editing_mri and editing_mri.get("overall_aria_status") in ov_opts:
                            def_ov = ov_opts.index(editing_mri["overall_aria_status"])
                        elif no_aria or (aria_e_status == "resolved" and (not aria_h or aria_h_status == "resolved")):
                            def_ov = ov_opts.index("resolved")
                        elif aria_e_status == "improved":
                            def_ov = ov_opts.index("improved")
                        elif aria_e_status == "worsened" or aria_h_status == "worsened":
                            def_ov = ov_opts.index("worsened")
                        else:
                            def_ov = 0

                        overall_aria_status = st.selectbox(
                            "Overall ARIA Event Status*",
                            options=ov_opts,
                            index=def_ov,
                            format_func=lambda s: s.title(),
                            help="Setting to 'Resolved' automatically clears the Active ARIA alert on the patient profile and dashboard.",
                            key=f"mri_ov_status_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                        )

                    with a_c2:
                        monthly_mri_req = st.checkbox(
                            "Require Monthly Safety MRI Monitoring?",
                            value=False if overall_aria_status == "resolved" else (
                                bool(editing_mri.get("monthly_mri_required")) if editing_mri else True
                            ),
                            key=f"mri_mon_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                        )
                        revert_schedule = st.checkbox(
                            "Revert to original MRI schedule?",
                            value=bool(editing_mri.get("revert_to_original_mri_schedule")) if editing_mri else (overall_aria_status == "resolved"),
                            key=f"mri_rev_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                        )
                        restart_schedule = st.checkbox(
                            "Restart MRI schedule from beginning?",
                            value=bool(editing_mri.get("restart_mri_schedule")) if editing_mri else False,
                            key=f"mri_rest_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                        )

                st.markdown("---")
                st.markdown("##### 🛡️ Safety Clearance & Therapy Status Decision")

                action_opts = ["continue", "hold", "discontinue"]
                if editing_mri and editing_mri.get("therapy_action") in action_opts:
                    def_act_idx = action_opts.index(editing_mri["therapy_action"])
                elif (aria_e or aria_h) and overall_aria_status != "resolved":
                    def_act_idx = 1  # Default to Hold when active ARIA is checked
                else:
                    def_act_idx = 0  # Continue when No ARIA or ARIA resolved

                therapy_action = st.radio(
                    "Therapy Action & Clearance*",
                    options=action_opts,
                    index=def_act_idx,
                    format_func=lambda s: {
                        "continue": "🟢 Continue Therapy (Clear patient to proceed to next infusion)",
                        "hold": "⏸️ Hold Therapy (Place patient on clinical HOLD)",
                        "discontinue": "❌ Discontinue Therapy Permanently"
                    }[s],
                    key=f"mri_th_act_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                )
                proceed_flag = (therapy_action == "continue")

                mri_notes = st.text_area(
                    "Scan & Clinical Notes",
                    value=(editing_mri.get("notes") or "") if editing_mri else "",
                    placeholder="Record radiographic details, anatomical locations, sizes, or clinical disposition...",
                    key=f"mri_notes_{selected_mrn}_{editing_mri['mri_pk'] if editing_mri else 'new'}"
                )

                btn_label = "💾 Update MRI & Sync Patient Status" if editing_mri else "💾 Save MRI & Sync Patient Status"
                b_m1, b_m2 = st.columns([2, 1] if editing_mri else [1, 0.01])
                with b_m1:
                    if st.button(btn_label, type="primary", use_container_width=True, key=f"btn_save_mri_{selected_mrn}"):
                        if other_findings and not other_details.strip():
                            st.error("Please provide details for 'Other Findings Present'.")
                        elif mri_type == "unscheduled surveillance" and not (unscheduled_reason and unscheduled_reason.strip()):
                            st.error("Please provide a reason for the unscheduled scan.")
                        else:
                            try:
                                # If logging a new completed scheduled surveillance scan, check if a scheduled placeholder exists for this target
                                target_mri_pk = editing_mri["mri_pk"] if editing_mri else None
                                if not target_mri_pk and target_before_inf:
                                    sched_match = next(
                                        (
                                            m for m in mris_list
                                            if m.get("status") == "scheduled"
                                            and m.get("target_before_infusion") == target_before_inf
                                        ),
                                        None
                                    )
                                    if sched_match:
                                        target_mri_pk = sched_match["mri_pk"]

                                record_mri_and_aria(
                                    patient_pk=patient_pk,
                                    mri_date=mri_date,
                                    mri_type=mri_type,
                                    no_aria_confirmed=no_aria,
                                    aria_e_present=aria_e,
                                    aria_h_present=aria_h,
                                    radiographic_severity_e=radio_severity_e,
                                    radiographic_severity_h=radio_severity_h,
                                    symptom_severity=symptom_severity,
                                    other_findings=other_findings,
                                    other_findings_details=other_details if other_findings else None,
                                    proceed_to_next_infusion=proceed_flag,
                                    aria_e_status=aria_e_status,
                                    aria_h_status=aria_h_status,
                                    overall_aria_status=overall_aria_status,
                                    therapy_action=therapy_action,
                                    monthly_mri_required=monthly_mri_req,
                                    revert_to_original_mri_schedule=revert_schedule,
                                    restart_mri_schedule=restart_schedule,
                                    unscheduled_reason=unscheduled_reason,
                                    notes=mri_notes,
                                    user_email=user["email"],
                                    status="completed",
                                    target_before_infusion=target_before_inf,
                                    existing_mri_pk=target_mri_pk
                                )
                                st.success(
                                    f"🎉 Saved MRI/ARIA record for **{selected_mrn}** ({format_date(mri_date)}). "
                                    f"Patient therapy status synchronized to **{therapy_action.upper()}**!"
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Database error saving MRI/ARIA record: {e}")

                if editing_mri:
                    with b_m2:
                        if st.button("🗑️ Delete Scan", key=f"btn_del_mri_{editing_mri['mri_pk']}", use_container_width=True):
                            try:
                                delete_mri(editing_mri["mri_pk"], user["email"])
                                st.warning("Deleted MRI scan and linked ARIA event.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")

    # ---- RIGHT COLUMN: Unified MRI & ARIA History Timelines ----
    with col_hist:
        st.markdown("#### 📋 Unified MRI & ARIA Surveillance History")
        if not mris_list:
            st.info("No MRI scans recorded for this patient yet.")
        else:
            mri_rows = []
            for m in mris_list:
                st_str = m.get("status", "completed").title()
                e_str = (
                    f"Yes ({(m.get('radiographic_severity_e') or 'mild').title()})"
                    if m.get("aria_e_present") else "No"
                )
                h_str = (
                    f"Yes ({(m.get('radiographic_severity_h') or 'mild').title()})"
                    if m.get("aria_h_present") else "No"
                )
                ov_st = (m.get("overall_aria_status") or ("resolved" if m.get("no_aria_confirmed") else "-")).upper()
                clearance = (
                    "🗓️ Scheduled"
                    if m.get("status") == "scheduled"
                    else ("🟢 Cleared (Continue)" if m.get("proceed_to_next_infusion") else "🔴 Held")
                )
                mri_rows.append({
                    "Scan Date": format_date(m["mri_date"]),
                    "Scan Type": m["mri_type"].title(),
                    "Status": st_str,
                    "No ARIA": "Yes" if m.get("no_aria_confirmed") else "No",
                    "ARIA-E": e_str,
                    "ARIA-H": h_str,
                    "Symptom Sev": (m.get("symptom_severity") or "-").title(),
                    "ARIA Status": ov_st,
                    "Clearance": clearance,
                    "Notes / Unsched Reason": " | ".join(filter(None, [m.get("unscheduled_reason"), m.get("notes")]))
                })
            st.dataframe(pd.DataFrame(mri_rows), use_container_width=True, hide_index=True)

        st.markdown("#### ⚠️ ARIA Event Log Summary")
        if not arias_list:
            st.info("No ARIA events recorded for this patient.")
        else:
            aria_rows = []
            for a in arias_list:
                aria_rows.append({
                    "Date": format_date(a["aria_date"]),
                    "ARIA-E": f"Yes ({(a.get('radiographic_severity_e') or '-').title()})" if a.get("aria_e") else "No",
                    "ARIA-H": f"Yes ({(a.get('radiographic_severity_h') or '-').title()})" if a.get("aria_h") else "No",
                    "Symptoms": (a.get("symptom_severity") or "none").title(),
                    "ARIA Status": (a.get("status") or "").upper(),
                    "Therapy Action": (a.get("therapy_status") or "").upper(),
                    "Monthly MRI?": "Yes" if a.get("monthly_mri_required") else "No",
                    "Notes": a.get("notes") or ""
                })
            st.dataframe(pd.DataFrame(aria_rows), use_container_width=True, hide_index=True)

# ==============================================================================
# SECTION 3: PHONE CALL LOG (Linking + Confirmation + Full CRUD)
# ==============================================================================
elif selected_section == "📞 Phone Call Log":
    st.subheader(f"📞 Follow-up Phone Call Log — {selected_mrn}")

    next_call_num = (calls_list[0]["call_number"] + 1) if calls_list else 1

    # Pending Follow-ups Banner
    pending_calls = [c for c in calls_list if c.get("follow_up_required") and not c.get("follow_up_confirmed")]
    if pending_calls:
        st.warning(f"⚠️ **{selected_mrn} has {len(pending_calls)} pending phone call follow-up(s):**")
        for pc in pending_calls:
            target_str = format_date(pc.get("follow_up_date"), "Date not specified")
            c_info, c_act1, c_act2 = st.columns([3, 1.2, 1.2])
            with c_info:
                st.markdown(
                    f"**Call #{pc['call_number']} on {format_date(pc['call_date'])}** "
                    f"({pc['call_reason'].title()}) — Target Follow-up: `{target_str}`"
                )
                if pc.get("notes"):
                    st.caption(f"Notes: {pc['notes']}")
            with c_act1:
                if st.button("📞 Log Linked Follow-up", key=f"link_call_{pc['phone_call_pk']}", use_container_width=True):
                    st.session_state[f"preselect_parent_call_{selected_mrn}"] = pc["phone_call_pk"]
                    st.rerun()
            with c_act2:
                if st.button("✅ Follow-up Occurred", key=f"conf_call_{pc['phone_call_pk']}", use_container_width=True):
                    confirm_phone_call_follow_up(pc["phone_call_pk"], follow_up_confirmed=True, user_email=user["email"])
                    st.success(f"Call #{pc['call_number']} follow-up marked as confirmed!")
                    st.rerun()
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    c_left, c_right = st.columns([1.1, 1.4])

    with c_left:
        with st.container(border=True):
            st.markdown(f"#### 📞 Log New Phone Call (Call #{next_call_num})")

            parent_options = ["None (Initial / Standalone Call)"]
            parent_map = {}
            default_parent_idx = 0
            preselected_parent = st.session_state.get(f"preselect_parent_call_{selected_mrn}")

            for c in calls_list:
                lbl = f"Call #{c['call_number']} ({format_date(c['call_date'])} - {c['call_reason'].title()})"
                if c.get("follow_up_required") and not c.get("follow_up_confirmed"):
                    lbl += " [⚠️ Pending Follow-up]"
                parent_options.append(lbl)
                parent_map[lbl] = c["phone_call_pk"]
                if preselected_parent and c["phone_call_pk"] == preselected_parent:
                    default_parent_idx = len(parent_options) - 1

            sel_parent_label = st.selectbox(
                "Is this call a follow-up to a previous call?",
                options=parent_options,
                index=default_parent_idx,
                key=f"call_parent_{selected_mrn}"
            )
            sel_parent_pk = parent_map.get(sel_parent_label)

            if sel_parent_pk:
                st.info("🔗 Submitting this call will automatically mark the linked prior call's follow-up as **Confirmed**.")

            col_cd, col_cr = st.columns(2)
            with col_cd:
                call_date = st.date_input("Call Date*", value=datetime.date.today(), format="MM/DD/YYYY", key=f"call_dt_{selected_mrn}")
            with col_cr:
                call_reason = st.selectbox(
                    "Call Reason*",
                    options=["ARIA follow-up", "infusion reaction follow-up", "scheduling", "symptom check", "other"],
                    format_func=lambda s: s.title(),
                    key=f"call_rsn_{selected_mrn}"
                )

            call_outcome = st.selectbox(
                "Call Outcome*",
                options=["reached - no concerns", "reached - new symptoms", "reached - escalated", "voicemail left", "no answer"],
                format_func=lambda s: s.title(),
                key=f"call_out_{selected_mrn}"
            )

            f_req_str = st.radio(
                "Subsequent Follow-up Required?*",
                options=["No", "Yes"],
                horizontal=True,
                key=f"call_freq_{selected_mrn}"
            )
            follow_up_required = (f_req_str == "Yes")
            follow_up_date = None
            follow_up_confirmed = False

            if follow_up_required:
                fc1, fc2 = st.columns(2)
                with fc1:
                    follow_up_date = st.date_input(
                        "Target Follow-up Date*",
                        value=datetime.date.today() + datetime.timedelta(days=7),
                        format="MM/DD/YYYY",
                        key=f"call_fdt_{selected_mrn}"
                    )
                with fc2:
                    f_conf_str = st.radio(
                        "Follow-up Confirmed?",
                        options=["No", "Yes"],
                        horizontal=True,
                        key=f"call_fconf_{selected_mrn}"
                    )
                    follow_up_confirmed = (f_conf_str == "Yes")

            call_notes = st.text_area(
                "Call Notes",
                placeholder="Document conversation details, symptoms checked, or instructions...",
                key=f"call_notes_{selected_mrn}"
            )

            if st.button("💾 Log Phone Call", type="primary", use_container_width=True, key=f"btn_save_call_{selected_mrn}"):
                try:
                    record_phone_call(
                        patient_pk=patient_pk,
                        call_date=call_date,
                        call_reason=call_reason,
                        call_outcome=call_outcome,
                        follow_up_required=follow_up_required,
                        follow_up_date=follow_up_date,
                        follow_up_confirmed=follow_up_confirmed,
                        parent_call_pk=sel_parent_pk,
                        notes=call_notes,
                        user_email=user["email"]
                    )
                    st.session_state.pop(f"preselect_parent_call_{selected_mrn}", None)
                    st.success(f"🎉 Logged Call #{next_call_num} for **{selected_mrn}**!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error logging phone call: {e}")

    with c_right:
        st.markdown("#### 📋 Phone Call History")
        if not calls_list:
            st.info("No phone calls logged for this patient yet.")
        else:
            call_rows = []
            for c in calls_list:
                call_rows.append({
                    "Call ID": f"Call #{c['call_number']}",
                    "Date": format_date(c["call_date"]),
                    "Reason": c["call_reason"].title(),
                    "Outcome": c["call_outcome"].title(),
                    "Linked To": f"Call #{c['parent_call_number']}" if c.get("parent_call_number") else "Initial",
                    "Follow-up Req": "Yes" if c["follow_up_required"] else "No",
                    "Follow-up Date": format_date(c.get("follow_up_date")),
                    "Confirmed": "Yes" if c["follow_up_confirmed"] else ("No" if c["follow_up_required"] else "-"),
                    "Notes": c.get("notes") or ""
                })
            st.dataframe(pd.DataFrame(call_rows), use_container_width=True, hide_index=True)

            with st.expander("✏️ Edit or Delete an Existing Phone Call"):
                call_edit_map = {
                    f"Call #{c['call_number']} ({format_date(c['call_date'])} — {c['call_reason'].title()})": c
                    for c in calls_list
                }
                sel_call_lbl = st.selectbox("Select Call to Edit", options=list(call_edit_map.keys()), key=f"edit_call_sel_{selected_mrn}")
                sel_c = call_edit_map[sel_call_lbl]

                ec1, ec2 = st.columns(2)
                rsn_opts = ["ARIA follow-up", "infusion reaction follow-up", "scheduling", "symptom check", "other"]
                out_opts = ["reached - no concerns", "reached - new symptoms", "reached - escalated", "voicemail left", "no answer"]
                with ec1:
                    e_c_date = st.date_input("Call Date", value=sel_c["call_date"], format="MM/DD/YYYY", key=f"ec_dt_{sel_c['phone_call_pk']}")
                    e_c_rsn = st.selectbox(
                        "Call Reason",
                        options=rsn_opts,
                        index=rsn_opts.index(sel_c["call_reason"]) if sel_c["call_reason"] in rsn_opts else 0,
                        format_func=lambda s: s.title(),
                        key=f"ec_rsn_{sel_c['phone_call_pk']}"
                    )
                with ec2:
                    e_c_out = st.selectbox(
                        "Call Outcome",
                        options=out_opts,
                        index=out_opts.index(sel_c["call_outcome"]) if sel_c["call_outcome"] in out_opts else 0,
                        format_func=lambda s: s.title(),
                        key=f"ec_out_{sel_c['phone_call_pk']}"
                    )
                    e_c_freq = st.checkbox("Follow-up Required", value=bool(sel_c["follow_up_required"]), key=f"ec_freq_{sel_c['phone_call_pk']}")

                e_c_fdt = None
                e_c_fconf = bool(sel_c["follow_up_confirmed"])
                if e_c_freq:
                    efc1, efc2 = st.columns(2)
                    with efc1:
                        e_c_fdt = st.date_input(
                            "Follow-up Date",
                            value=sel_c.get("follow_up_date") or datetime.date.today(),
                            format="MM/DD/YYYY",
                            key=f"ec_fdt_{sel_c['phone_call_pk']}"
                        )
                    with efc2:
                        e_c_fconf = st.checkbox("Follow-up Confirmed", value=bool(sel_c["follow_up_confirmed"]), key=f"ec_fconf_{sel_c['phone_call_pk']}")

                e_c_notes = st.text_area("Notes", value=sel_c.get("notes") or "", key=f"ec_notes_{sel_c['phone_call_pk']}")

                cb1, cb2 = st.columns(2)
                with cb1:
                    if st.button("💾 Update Call", key=f"btn_upd_call_{sel_c['phone_call_pk']}", type="primary", use_container_width=True):
                        update_phone_call(
                            phone_call_pk=sel_c["phone_call_pk"],
                            call_date=e_c_date,
                            call_reason=e_c_rsn,
                            call_outcome=e_c_out,
                            follow_up_required=e_c_freq,
                            follow_up_date=e_c_fdt,
                            follow_up_confirmed=e_c_fconf,
                            notes=e_c_notes,
                            user_email=user["email"]
                        )
                        st.success(f"Updated Call #{sel_c['call_number']}!")
                        st.rerun()
                with cb2:
                    if st.button("🗑️ Delete Call", key=f"btn_del_call_{sel_c['phone_call_pk']}", use_container_width=True):
                        delete_phone_call(sel_c["phone_call_pk"], user["email"])
                        st.warning(f"Deleted Call #{sel_c['call_number']}.")
                        st.rerun()

# ==============================================================================
# SECTION 4: PROFILE, HOLD & DISCONTINUATION (Full CRUD)
# ==============================================================================
elif selected_section == "⚙️ Profile, Hold & Discontinuation":
    st.subheader(f"⚙️ Patient Profile, Therapy Status & Discontinuation — {selected_mrn}")

    p_col1, p_col2 = st.columns(2)

    with p_col1:
        with st.container(border=True):
            st.markdown("#### 🪪 Edit Patient Profile & Therapy Status")
            drug_opts = ["lecanemab", "donanemab"]
            apoe_opts = ["non-carrier", "heterozygote", "homozygote", "unknown"]
            loc_opts = ["Talis", "Vivo", "UT North"]
            th_opts = ["continue", "hold", "discontinue"]

            upd_drug = st.selectbox(
                "Drug Therapy",
                options=drug_opts,
                index=drug_opts.index(patient["drug"]) if patient["drug"] in drug_opts else 0,
                format_func=lambda s: s.title(),
                key=f"prof_drug_{selected_mrn}"
            )
            upd_apoe = st.selectbox(
                "APOE Genetic Status",
                options=apoe_opts,
                index=apoe_opts.index(patient["apoe_status"]) if patient["apoe_status"] in apoe_opts else 3,
                format_func=lambda s: s.title(),
                key=f"prof_apoe_{selected_mrn}"
            )
            upd_loc = st.selectbox(
                "Infusion Location",
                options=loc_opts,
                index=loc_opts.index(patient["infusion_location"]) if patient["infusion_location"] in loc_opts else 0,
                key=f"prof_loc_{selected_mrn}"
            )
            upd_cms = st.text_input(
                "CMS Registry Number",
                value=patient.get("cms_registry_number") or "",
                key=f"prof_cms_{selected_mrn}"
            )
            upd_base_mri = st.checkbox(
                "Baseline MRI Completed",
                value=bool(patient.get("baseline_mri_done")),
                key=f"prof_bmri_{selected_mrn}"
            )
            upd_th_status = st.selectbox(
                "Overall Therapy Status",
                options=th_opts,
                index=th_opts.index(patient["therapy_status"]) if patient["therapy_status"] in th_opts else 0,
                format_func=lambda s: s.upper(),
                key=f"prof_th_{selected_mrn}"
            )

            if st.button("💾 Save Profile Changes", type="primary", use_container_width=True, key=f"btn_save_prof_{selected_mrn}"):
                try:
                    update_patient_profile(
                        patient_pk=patient_pk,
                        drug=upd_drug,
                        apoe_status=upd_apoe,
                        baseline_mri_done=upd_base_mri,
                        cms_registry_number=upd_cms,
                        infusion_location=upd_loc,
                        therapy_status=upd_th_status,
                        user_email=user["email"]
                    )
                    st.success(f"Updated patient profile for **{selected_mrn}**!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error updating profile: {e}")

    with p_col2:
        with st.container(border=True):
            st.markdown("#### ❌ Record or Manage Therapy Discontinuation")

            existing_discon = discon_list[0] if discon_list else None
            if existing_discon:
                st.warning(
                    f"Patient was marked **DISCONTINUED** on **{format_date(existing_discon['discontinuation_date'])}** "
                    f"(Reason: `{existing_discon['reason'].upper()}`). You can update or revert this record below."
                )

            discon_date = st.date_input(
                "Discontinuation Date*",
                value=existing_discon["discontinuation_date"] if existing_discon else datetime.date.today(),
                format="MM/DD/YYYY",
                key=f"dis_dt_{selected_mrn}"
            )
            reason_opts = ["stroke", "DVT", "MI", "pulmonary embolism", "non-compliance", "disease progression", "other"]
            cur_rsn = existing_discon["reason"] if existing_discon and existing_discon["reason"] in reason_opts else "stroke"
            discon_reason = st.selectbox(
                "Primary Clinical Reason*",
                options=reason_opts,
                index=reason_opts.index(cur_rsn),
                format_func=lambda s: {
                    "stroke": "Stroke / CVA",
                    "DVT": "Deep Vein Thrombosis (DVT)",
                    "MI": "Myocardial Infarction (MI)",
                    "pulmonary embolism": "Pulmonary Embolism",
                    "non-compliance": "Patient Non-compliance",
                    "disease progression": "Disease Progression",
                    "other": "Other Reason (Specify Below)"
                }.get(s, s),
                key=f"dis_rsn_{selected_mrn}"
            )
            discon_other = ""
            if discon_reason == "other":
                discon_other = st.text_area(
                    "Other Reason Details*",
                    value=(existing_discon.get("other_reason_details") or "") if existing_discon else "",
                    key=f"dis_oth_{selected_mrn}"
                )

            discon_mri_req = st.checkbox(
                "Post-Discontinuation Follow-up Safety MRI Required?",
                value=bool(existing_discon.get("follow_up_mri_required")) if existing_discon else True,
                key=f"dis_mri_{selected_mrn}"
            )
            discon_notes = st.text_area(
                "Discontinuation Notes",
                value=(existing_discon.get("notes") or "") if existing_discon else "",
                key=f"dis_notes_{selected_mrn}"
            )

            if existing_discon:
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("💾 Update Discontinuation", type="primary", use_container_width=True, key=f"btn_upd_dis_{selected_mrn}"):
                        update_discontinuation(
                            discontinuation_pk=existing_discon["discontinuation_pk"],
                            discontinuation_date=discon_date,
                            reason=discon_reason,
                            other_reason_details=discon_other,
                            follow_up_mri_required=discon_mri_req,
                            notes=discon_notes,
                            user_email=user["email"]
                        )
                        st.success("Updated discontinuation record.")
                        st.rerun()
                with dc2:
                    if st.button("↩️ Revert Discontinuation & Resume", use_container_width=True, key=f"btn_del_dis_{selected_mrn}"):
                        delete_discontinuation(existing_discon["discontinuation_pk"], patient_pk, user["email"])
                        st.success("Removed discontinuation record and restored patient to active status.")
                        st.rerun()
            else:
                if st.button("❌ Record Permanent Discontinuation", type="primary", use_container_width=True, key=f"btn_rec_dis_{selected_mrn}"):
                    if discon_reason == "other" and not discon_other.strip():
                        st.error("Please provide details for 'Other Reason'.")
                    else:
                        record_discontinuation(
                            patient_pk=patient_pk,
                            discontinuation_date=discon_date,
                            reason=discon_reason,
                            other_reason_details=discon_other if discon_reason == "other" else None,
                            follow_up_mri_required=discon_mri_req,
                            notes=discon_notes,
                            user_email=user["email"]
                        )
                        st.success(f"Recorded permanent discontinuation for {selected_mrn}.")
                        st.rerun()

# ==============================================================================
# SECTION 5: AUDIT & CHANGE LOG (Central Time + Field-Level Diffs)
# ==============================================================================
elif selected_section == "📋 Audit & Change Log":
    st.subheader(f"📋 Database Operations Audit Trail — {selected_mrn}")
    st.caption("All timestamps are displayed in US Central Time (America/Chicago).")

    if not audit_list:
        st.info("No audit logs found for this patient.")
    else:
        def get_audit_details(row):
            action = row["action"]
            old_val = row["old_value"] or {}
            new_val = row["new_value"] or {}

            if action == "insert":
                summary_parts = []
                for k in ("infusion_number", "infusion_date", "status", "mri_type", "mri_date", "aria_e_present", "aria_h_present", "overall_aria_status", "therapy_status", "call_number", "call_reason", "reason"):
                    if k in new_val and new_val[k] is not None:
                        summary_parts.append(f"{k}={new_val[k]}")
                return "Created: " + (", ".join(summary_parts) if summary_parts else "New record")
            elif action == "delete":
                return "Record deleted."
            elif action == "update":
                changes = []
                for k, v in new_val.items():
                    old_v = old_val.get(k)
                    if old_v != v:
                        if k in ("updated_at", "updated_by", "created_at", "created_by"):
                            continue
                        changes.append(f"[{k}] '{old_v}' ➔ '{v}'")
                return ", ".join(changes) if changes else "Record touched (no field value changes)."
            return ""

        audit_rows = []
        for row in audit_list:
            audit_rows.append({
                "Timestamp (Central Time)": format_timestamp_local(row["changed_at"]),
                "Table": row["table_name"].upper(),
                "Action": row["action"].upper(),
                "User": row["changed_by"] or "system",
                "Details / Field Diffs": get_audit_details(row)
            })

        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)
