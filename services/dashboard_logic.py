import datetime
from services.schedule_logic import (
    get_next_infusion_number,
    mri_required_before_next_infusion,
    calculate_next_infusion_date
)

def evaluate_patient_status(patient: dict, current_date: datetime.date = None) -> dict:
    """
    Evaluates a single patient's records and returns their status flags and alerts.
    
    Expected patient dictionary fields:
        - patient_pk (UUID)
        - mrn (str)
        - drug (str, 'lecanemab' or 'donanemab')
        - apoe_status (str)
        - baseline_mri_done (bool)
        - therapy_status (str, 'continue', 'hold', 'discontinue')
        - active (bool)
        
        - last_infusion_number (int or None)
        - last_infusion_date (date or None)
        - has_prior_reaction (bool) -- True if any prior infusion had a reaction
        
        - last_mri_date (date or None)
        - last_mri_type (str or None)
        
        - last_aria_date (date or None)
        - last_aria_status (str or None, 'active' or 'inactive')
        - monthly_mri_required (bool) -- True if active ARIA monthly monitoring is enabled
        
        - discontinuation_date (date or None)
        - follow_up_mri_required (bool) -- True if post-discontinuation follow-up MRI is required
    """
    if current_date is None:
        current_date = datetime.date.today()
        
    drug = patient.get("drug", "")
    therapy_status = patient.get("therapy_status", "continue")
    
    # 1. Infusion schedule details
    last_inf_no = patient.get("last_infusion_number")
    last_inf_date = patient.get("last_infusion_date")
    next_inf_no = get_next_infusion_number(last_inf_no)
    next_inf_date = calculate_next_infusion_date(last_inf_date, drug)
    
    # 2. Check if MRI is required before the next infusion
    # A surveillance MRI is required before next_inf_no for this drug
    mri_surveillance_required = mri_required_before_next_infusion(drug, next_inf_no)
    
    # Has an MRI been completed since the last infusion?
    # If a surveillance MRI is required, it must be performed after the last infusion date (or baseline MRI if it's the 1st infusion).
    mri_done_since_last_infusion = False
    if mri_surveillance_required:
        last_mri_date = patient.get("last_mri_date")
        if last_mri_date:
            if last_inf_date:
                mri_done_since_last_infusion = last_mri_date > last_inf_date
            else:
                # No infusions yet; check baseline or if any MRI is recorded
                mri_done_since_last_infusion = True # Since baseline is recorded separately or they have an MRI
                
    mri_pending = mri_surveillance_required and not mri_done_since_last_infusion
    
    # 3. Action check: Next infusion due in <= 7 days (or overdue)
    infusion_due_soon = False
    if next_inf_date and therapy_status == "continue":
        infusion_due_soon = next_inf_date <= current_date + datetime.timedelta(days=7)
        
    # 4. Active ARIA details
    # UPGRADE 4: 'active', 'improved', and 'worsened' all keep the patient under ARIA monitoring.
    # Only 'resolved' clears the active ARIA flag.
    last_aria_status = patient.get("last_aria_status")
    has_active_aria = last_aria_status in ("active", "improved", "worsened")
    
    # Monthly MRI check
    # Required if they have active ARIA, monthly_mri_required is True, and they haven't had an MRI in the last 30 days
    monthly_mri_due = False
    if has_active_aria and patient.get("monthly_mri_required", False):
        last_mri_date = patient.get("last_mri_date")
        reference_date = last_mri_date or patient.get("last_aria_date")
        if reference_date:
            days_since_ref = (current_date - reference_date).days
            monthly_mri_due = days_since_ref >= 30
            
    # 5. Premedication reminder (prior reaction)
    has_prior_reaction = patient.get("has_prior_reaction", False)
    
    # 6. Post-discontinuation follow-up MRI required
    discontinued_mri_pending = False
    if therapy_status == "discontinue" and patient.get("follow_up_mri_required", False):
        # Has an MRI been done after the discontinuation date?
        discon_date = patient.get("discontinuation_date")
        last_mri_date = patient.get("last_mri_date")
        if discon_date:
            if not last_mri_date or last_mri_date <= discon_date:
                discontinued_mri_pending = True
                
    # 6.5. Phone call action flag (UPGRADE 1)
    phone_call_action_required = False
    last_call_outcome = patient.get("last_call_outcome")
    call_follow_up_required = patient.get("call_follow_up_required", False)
    if last_call_outcome in ("reached - new symptoms", "reached - escalated") or call_follow_up_required:
        phone_call_action_required = True
                
    # 7. Evaluate if the patient needs action this week
    # A patient needs action if any of the following are True:
    reasons = []
    if infusion_due_soon:
        reasons.append("Next infusion due within 7 days")
    if mri_pending:
        reasons.append(f"Surveillance MRI required before Infusion #{next_inf_no}")
    if has_active_aria:
        reasons.append("Active ARIA event under monitoring")
    if monthly_mri_due:
        reasons.append("Monthly ARIA follow-up MRI is due")
    if therapy_status == "hold":
        reasons.append("Therapy status is on HOLD")
    if has_prior_reaction and therapy_status == "continue":
        reasons.append("Premedication reminder active (prior reaction)")
    if discontinued_mri_pending:
        reasons.append("Post-discontinuation follow-up MRI required")
    if phone_call_action_required:
        reasons.append("Phone call follow-up or symptom escalation action required")
        
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
        "mri_surveillance_required": mri_surveillance_required,
        "mri_pending": mri_pending,
        "has_active_aria": has_active_aria,
        "monthly_mri_due": monthly_mri_due,
        "has_prior_reaction": has_prior_reaction,
        "discontinued_mri_pending": discontinued_mri_pending,
        "phone_call_action_required": phone_call_action_required,
        "needs_action": needs_action,
        "action_reasons": reasons
    }
