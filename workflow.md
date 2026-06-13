# Clinical Guide: How to Use the Patient Tracker

This guide outlines how doctors, nurses, and administrative staff use the **Anti-Amyloid Patient Tracking App** to monitor patients undergoing therapy (*lecanemab* or *donanemab*).

---

## 🔒 Security & Privacy Rules (Must-Know)

To comply with HIPAA and privacy safeguards:
1. **Never enter a patient's name, date of birth, phone number, or gender.**
2. The **Medical Record Number (MRN)** is the **only** patient identifier stored in this system.
3. **MRN Format**: Must be an uppercase **M** followed by **00** and **7 digits** (e.g., `M001234567`).
4. **Activity Logs**: All changes you make (adding patients, recording infusions, logging scans) are automatically logged with your login name and a timestamp for clinical safety auditing.

---

## 📊 1. The Dashboard (Your Daily Worklist)
When you log in, you will land on the **Clinical Dashboard**. This is your central hub:

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

1. Select **02 Patient Enrollment** in the sidebar.
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

1. Select **03 Infusion Update** in the sidebar.
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

1. Select **04 MRI Update** in the sidebar.
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

1. Select **05 ARIA Event** in the sidebar.
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

1. Select **06 Discontinuation Event** in the sidebar.
2. Select the patient's **MRN** and enter the **Discontinuation Date**.
3. Select the primary **Clinical Reason** (e.g., Stroke, Disease Progression, DVT). If selecting "Other", type specific details.
4. Check **Post-Discontinuation Follow-up Safety MRI Required** if follow-up safety scans are needed.
5. Click **Record Permanent Discontinuation**. (This permanently changes their status to inactive and removes them from scheduled infusion due dates).

---

## 🔍 7. How to Look Up a Patient's History
To review a patient's complete clinical timeline:

1. Select **07 Patient Lookup** in the sidebar.
2. Select the patient's **MRN**.
3. Use the tabs to browse:
   * **💉 Infusions History**: List of completed infusions, dates, and reactions.
   * **🧠 MRI Scans History**: List of scanned dates, types, findings, and holds.
   * **⚠️ ARIA Events History**: Chronological log of ARIA events, severities, and status.
   * **❌ Discontinuation details**: Reasons and follow-up plans.
   * **📋 Audit & Change Logs**: A human-readable history showing exactly **who** made changes to this patient's profile and **when**, outlining the exact changes (e.g. changing location from Talis to Vivo).
