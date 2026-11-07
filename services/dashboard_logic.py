import datetime
from services.schedule_logic import (
    get_next_infusion_number,
    mri_required_before_next_infusion,
    calculate_next_infusion_date
)

def evaluate_patient_status(patient: dict, current_date: datetime.date = None) -> dict:
    """
    Evaluates a single patient's records and returns their status flags and alerts.
    Respects explicit scheduled infusion/MRI dates when entered, falling back to
    calculated interval dates when no explicit schedule exists.
    """
    if current_date is None:
        current_date = datetime.date.today()

    drug = patient.get("drug", "")
    therapy_status = patient.get("therapy_status", "continue")

    # 1. Infusion schedule details (prefer explicit scheduled infusion date if stored)
    last_inf_no = patient.get("last_infusion_number")
    last_inf_date = patient.get("last_infusion_date")

    sched_inf_no = patient.get("next_scheduled_infusion_number")
    sched_inf_date = patient.get("next_scheduled_infusion_date")

    if sched_inf_no and (last_inf_no is None or sched_inf_no > last_inf_no):
        next_inf_no = sched_inf_no
        next_inf_date = sched_inf_date
    else:
        next_inf_no = get_next_infusion_number(last_inf_no)
        next_inf_date = sched_inf_date or calculate_next_infusion_date(last_inf_date, drug)

    # 2. Check if MRI is required before the next infusion
    mri_surveillance_required = mri_required_before_next_infusion(drug, next_inf_no)

    # Has a completed MRI been performed since the last completed infusion?
    mri_done_since_last_infusion = False
    if mri_surveillance_required:
        last_mri_date = patient.get("last_mri_date")
        if last_mri_date:
            if last_inf_date:
                mri_done_since_last_infusion = last_mri_date >= last_inf_date
            else:
                mri_done_since_last_infusion = True

    mri_pending = mri_surveillance_required and not mri_done_since_last_infusion

    # 3. Action check: Next infusion due in <= 7 days (or overdue)
    infusion_due_soon = False
    if next_inf_date and therapy_status == "continue":
        infusion_due_soon = next_inf_date <= current_date + datetime.timedelta(days=7)

    # 4. Active ARIA details (synchronized across aria_events and mris)
    last_aria_status = patient.get("last_aria_status")
    last_mri_overall_aria = patient.get("last_mri_overall_aria_status")
    last_aria_date = patient.get("last_aria_date")
    last_mri_date = patient.get("last_mri_date")

    # Determine the most recent ARIA status across mris and aria_events
    effective_aria_status = last_aria_status
    if last_mri_date and (not last_aria_date or last_mri_date >= last_aria_date):
        if last_mri_overall_aria:
            effective_aria_status = last_mri_overall_aria
        elif (patient.get("last_mri_aria_e") or patient.get("last_mri_aria_h")) and not effective_aria_status:
            effective_aria_status = "active"

    has_active_aria = effective_aria_status in ("active", "improved", "worsened")

    # Monthly MRI check
    monthly_mri_due = False
    if has_active_aria and patient.get("monthly_mri_required", False):
        reference_date = last_mri_date or last_aria_date
        if reference_date:
            days_since_ref = (current_date - reference_date).days
            monthly_mri_due = days_since_ref >= 30

    # 5. Premedication reminder (prior reaction)
    has_prior_reaction = patient.get("has_prior_reaction", False)

    # 6. Post-discontinuation follow-up MRI required
    discontinued_mri_pending = False
    if therapy_status == "discontinue" and patient.get("follow_up_mri_required", False):
        discon_date = patient.get("discontinuation_date")
        if discon_date:
            if not last_mri_date or last_mri_date <= discon_date:
                discontinued_mri_pending = True

    # 6.5. Phone call action flag
    phone_call_action_required = False
    last_call_outcome = patient.get("last_call_outcome")
    call_follow_up_required = patient.get("call_follow_up_required", False)
    call_follow_up_confirmed = patient.get("call_follow_up_confirmed", False)
    call_follow_up_date = patient.get("call_follow_up_date")

    unconfirmed_follow_up = call_follow_up_required and not call_follow_up_confirmed
    if last_call_outcome in ("reached - new symptoms", "reached - escalated") or unconfirmed_follow_up:
        phone_call_action_required = True

    # 7. Evaluate if the patient needs action this week
    reasons = []
    if infusion_due_soon:
        reasons.append(f"Next infusion (#{next_inf_no}) due {next_inf_date.strftime('%m/%d/%Y')}")
    if mri_pending:
        sched_mri_dt = patient.get("next_scheduled_mri_date")
        if sched_mri_dt:
            reasons.append(f"Surveillance MRI required before Infusion #{next_inf_no} (scheduled: {sched_mri_dt.strftime('%m/%d/%Y')})")
        else:
            reasons.append(f"Surveillance MRI required before Infusion #{next_inf_no}")
    if has_active_aria:
        reasons.append(f"Active ARIA event under monitoring ({effective_aria_status.upper()})")
    if monthly_mri_due:
        reasons.append("Monthly ARIA follow-up MRI is due")
    if therapy_status == "hold":
        reasons.append("Therapy status is on HOLD")
    if has_prior_reaction and therapy_status == "continue":
        reasons.append("Premedication reminder active (prior reaction)")
    if discontinued_mri_pending:
        reasons.append("Post-discontinuation follow-up MRI required")
    if phone_call_action_required:
        if unconfirmed_follow_up and call_follow_up_date:
            reasons.append(f"Phone call follow-up required (target: {call_follow_up_date.strftime('%m/%d/%Y')})")
        elif unconfirmed_follow_up:
            reasons.append("Phone call follow-up required")
        else:
            reasons.append("Phone call symptom escalation action required")

    needs_action = len(reasons) > 0

    return {
        "mrn": patient.get("mrn"),
        "drug": drug,
        "therapy_status": therapy_status,
        "active": patient.get("active", True),
        "last_infusion_number": last_inf_no,
        "last_infusion_date": last_inf_date,
        "next_infusion_number": next_inf_no,
        "next_infusion_date": next_inf_date,
        "next_scheduled_mri_date": patient.get("next_scheduled_mri_date"),
        "mri_surveillance_required": mri_surveillance_required,
        "mri_pending": mri_pending,
        "has_active_aria": has_active_aria,
        "effective_aria_status": effective_aria_status or "none",
        "monthly_mri_due": monthly_mri_due,
        "has_prior_reaction": has_prior_reaction,
        "discontinued_mri_pending": discontinued_mri_pending,
        "phone_call_action_required": phone_call_action_required,
        "needs_action": needs_action,
        "action_reasons": reasons
    }
