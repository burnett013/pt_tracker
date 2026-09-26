# Clinical Guide: How to Use the Patient Tracker

This guide outlines how doctors, nurses, and administrative staff use the **Anti-Amyloid Patient Tracking App** to monitor patients undergoing therapy (*lecanemab* or *donanemab*).

---

## 🌐 Accessing the App

The application is hosted on **Posit Connect Cloud** and can be accessed at:

> **https://connect.posit.cloud/burnett013/content/019ec20d-5d57-ece3-12bf-d3fe94c74**

No login or account is required for the current demo version. Simply open the link in any modern web browser.

### Sharing with Others
- Set the app's access to **"Anyone with the link"** in the Posit Connect Cloud settings (⚙️ gear icon → Access/Sharing).
- Send the URL above directly to any collaborator or reviewer.

---

## 🏗️ Architecture Overview

| Component | Technology | Details |
|-----------|-----------|---------|
| **Frontend** | Streamlit (Python) | Multi-page app with 7 workflow pages |
| **Database** | Neon Serverless PostgreSQL | Cloud-hosted, auto-scaling, SSL connections |
| **Hosting** | Posit Connect Cloud (Free tier) | Git-backed deployment from GitHub |
| **Source Code** | GitHub | https://github.com/burnett013/pt_tracker.git |

### Key Configuration
- **Database credentials** are stored as environment variables (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`) in the Posit Connect Cloud dashboard — never committed to Git.
- **Authentication** has been removed for demo purposes. All audit trail entries log as `demo@clinic.local`. Authentication can be re-enabled by restoring the `services/auth.py` integration when deploying to a production environment with Entra ID or similar identity provider.
- The `sys.path` injection at the top of `app.py` and each page under `pages/` is required for Posit Connect Cloud's sandboxed Python environment to resolve the `services` and `db` packages.

---

## 🔒 Security & Privacy Rules (Must-Know)

To comply with HIPAA and privacy safeguards:
1. **Never enter a patient's name, date of birth, phone number, or gender.**
2. The **Medical Record Number (MRN)** is the **only** patient identifier stored in this system.
3. **MRN Format**: Must be an uppercase **M** followed by **00** and **7 digits** (e.g., `M001234567`).
4. **Activity Logs**: All changes you make (adding patients, recording infusions, logging scans) are automatically logged with a user identifier and timestamp for clinical safety auditing.

---

## 📊 1. The Dashboard (Your Daily Worklist)
When you open the app, navigate to the **Dashboard** page in the sidebar. This is your central hub:

* **🚨 Action Items This Week**: This is your priority list. A patient appears here if they require immediate attention, including:
  * An infusion is due or overdue this week.
  * A safety MRI scan is required before their next infusion and has not been logged yet.
  * The patient has active ARIA.
  * A monthly ARIA follow-up MRI is due.
  * The patient's therapy is currently on **HOLD**.
  * The patient requires premedication due to a past infusion reaction.
* **📋 Active Patient Roster**: A searchable list of all patients currently undergoing therapy, showing their last infusion count, next due date, and safety flags.
* **🧠 ARIA & MRI Watchlist**: Summarizes patients under active ARIA monitoring and those awaiting routine safety scans.
* **⏸️ Holds & Discontinued**: Roster of patients whose therapy is suspended or permanently stopped.

---

## ➕ 2. How to Enroll a New Patient
Before a patient can receive their first infusion, they must be registered in the tracker:

1. Select **Patient Enrollment** in the sidebar.
2. Enter the patient's **MRN** (must match format: `M001234567`).
3. Select their prescribed **Drug Therapy** (*Lecanemab* or *Donanemab*).
4. Select their **APOE Genetic Status** (this guides clinical risk planning).
5. Check the **Baseline MRI Completed** box (required to initialize therapy).
6. Select the **Infusion Location** (Talis, Vivo, or UT North).
7. If available, enter the **CMS Registry Number**.
8. Click **Enroll Patient**.

---

## 💉 3. How to Log an Infusion
Every time a patient completes an infusion, it must be recorded to keep their schedule up-to-date:

1. Select **Infusion Update** in the sidebar.
2. Select the patient's **MRN** from the dropdown list.
3. Review the **Safety Check** panel:
   * **🔴 CRITICAL HOLD WARNING**: If a surveillance MRI is due before this infusion, the app will show a red block and **block you from submitting**. Do not administer the infusion.
   * **⚠️ Premedication Alert**: If the patient had an infusion reaction in the past, a warning will remind you to ensure premedication is given.
4. If clear to proceed, select the **Infusion Administration Date**.
5. Check **Infusion Reaction Occurred** if they experienced any adverse reaction.
6. Enter vitals or reaction details in the **Notes** box.
7. Click **Submit Infusion Record**.

---

## 🧠 4. How to Record an MRI Scan
Safety guidelines require periodic brain MRIs to monitor for ARIA. To log a scan:

1. Select **MRI Update** in the sidebar.
2. Select the patient's **MRN**.
3. Choose the **MRI Type**:
   * **Scheduled Surveillance**: Routine safety scans (e.g. before Infusion #3 for Lecanemab).
   * **ARIA Follow-up**: Scans performed to track resolving ARIA.
4. Enter the **MRI Scan Date**.
5. Check **ARIA-E Present** or **ARIA-H Present** if these findings are noted on the radiologist's report.
6. Check **Other Findings Present** to type specific details (like stroke risk signs).
7. **Safety Clearance (Critical)**:
   * **Clear to proceed?**: If the radiologist says it is safe to continue infusions, keep this checked.
   * **HOLD Therapy**: If new ARIA is found and infusions must stop, **uncheck** this box. This automatically puts the patient's therapy status on **HOLD** and flags them on the Dashboard.
8. Click **Record MRI scan**.

---

## ⚠️ 5. How to Log an ARIA Event
If a patient is diagnosed with ARIA (Amyloid-Related Imaging Abnormalities):

1. Select **ARIA Event** in the sidebar.
2. Select the patient's **MRN** and enter the **Detection Date**.
3. Check the type: **ARIA-E** (swelling) and/or **ARIA-H** (bleeding).
4. Select the **Radiographic Severity** (Mild, Moderate, Severe) and **Clinical Symptom Severity** (None, Mild, Moderate, Severe).
5. Select the **Recommended Therapy Action**:
   * **Hold**: Suspends infusions (patient appears on the Dashboard hold list).
   * **Discontinue**: Permanently stops therapy.
6. Check **Require Monthly Safety MRI Monitoring** to set a 30-day recurring MRI tracker on the Dashboard.
7. Click **Submit ARIA Event**.

---

## ❌ 6. How to Record a Discontinuation
If a patient permanently stops therapy (due to adverse events, disease progression, or choice):

1. Select **Discontinuation Event** in the sidebar.
2. Select the patient's **MRN** and enter the **Discontinuation Date**.
3. Select the primary **Clinical Reason** (e.g., Stroke, Disease Progression, DVT). If selecting "Other", type specific details.
4. Check **Post-Discontinuation Follow-up Safety MRI Required** if follow-up safety scans are needed.
5. Click **Record Permanent Discontinuation**. (This permanently changes their status to inactive and removes them from scheduled infusion due dates).

---

## 🔍 7. How to Look Up a Patient's History
To review a patient's complete clinical timeline:

1. Select **Patient Lookup** in the sidebar.
2. Select the patient's **MRN**.
3. Use the tabs to browse:
   * **💉 Infusions History**: List of completed infusions, dates, and reactions.
   * **🧠 MRI Scans History**: List of scanned dates, types, findings, and holds.
   * **⚠️ ARIA Events History**: Chronological log of ARIA events, severities, and status.
   * **❌ Discontinuation details**: Reasons and follow-up plans.
   * **📞 Phone Calls**: Chronological history of follow-up calls, scheduled follow-up dates, and confirmation status.
   * **📋 Audit & Change Logs**: A human-readable history showing exactly **who** made changes to this patient's profile and **when**, outlining the exact changes (e.g. changing location from Talis to Vivo).

---

## 📞 8. How to Log and Track Phone Calls

To document patient phone calls, link follow-ups, and track required actions:

1. Select **Phone Call Log** in the sidebar.
2. Select the patient's **MRN**. The app displays the patient's total call count and next sequential **Call ID** (e.g. `Call #1, Call #2`).
3. **Follow-up Linking**:
   * If this call is following up on a previous conversation, select the prior call from the **"Is this call a follow-up to a previous call?"** dropdown (or click the **"📞 Log Follow-up"** shortcut button directly on the prior call in the history table).
   * Submitting a linked follow-up automatically marks the original call's **Follow-up Confirmed** as **Yes**.
4. Enter the **Call Date** (formatted as `MM/DD/YYYY`), select the **Call Reason**, and record the **Call Outcome**.
5. **Follow-up Tracking**:
   * Select **Follow-up Required**: Choose **Yes** or **No**.
   * If **Yes**, enter the scheduled **Follow-up Date** and specify **Follow-up Confirmed** (**Yes** or **No**).
6. Add notes and click **Log Phone Call**.
7. **Pending Follow-up Action List**: Under the patient's history, any unconfirmed follow-up calls are prominently displayed with quick buttons to either **Log Follow-up** (pre-linking the call in the form above) or directly mark **Follow-up Call Occurred**.

---

## 🤖 9. Clinical AI Assistant & Workflow Guide

To assist clinical coordinators, nurses, and neurologists in navigating the application and verifying complex protocol guidelines:

1. Select **Clinical Assistant** in the sidebar (`pages/09_Clinical_Assistant.py`).
2. Type any operational or clinical scheduling query in natural language (or tap one of the Quick Topic buttons):
   * *"When are surveillance MRIs required for Lecanemab?"*
   * *"What happens when an ARIA-E event is detected?"*
   * *"How do I tie a follow-up phone call to a previous call?"*
   * *"Why is the app blocking me from logging Infusion #3?"*
3. **Safety & HIPAA Guardrail**:
   * The Assistant is grounded strictly in clinical protocols and system rules.
   * To ensure compliance with HIPAA, never enter patient names, dates of birth, or MRNs into the chat.

---

## 🔧 Developer Notes: Updating the App

### Making Code Changes
1. Edit files locally in the `anti_amyloid_tracker/` directory.
2. Commit and push to GitHub:
   ```bash
   git add -A
   git commit -m "Description of changes"
   git push origin main
   ```
3. Go to the Posit Connect Cloud dashboard and click **Republish** to pull the latest commit.

### Environment Variables
Set these in the Posit Connect Cloud dashboard under the app's settings → Environment Variables:
- Neon Database: `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`
- Gemini AI Assistant: `GEMINI_API_KEY` (Gemini API Key for the conversational assistant)

### Re-enabling Authentication
To restore authentication for production use:
1. Re-integrate `services/auth.py` by importing `render_auth_sidebar`, `get_logged_in_user`, and `verify_access` in `app.py` and all page files.
2. Configure the identity provider (e.g., Entra ID) in Posit Connect Cloud settings.
3. Set the `ALLOWED_USERS` environment variable to a comma-separated list of authorized email addresses.
