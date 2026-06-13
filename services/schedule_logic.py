import datetime

MRI_REQUIREMENTS = {
    "lecanemab": [3, 5, 7, 14],
    "donanemab": [2, 3, 5, 7],
}

INFUSION_INTERVAL_DAYS = {
    "lecanemab": 14,
    "donanemab": 28,
}

def get_next_infusion_number(last_infusion_number: int | None) -> int:
    """Calculates the next infusion number given the last completed one."""
    return 1 if last_infusion_number is None else last_infusion_number + 1

def mri_required_before_next_infusion(drug: str, next_infusion_number: int) -> bool:
    """
    Returns True if an MRI is required before administering the next infusion.
    
    Lecanemab: Before infusions 3, 5, 7, and 14.
    Donanemab: Before infusions 2, 3, 5, and 7.
    """
    drug_lower = (drug or "").strip().lower()
    if drug_lower not in MRI_REQUIREMENTS:
        return False
    return next_infusion_number in MRI_REQUIREMENTS[drug_lower]

def get_infusion_interval_days(drug: str) -> int:
    """Returns the interval between infusions in days (Lecanemab: 14, Donanemab: 28)."""
    drug_lower = (drug or "").strip().lower()
    return INFUSION_INTERVAL_DAYS.get(drug_lower, 14)

def calculate_next_infusion_date(last_infusion_date: datetime.date | None, drug: str) -> datetime.date | None:
    """Calculates the scheduled date for the next infusion based on the drug interval."""
    if not last_infusion_date:
        return None
    
    # Ensure it's a date object
    if isinstance(last_infusion_date, str):
        last_infusion_date = datetime.datetime.strptime(last_infusion_date, "%Y-%m-%d").date()
        
    days = get_infusion_interval_days(drug)
    return last_infusion_date + datetime.timedelta(days=days)
