import os
import json
import urllib.request
import urllib.error
import streamlit as st

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
WORKFLOW_PATH = os.path.join(BASE_DIR, "workflow.md")
SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")

@st.cache_data
def load_system_knowledge() -> str:
    """Reads the clinical workflow manual and prepares grounded context for Gemini."""
    workflow_text = ""
    if os.path.exists(WORKFLOW_PATH):
        try:
            with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
                workflow_text = f.read()
        except Exception:
            pass

    system_instruction = f"""You are the **Clinical Workflow Assistant** for the **Anti-Amyloid Patient Tracking System** (Project Elisabeth), serving clinical coordinators, nurses, and neurologists at UT Health East Texas / UT Tyler.

Your primary mission is to assist staff with navigating the 8 application workflows, understanding complex anti-amyloid therapy schedules, following ARIA safety protocols, and troubleshooting app actions.

### Core Grounding Knowledge & Rules:
{workflow_text}

### Clinical Safety & Schedule Highlights:
1. **Lecanemab (Leqembi)**:
   - Frequency: Every 2 weeks (14 days).
   - Mandatory Surveillance MRIs: Before Infusions #3, #5, #7, and #14.
   - Hard Safety Stop: The app blocks recording an infusion if a required surveillance MRI is pending.
2. **Donanemab (Kisunla)**:
   - Frequency: Every 4 weeks (28 days).
   - Mandatory Surveillance MRIs: Before Infusions #2, #3, #5, and #7.
3. **Phone Call Tracking**:
   - Each call has a sequential Call ID per patient (`Call #1`, `Call #2`...).
   - A follow-up call can be tied back to a prior call via the "Is this call a follow-up to a previous call?" dropdown.
   - Linking a follow-up call automatically marks the prior call's follow-up as confirmed.
   - Staff can also use the single-click 'Follow-up Call Occurred' button in the pending call banner to close out a requirement.
4. **ARIA Classifications**:
   - ARIA-E: Vasogenic edema / sulcal effusion.
   - ARIA-H: Microhemorrhages / superficial hemosiderosis.
   - Radiographic severities are tracked separately for E and H (`Mild`, `Moderate`, `Severe`).
   - If findings require stopping drug, clear to proceed is unchecked, placing patient on HOLD.

### Privacy & Governance Guardrails (CRITICAL):
- **HIPAA Compliance**: This assistant is for **operational workflow and clinical protocol questions only**.
- **No PII/PHI**: Never ask for or store patient names, dates of birth, phone numbers, or MRNs.
- If a user inputs patient-identifying data, advise them: *"Please do not enter patient names or identifiers into this chat. How can I help you with the app's workflow or schedule guidelines?"*
- Always be concise, helpful, and formatted in clean markdown.
"""
    return system_instruction

def get_gemini_api_key(api_key: str | None = None) -> str | None:
    """Resolves the Gemini API key from argument, session_state, secrets.toml, or environment variables."""
    key = api_key
    if not key:
        try:
            key = st.session_state.get("custom_gemini_key")
        except Exception:
            pass

    if not key:
        try:
            if hasattr(st, "secrets"):
                if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
                    key = st.secrets["gemini"]["api_key"]
                elif "GEMINI_API_KEY" in st.secrets:
                    key = st.secrets["GEMINI_API_KEY"]
                elif "postgres" in st.secrets and "GEMINI_API_KEY" in st.secrets["postgres"]:
                    key = st.secrets["postgres"]["GEMINI_API_KEY"]
        except Exception:
            pass

    if not key and os.path.exists(SECRETS_PATH):
        try:
            import tomllib
            with open(SECRETS_PATH, "rb") as f:
                cfg = tomllib.load(f)
                key = (
                    cfg.get("GEMINI_API_KEY")
                    or cfg.get("gemini", {}).get("api_key")
                    or cfg.get("postgres", {}).get("GEMINI_API_KEY")
                )
        except Exception:
            pass

    if not key:
        key = os.environ.get("GEMINI_API_KEY")

    if not key:
        return None

    cleaned = str(key).strip().strip('"').strip("'")
    return cleaned if cleaned else None

def generate_assistant_reply(
    history_text: str,
    system_instruction: str,
    api_key: str | None = None,
    model: str = "gemini-3.5-flash-lite"
) -> str:
    """Calls the Gemini REST API directly using stdlib urllib to avoid SDK/namespace issues."""
    key = get_gemini_api_key(api_key)
    if not key:
        raise ValueError("Missing Gemini API key.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": history_text}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            err_msg = err_json.get("error", {}).get("message", err_body)
        except Exception:
            err_msg = err_body
        raise RuntimeError(f"Gemini API HTTP {e.code}: {err_msg}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to reach Gemini API: {e}") from e

    candidates = data.get("candidates", [])
    if not candidates:
        return "No response generated. Please rephrase your question."

    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [p.get("text", "") for p in parts if "text" in p]
    return "\n".join(texts).strip() or "No text returned from assistant."

