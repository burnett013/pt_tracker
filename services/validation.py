import re

def clean_mrn(mrn: str) -> str:
    """Cleans MRN by stripping whitespace and converting to uppercase."""
    if not mrn:
        return ""
    return mrn.strip().upper()

def is_valid_mrn(mrn: str) -> bool:
    """Validates MRN matches the format: uppercase M followed by '00' and 7 digits."""
    cleaned = clean_mrn(mrn)
    return bool(re.fullmatch(r"M00\d{7}", cleaned))

def is_valid_apoe(status: str) -> bool:
    """Validates APOE status."""
    return status in ('non-carrier', 'heterozygote', 'homozygote', 'unknown')

def is_valid_drug(drug: str) -> bool:
    """Validates drug choice."""
    return drug in ('lecanemab', 'donanemab')

def is_valid_infusion_location(location: str) -> bool:
    """Validates infusion location."""
    return location in ('Talis', 'Vivo', 'UT North')

def is_valid_cms_number(num: str) -> bool:
    """Validates CMS registry number if provided (optional)."""
    if not num:
        return True
    # Basic check, just check it is a simple code or non-empty string.
    # No strict format is defined in constraints, but we can clean it.
    return len(num.strip()) > 0
