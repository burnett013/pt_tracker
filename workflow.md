# Clinical Guide: How to Use the Anti-Amyloid Patient Tracker

This guide outlines how doctors, nurses, and clinical coordinators use the **Anti-Amyloid Patient Tracking App** to monitor patients undergoing therapy (*lecanemab* or *donanemab*).

---

## 🌐 Accessing the App

The application is hosted on **Posit Connect Cloud** and can be accessed at:

> **https://connect.posit.cloud/burnett013/content/019ec20d-5d57-ece3-12bf-d3fe94c74**

---

## 🏗️ Streamlined 3-Page Patient-Centric Architecture

The app is organized around **3 primary sidebar pages** so staff never have to repeatedly select the same patient across separate pages:

| Sidebar Page | Purpose |
|--------------|---------|
| **📊 01 Dashboard** | Daily clinical worklist, action cards, active roster, ARIA/MRI watchlists, and holds/discontinuations. Clicking any action button opens that patient's profile directly to the relevant section. |
| **➕ 02 Patient Enrollment** | Enroll a new patient by MRN, record APOE & baseline MRI status, and optionally auto-generate their upcoming Infusion & Surveillance MRI schedule from a 1st infusion date. |
| **👤 03 Patient Profile** | Unified clinical workspace for a selected patient with a persistent summary header and 5 interactive sections: **📅 Schedule & Infusions**, **🧠 MRI & ARIA Surveillance**, **📞 Phone Call Log**, **⚙️ Profile, Hold & Discontinuation**, and **📋 Audit & Change Log**. |

---

## 🔒 Security & Privacy Rules (Must-Know)

To comply with HIPAA and privacy safeguards:
1. **Never enter a patient's name, date of birth, phone number, or gender.**
2. The **Medical Record Number (MRN)** is the **only** patient identifier stored in this system.
3. **MRN Format**: Must be an uppercase **M** followed by **00** and **7 digits** (e.g., `M001234567`).
4. **Activity Logs**: All creations, edits, and deletions are automatically logged in **US Central Time (`America/Chicago`)** for clinical safety auditing.

---

## 📊 1. Dashboard (Your Daily Worklist)
- **🚨 Action Items This Week**: Priority cards for any patient with an infusion due within 7 days, a required surveillance MRI pending before their next infusion, active ARIA monitoring, a monthly ARIA MRI due, therapy on **HOLD**, premedication required due to a past reaction, or an unconfirmed phone call follow-up.
- **Direct Deep Links**: Clicking **📅 Schedule & Infusions**, **🧠 MRI & ARIA**, **📞 Phone Call Log**, **⚙️ Status & Profile**, or **📋 Audit Log** on any patient card opens **03 Patient Profile** pre-selected to that patient and section.
- **▶️ Resume Therapy**: For patients on `HOLD`, a **Resume Therapy** button sits directly beneath their card to restore their status to `CONTINUE`.

---

## ➕ 2. Patient Enrollment & Initial Schedule Generation
1. Select **Patient Enrollment** in the sidebar.
2. Enter the **MRN** (`M001234567`), **Drug Therapy** (*Lecanemab* or *Donanemab*), **APOE Genetic Status**, **Baseline MRI Completed**, **Infusion Location** (`Talis`, `Vivo`, `UT North`), and optional **CMS Registry Number**.
3. **Optional Initial Schedule Setup**: Keep **"Auto-generate initial Infusion & Surveillance MRI schedule"** checked and pick the **Planned 1st Infusion Date** to automatically build the patient's entire upcoming schedule of infusions and mandatory MRI checkpoints.
4. Click **Enroll Patient**, then click **👤 Open in Patient Profile & Workspace**.

---

## 👤 3. Patient Profile & Clinical Workspace

Once you select a patient at the top of **03 Patient Profile**, their **Persistent Summary Header** stays visible at the top (showing MRN, Drug, APOE, Location, Therapy Status badge, Active ARIA badge, Completed/Next Infusion dates, Surveillance MRI status, and quick **Hold / Resume / Resolve ARIA** buttons).

Switch between the 5 workspace sections below the header:

### 📅 Section A: Schedule & Infusions ("Sticky Note" Schedule + Check-Off)
- **Complete Patient Schedule**: Displays the full chronological list of **Scheduled & Completed Infusions** alongside **Mandatory Surveillance MRI Checkpoints** (*Lecanemab*: before Infusions #3, #5, #7, #14; *Donanemab*: before Infusions #2, #3, #5, #7).
- **Schedule Generator**: Expand **🗓️ Generate or Add Scheduled Infusions** to auto-populate upcoming infusion and MRI dates from any start date.
- **Check Off / Log Infusion**: Select the infusion number, choose **Completed (Administered)** or **Scheduled (Planned Date)**, confirm the date, and record any **Infusion Reaction Severity** (`None`, `Mild`, `Moderate`, `Severe`, `Anaphylaxis`).
  - *Hard Safety Stop*: Blocks logging a completed infusion if a required surveillance MRI before that infusion is still pending.
- **Edit or Delete Existing Infusions (Full CRUD)**: Expand **✏️ Edit or Delete an Existing Infusion / Scheduled Date** to adjust any planned date, completed date, status, reaction severity, or notes—or delete an entry. Changes sync immediately with the Dashboard and Header.

### 🧠 Section B: Unified MRI & ARIA Surveillance (Branching Logic)
Because an ARIA event always originates from an MRI scan, **MRI Update** and **ARIA Event** are combined into a single synchronized workflow:
1. Choose **Log New Completed MRI Scan**, **Schedule Future MRI Scan**, or **Edit Existing MRI / ARIA Record**.
2. Select **MRI Type** (`Scheduled Surveillance`, `ARIA Follow-up`, or `Unscheduled Surveillance`) and **MRI Scan Date**.
   - If `Unscheduled Surveillance`, enter the symptom reason (e.g., headache, confusion, visual disturbance).
3. **Radiographic Findings (Dynamic Branching)**:
   - Check **No ARIA on this scan** if the scan is negative for ARIA.
   - Or check **ARIA-E Present** and/or **ARIA-H Present** to dynamically reveal:
     - **ARIA-E / ARIA-H Radiographic Severity** (`Mild`, `Moderate`, `Severe`) and **Finding Status** (`Active`, `Stable`, `Improved`, `Worsened`, `Resolved`).
     - **Clinical Symptom Severity** (`None`, `Mild`, `Moderate`, `Severe`).
     - **Overall ARIA Event Status** (`Active`, `Improved`, `Worsened`, `Resolved`).
     - **Monthly Safety MRI Monitoring** and schedule revert/restart flags.
4. **Safety Clearance & Automatic Synchronization**:
   - Select **Continue Therapy (Clear to proceed)**, **Hold Therapy**, or **Discontinue Therapy**.
   - Clicking **Save MRI & Sync Patient Status** atomically updates the MRI log, the ARIA event log, and the patient's overall therapy status. Marking ARIA as **Resolved** and **Continue Therapy** automatically clears the Active ARIA alert and resumes therapy.

### 📞 Section C: Phone Call Log
- View and act on **Pending Follow-up Calls** at the top with 1-click **📞 Log Linked Follow-up** or **✅ Follow-up Occurred** buttons.
- Log new calls (`Call #1`, `Call #2`...), link follow-up calls to prior calls, and edit or delete any past call via the **✏️ Edit or Delete an Existing Phone Call** expander.

### ⚙️ Section D: Profile, Hold & Discontinuation
- **Edit Patient Profile**: Modify Drug Therapy, APOE Status, Infusion Location, CMS Registry Number, Baseline MRI flag, or overall Therapy Status at any time.
- **Manage Discontinuation**: Record permanent therapy discontinuation (`Stroke`, `DVT`, `MI`, `Pulmonary Embolism`, `Non-compliance`, `Disease Progression`, `Other`) and follow-up MRI requirements, or edit/revert an existing discontinuation.

### 📋 Section E: Audit & Change Log
- Displays a chronological audit trail of all `INSERT`, `UPDATE`, and `DELETE` actions for the patient, formatted in **US Central Time (`America/Chicago`)** with field-level diffs (`[therapy_status] 'hold' ➔ 'continue'`).
