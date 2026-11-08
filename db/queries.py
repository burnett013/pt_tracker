import os
import datetime
import psycopg2
import psycopg2.extras
import streamlit as st

# Path configuration for loading secrets locally
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")

def load_db_config():
    """Loads database config from Streamlit secrets.toml or environment variables."""
    try:
        if "postgres" in st.secrets:
            return st.secrets["postgres"]
    except Exception:
        pass

    if os.path.exists(SECRETS_PATH):
        try:
            import tomllib
            with open(SECRETS_PATH, "rb") as f:
                config = tomllib.load(f)
                if "postgres" in config:
                    return config["postgres"]
        except Exception:
            pass

    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", 5432)),
        "database": os.environ.get("PGDATABASE", "project_elisabeth"),
        "user": os.environ.get("PGUSER", os.environ.get("USER", "")),
        "password": os.environ.get("PGPASSWORD", "")
    }

def get_connection():
    """Returns a new connection to the PostgreSQL database."""
    config = load_db_config()
    return psycopg2.connect(
        host=config.get("host"),
        port=config.get("port"),
        dbname=config.get("database"),
        user=config.get("user"),
        password=config.get("password")
    )

@st.cache_resource
def ensure_schema_migrations():
    """
    Idempotently applies schema upgrades and data synchronization backfills
    to the live database without losing any existing patient records.
    """
    conn = get_connection()
    try:
        conn.autocommit = True
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Infusions table upgrades (scheduled vs completed support)
            cur.execute("ALTER TABLE infusions ADD COLUMN IF NOT EXISTS scheduled_date DATE;")
            cur.execute("ALTER TABLE infusions ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'completed';")
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'infusions_status_check'
                    ) THEN
                        ALTER TABLE infusions ADD CONSTRAINT infusions_status_check
                        CHECK (status IN ('scheduled', 'completed', 'missed', 'cancelled'));
                    END IF;
                END $$;
            """)
            # Drop overly restrictive unique(patient_pk, infusion_date) so scheduled dates can be edited freely
            cur.execute("ALTER TABLE infusions DROP CONSTRAINT IF EXISTS infusions_patient_pk_infusion_date_key;")
            cur.execute("UPDATE infusions SET scheduled_date = infusion_date WHERE scheduled_date IS NULL;")

            # 2. MRIs table upgrades (unified ARIA fields + scheduled scan support)
            cur.execute("ALTER TABLE mris ADD COLUMN IF NOT EXISTS scheduled_date DATE;")
            cur.execute("ALTER TABLE mris ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'completed';")
            cur.execute("ALTER TABLE mris ADD COLUMN IF NOT EXISTS target_before_infusion INTEGER;")
            cur.execute("ALTER TABLE mris ADD COLUMN IF NOT EXISTS radiographic_severity_e TEXT;")
            cur.execute("ALTER TABLE mris ADD COLUMN IF NOT EXISTS radiographic_severity_h TEXT;")
            cur.execute("ALTER TABLE mris ADD COLUMN IF NOT EXISTS symptom_severity TEXT;")
            cur.execute("ALTER TABLE mris ADD COLUMN IF NOT EXISTS overall_aria_status TEXT;")
            cur.execute("ALTER TABLE mris ADD COLUMN IF NOT EXISTS therapy_action TEXT;")
            cur.execute("ALTER TABLE mris ADD COLUMN IF NOT EXISTS monthly_mri_required BOOLEAN DEFAULT FALSE;")

            # Relax aria_e_status and aria_h_status check constraints on mris to include 'active' and 'improved'
            cur.execute("ALTER TABLE mris DROP CONSTRAINT IF EXISTS mris_aria_e_status_check;")
            cur.execute("ALTER TABLE mris DROP CONSTRAINT IF EXISTS mris_aria_h_status_check;")
            cur.execute("""
                ALTER TABLE mris ADD CONSTRAINT mris_aria_e_status_check
                CHECK (aria_e_status IS NULL OR aria_e_status IN ('active', 'stable', 'improved', 'worsened', 'resolved'));
            """)
            cur.execute("""
                ALTER TABLE mris ADD CONSTRAINT mris_aria_h_status_check
                CHECK (aria_h_status IS NULL OR aria_h_status IN ('active', 'stable', 'improved', 'worsened', 'resolved'));
            """)

            # 3. ARIA events table linkage to mris
            cur.execute("ALTER TABLE aria_events ADD COLUMN IF NOT EXISTS mri_pk UUID REFERENCES mris(mri_pk) ON DELETE CASCADE;")

            # 4. Ensure audit trigger returns OLD on DELETE
            cur.execute("""
                CREATE OR REPLACE FUNCTION audit_trigger_func() RETURNS trigger AS $$
                DECLARE
                    old_val jsonb := NULL;
                    new_val jsonb := NULL;
                    tbl_name text := TG_TABLE_NAME;
                    rec_pk text;
                    act text := TG_OP;
                    usr text := current_setting('app.current_user', true);
                BEGIN
                    IF TG_OP = 'INSERT' THEN
                        new_val := to_jsonb(NEW);
                        CASE tbl_name
                            WHEN 'patients' THEN rec_pk := NEW.patient_pk::text;
                            WHEN 'infusions' THEN rec_pk := NEW.infusion_pk::text;
                            WHEN 'mris' THEN rec_pk := NEW.mri_pk::text;
                            WHEN 'aria_events' THEN rec_pk := NEW.aria_event_pk::text;
                            WHEN 'discontinuation_events' THEN rec_pk := NEW.discontinuation_pk::text;
                            WHEN 'phone_calls' THEN rec_pk := NEW.phone_call_pk::text;
                        END CASE;
                    ELSIF TG_OP = 'UPDATE' THEN
                        old_val := to_jsonb(OLD);
                        new_val := to_jsonb(NEW);
                        CASE tbl_name
                            WHEN 'patients' THEN rec_pk := NEW.patient_pk::text;
                            WHEN 'infusions' THEN rec_pk := NEW.infusion_pk::text;
                            WHEN 'mris' THEN rec_pk := NEW.mri_pk::text;
                            WHEN 'aria_events' THEN rec_pk := NEW.aria_event_pk::text;
                            WHEN 'discontinuation_events' THEN rec_pk := NEW.discontinuation_pk::text;
                            WHEN 'phone_calls' THEN rec_pk := NEW.phone_call_pk::text;
                        END CASE;
                    ELSIF TG_OP = 'DELETE' THEN
                        old_val := to_jsonb(OLD);
                        CASE tbl_name
                            WHEN 'patients' THEN rec_pk := OLD.patient_pk::text;
                            WHEN 'infusions' THEN rec_pk := OLD.infusion_pk::text;
                            WHEN 'mris' THEN rec_pk := OLD.mri_pk::text;
                            WHEN 'aria_events' THEN rec_pk := OLD.aria_event_pk::text;
                            WHEN 'discontinuation_events' THEN rec_pk := OLD.discontinuation_pk::text;
                            WHEN 'phone_calls' THEN rec_pk := OLD.phone_call_pk::text;
                        END CASE;
                    END IF;

                    IF usr IS NULL OR usr = '' THEN
                        usr := session_user;
                    END IF;

                    INSERT INTO audit_log (table_name, record_pk, action, changed_by, old_value, new_value)
                    VALUES (tbl_name, rec_pk, lower(act), usr, old_val, new_val);

                    IF TG_OP = 'DELETE' THEN
                        RETURN OLD;
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)

            # 5. Backfill & sync existing MRI rows that reported ARIA-E or ARIA-H but had no aria_events row
            cur.execute("""
                SELECT m.*
                FROM mris m
                WHERE (m.aria_e_present = TRUE OR m.aria_h_present = TRUE)
                  AND NOT EXISTS (
                      SELECT 1 FROM aria_events a
                      WHERE a.mri_pk = m.mri_pk
                         OR (a.patient_pk = m.patient_pk AND a.aria_date = m.mri_date)
                  );
            """)
            unlinked_mris = cur.fetchall()
            for m in unlinked_mris:
                inferred_status = "active"
                if m.get("aria_e_status") == "resolved" and (not m.get("aria_h_present") or m.get("aria_h_status") == "resolved"):
                    inferred_status = "resolved"
                elif m.get("aria_e_status") in ("improved", "worsened"):
                    inferred_status = m.get("aria_e_status")
                inferred_therapy = "continue" if m.get("proceed_to_next_infusion") else "hold"
                cur.execute("""
                    INSERT INTO aria_events (
                        patient_pk, mri_pk, aria_date, aria_e, aria_h,
                        radiographic_severity_e, radiographic_severity_h,
                        symptom_severity, status, therapy_status, monthly_mri_required, notes, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    m["patient_pk"],
                    m["mri_pk"],
                    m["mri_date"],
                    bool(m.get("aria_e_present")),
                    bool(m.get("aria_h_present")),
                    m.get("radiographic_severity_e") or ("mild" if m.get("aria_e_present") else None),
                    m.get("radiographic_severity_h") or ("mild" if m.get("aria_h_present") else None),
                    m.get("symptom_severity") or "none",
                    inferred_status,
                    inferred_therapy,
                    inferred_status != "resolved",
                    m.get("notes") or "Synced from MRI scan record",
                    m.get("created_by") or "system"
                ))

            # 5b. Backfill & sync existing ARIA events that had no corresponding MRI row
            cur.execute("""
                SELECT a.*
                FROM aria_events a
                WHERE a.mri_pk IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM mris m
                      WHERE m.patient_pk = a.patient_pk AND m.mri_date = a.aria_date
                  );
            """)
            unlinked_arias = cur.fetchall()
            for a in unlinked_arias:
                cur.execute("""
                    INSERT INTO mris (
                        patient_pk, scheduled_date, mri_date, status, mri_type,
                        no_aria_confirmed, aria_e_present, aria_h_present,
                        radiographic_severity_e, radiographic_severity_h, symptom_severity,
                        proceed_to_next_infusion, overall_aria_status, therapy_action,
                        monthly_mri_required, notes, created_by
                    ) VALUES (
                        %s, %s, %s, 'completed', 'scheduled surveillance',
                        FALSE, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    ) RETURNING mri_pk;
                """, (
                    a["patient_pk"], a["aria_date"], a["aria_date"],
                    bool(a.get("aria_e")), bool(a.get("aria_h")),
                    a.get("radiographic_severity_e"), a.get("radiographic_severity_h"),
                    a.get("symptom_severity") or "none",
                    a.get("therapy_status") == "continue",
                    a.get("status") or "active",
                    a.get("therapy_status") or "hold",
                    bool(a.get("monthly_mri_required")),
                    a.get("notes") or "Synced from ARIA event record",
                    a.get("created_by") or "system"
                ))
                new_mri_row = cur.fetchone()
                if new_mri_row:
                    cur.execute("UPDATE aria_events SET mri_pk = %s WHERE aria_event_pk = %s;", (new_mri_row["mri_pk"], a["aria_event_pk"]))

            # 6. Backfill & sync existing MRI rows where ARIA follow-up had no ARIA or marked ARIA resolved & cleared to proceed
            cur.execute("""
                SELECT DISTINCT ON (patient_pk) *
                FROM mris
                WHERE COALESCE(status, 'completed') = 'completed'
                ORDER BY patient_pk, mri_date DESC, created_at DESC;
            """)
            latest_mris = cur.fetchall()
            for lm in latest_mris:
                no_aria_found = (not lm.get("aria_e_present") and not lm.get("aria_h_present"))
                e_res = (lm.get("aria_e_status") == "resolved" or not lm.get("aria_e_present"))
                h_res = (lm.get("aria_h_status") == "resolved" or not lm.get("aria_h_present"))
                is_resolved_followup = (
                    lm.get("mri_type") == "ARIA follow-up"
                    and ((no_aria_found and lm.get("proceed_to_next_infusion") is True) or (e_res and h_res and lm.get("aria_e_status") == "resolved"))
                )
                if is_resolved_followup:
                    cur.execute("""
                        UPDATE mris
                        SET overall_aria_status = 'resolved',
                            aria_e_status = 'resolved',
                            therapy_action = CASE WHEN proceed_to_next_infusion THEN 'continue' ELSE 'hold' END
                        WHERE mri_pk = %s;
                    """, (lm["mri_pk"],))
                    cur.execute("""
                        UPDATE aria_events
                        SET status = 'resolved', monthly_mri_required = FALSE
                        WHERE patient_pk = %s AND aria_date <= %s AND status != 'resolved';
                    """, (lm["patient_pk"], lm["mri_date"]))
                    if lm.get("proceed_to_next_infusion") is True:
                        cur.execute("""
                            UPDATE patients
                            SET therapy_status = 'continue', updated_at = CURRENT_TIMESTAMP
                            WHERE patient_pk = %s AND therapy_status = 'hold';
                        """, (lm["patient_pk"],))
        return True
    except Exception:
        return False
    finally:
        conn.close()

def execute_transaction(queries_with_params, user_email="system"):
    """
    Executes multiple SQL operations inside a single database transaction.
    Sets the session variable 'app.current_user' so audit triggers capture the username.
    """
    ensure_schema_migrations()
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_user', %s, true);", (user_email,))

            last_result = None
            for query, params in queries_with_params:
                cur.execute(query, params)
                try:
                    if cur.description:
                        last_result = cur.fetchall()
                except psycopg2.ProgrammingError:
                    pass

            conn.commit()
            return last_result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_patient_overview(mrn=None):
    """
    Retrieves aggregated overview information for all patients, or a single patient if mrn is provided.
    Integrates completed infusions, next scheduled infusions, completed/scheduled MRIs, ARIA events,
    discontinuations, and phone calls.
    """
    ensure_schema_migrations()
    sql = """
    WITH latest_infusion AS (
        SELECT DISTINCT ON (patient_pk) *
        FROM infusions
        WHERE COALESCE(status, 'completed') = 'completed'
        ORDER BY patient_pk, infusion_number DESC, infusion_date DESC
    ),
    next_scheduled_infusion AS (
        SELECT DISTINCT ON (patient_pk) *
        FROM infusions
        WHERE status = 'scheduled'
        ORDER BY patient_pk, infusion_number ASC, COALESCE(scheduled_date, infusion_date) ASC
    ),
    reaction_summary AS (
        SELECT patient_pk, bool_or(reaction_severity != 'none') as has_prior_reaction
        FROM infusions
        WHERE COALESCE(status, 'completed') = 'completed'
        GROUP BY patient_pk
    ),
    latest_mri AS (
        SELECT DISTINCT ON (patient_pk) *
        FROM mris
        WHERE COALESCE(status, 'completed') = 'completed'
        ORDER BY patient_pk, mri_date DESC, created_at DESC
    ),
    next_scheduled_mri AS (
        SELECT DISTINCT ON (patient_pk) *
        FROM mris
        WHERE status = 'scheduled'
        ORDER BY patient_pk, COALESCE(scheduled_date, mri_date) ASC, created_at ASC
    ),
    latest_aria AS (
        SELECT DISTINCT ON (patient_pk) *
        FROM aria_events
        ORDER BY patient_pk, aria_date DESC, created_at DESC
    ),
    latest_discon AS (
        SELECT DISTINCT ON (patient_pk) *
        FROM discontinuation_events
        ORDER BY patient_pk, discontinuation_date DESC, created_at DESC
    ),
    latest_phone_call AS (
        SELECT DISTINCT ON (patient_pk) *
        FROM phone_calls
        ORDER BY patient_pk, call_number DESC, call_date DESC, created_at DESC
    )
    SELECT 
        p.patient_pk,
        p.mrn,
        p.drug,
        p.apoe_status,
        p.baseline_mri_done,
        p.cms_registry_number,
        p.infusion_location,
        p.therapy_status,
        p.active,
        p.enrolled_at,
        p.created_by,
        p.updated_at,
        p.updated_by,
        i.infusion_number as last_infusion_number,
        i.infusion_date as last_infusion_date,
        nsi.infusion_number as next_scheduled_infusion_number,
        COALESCE(nsi.scheduled_date, nsi.infusion_date) as next_scheduled_infusion_date,
        COALESCE(r.has_prior_reaction, FALSE) as has_prior_reaction,
        m.mri_date as last_mri_date,
        m.mri_type as last_mri_type,
        m.proceed_to_next_infusion as last_mri_proceed,
        m.aria_e_present as last_mri_aria_e,
        m.aria_h_present as last_mri_aria_h,
        m.overall_aria_status as last_mri_overall_aria_status,
        COALESCE(nsm.scheduled_date, nsm.mri_date) as next_scheduled_mri_date,
        nsm.target_before_infusion as next_scheduled_mri_target,
        a.aria_date as last_aria_date,
        a.status as last_aria_status,
        a.aria_e as last_aria_e,
        a.aria_h as last_aria_h,
        a.radiographic_severity_e as last_aria_severity_e,
        a.radiographic_severity_h as last_aria_severity_h,
        a.symptom_severity as last_aria_symptom_severity,
        COALESCE(a.monthly_mri_required, FALSE) as monthly_mri_required,
        d.discontinuation_date,
        d.reason as discontinuation_reason,
        COALESCE(d.follow_up_mri_required, FALSE) as follow_up_mri_required,
        c.call_number as last_call_number,
        c.call_date as last_call_date,
        c.call_outcome as last_call_outcome,
        COALESCE(c.follow_up_required, FALSE) as call_follow_up_required,
        c.follow_up_date as call_follow_up_date,
        COALESCE(c.follow_up_confirmed, FALSE) as call_follow_up_confirmed
    FROM patients p
    LEFT JOIN latest_infusion i ON p.patient_pk = i.patient_pk
    LEFT JOIN next_scheduled_infusion nsi ON p.patient_pk = nsi.patient_pk
    LEFT JOIN reaction_summary r ON p.patient_pk = r.patient_pk
    LEFT JOIN latest_mri m ON p.patient_pk = m.patient_pk
    LEFT JOIN next_scheduled_mri nsm ON p.patient_pk = nsm.patient_pk
    LEFT JOIN latest_aria a ON p.patient_pk = a.patient_pk
    LEFT JOIN latest_discon d ON p.patient_pk = d.patient_pk
    LEFT JOIN latest_phone_call c ON p.patient_pk = c.patient_pk
    """

    params = []
    if mrn:
        sql += " WHERE p.mrn = %s"
        params.append(mrn)

    sql += " ORDER BY p.enrolled_at DESC;"

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()
    finally:
        conn.close()

# ==============================================================================
# PATIENT PROFILE CRUD
# ==============================================================================

def enroll_patient(mrn, drug, apoe_status, baseline_mri_done, cms_registry_number, infusion_location, user_email):
    """Enrolls a new patient and logs it in the audit trail."""
    query = """
    INSERT INTO patients (mrn, drug, apoe_status, baseline_mri_done, cms_registry_number, infusion_location, created_by)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING patient_pk;
    """
    params = (mrn, drug, apoe_status, baseline_mri_done, cms_registry_number or None, infusion_location, user_email)
    res = execute_transaction([(query, params)], user_email)
    return res[0][0] if res else None

def update_patient_profile(patient_pk, drug, apoe_status, baseline_mri_done, cms_registry_number, infusion_location, therapy_status, user_email):
    """Updates a patient's core demographic/profile fields and therapy status."""
    active_flag = (therapy_status != 'discontinue')
    query = """
    UPDATE patients
    SET drug = %s,
        apoe_status = %s,
        baseline_mri_done = %s,
        cms_registry_number = %s,
        infusion_location = %s,
        therapy_status = %s,
        active = %s,
        updated_by = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE patient_pk = %s
    RETURNING patient_pk;
    """
    params = (
        drug, apoe_status, baseline_mri_done, cms_registry_number or None,
        infusion_location, therapy_status, active_flag, user_email, patient_pk
    )
    res = execute_transaction([(query, params)], user_email)
    return res[0][0] if res else None

def update_therapy_status(patient_pk, therapy_status, user_email, resolve_active_aria=False):
    """Directly updates a patient's therapy status (e.g. from hold to continue)."""
    active_flag = (therapy_status != 'discontinue')
    queries = [
        (
            """
            UPDATE patients 
            SET therapy_status = %s, active = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE patient_pk = %s;
            """,
            (therapy_status, active_flag, user_email, patient_pk)
        )
    ]
    if resolve_active_aria and therapy_status == "continue":
        queries.append((
            """
            UPDATE aria_events
            SET status = 'resolved', therapy_status = 'continue', monthly_mri_required = FALSE
            WHERE patient_pk = %s AND status IN ('active', 'improved', 'worsened');
            """,
            (patient_pk,)
        ))
    execute_transaction(queries, user_email)

# ==============================================================================
# INFUSIONS & SCHEDULE CRUD
# ==============================================================================

def record_infusion(patient_pk, infusion_number, infusion_date, reaction_severity="none", premedication_reminder=False, notes="", user_email="demo@clinic.local", status="completed", scheduled_date=None):
    """
    Records or updates a patient infusion event (scheduled or completed).
    Uses ON CONFLICT (patient_pk, infusion_number) so completing a previously scheduled
    infusion seamlessly updates that infusion number's record.
    """
    sched_dt = scheduled_date or infusion_date
    query = """
    INSERT INTO infusions (
        patient_pk, infusion_number, scheduled_date, infusion_date, status,
        reaction_severity, premedication_reminder, notes, created_by
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (patient_pk, infusion_number)
    DO UPDATE SET
        infusion_date = EXCLUDED.infusion_date,
        scheduled_date = COALESCE(infusions.scheduled_date, EXCLUDED.scheduled_date),
        status = EXCLUDED.status,
        reaction_severity = EXCLUDED.reaction_severity,
        premedication_reminder = EXCLUDED.premedication_reminder,
        notes = EXCLUDED.notes,
        created_by = EXCLUDED.created_by
    RETURNING infusion_pk;
    """
    params = (patient_pk, infusion_number, sched_dt, infusion_date, status, reaction_severity, premedication_reminder, notes, user_email)
    res = execute_transaction([(query, params)], user_email)
    return res[0][0] if res else None

def update_infusion(infusion_pk, infusion_number, scheduled_date, infusion_date, status, reaction_severity, premedication_reminder, notes, user_email="demo@clinic.local"):
    """Updates an existing infusion record by infusion_pk."""
    query = """
    UPDATE infusions
    SET infusion_number = %s,
        scheduled_date = %s,
        infusion_date = %s,
        status = %s,
        reaction_severity = %s,
        premedication_reminder = %s,
        notes = %s
    WHERE infusion_pk = %s
    RETURNING infusion_pk;
    """
    params = (infusion_number, scheduled_date or infusion_date, infusion_date, status, reaction_severity, premedication_reminder, notes, infusion_pk)
    res = execute_transaction([(query, params)], user_email)
    return res[0][0] if res else None

def delete_infusion(infusion_pk, user_email="demo@clinic.local"):
    """Deletes an infusion record by infusion_pk."""
    query = "DELETE FROM infusions WHERE infusion_pk = %s RETURNING infusion_pk;"
    res = execute_transaction([(query, (infusion_pk,))], user_email)
    return res[0][0] if res else None

def generate_patient_schedule(patient_pk, drug, start_date, num_infusions=14, user_email="demo@clinic.local"):
    """
    Auto-generates scheduled infusions and mandatory surveillance MRI placeholders
    starting from start_date (if not already completed).
    Lecanemab: every 14 days, MRIs before #3, #5, #7, #14.
    Donanemab: every 28 days, MRIs before #2, #3, #5, #7.
    """
    from services.schedule_logic import get_infusion_interval_days, MRI_REQUIREMENTS

    interval = get_infusion_interval_days(drug)
    mri_reqs = MRI_REQUIREMENTS.get((drug or "").lower(), [])

    queries = []
    for n in range(1, num_infusions + 1):
        inf_dt = start_date + datetime.timedelta(days=interval * (n - 1))
        # Upsert scheduled infusion only if not already completed
        inf_q = """
        INSERT INTO infusions (
            patient_pk, infusion_number, scheduled_date, infusion_date, status,
            reaction_severity, premedication_reminder, notes, created_by
        )
        VALUES (%s, %s, %s, %s, 'scheduled', 'none', FALSE, %s, %s)
        ON CONFLICT (patient_pk, infusion_number)
        DO UPDATE SET
            scheduled_date = EXCLUDED.scheduled_date,
            infusion_date = CASE WHEN infusions.status = 'scheduled' THEN EXCLUDED.infusion_date ELSE infusions.infusion_date END
        WHERE infusions.status = 'scheduled';
        """
        queries.append((inf_q, (patient_pk, n, inf_dt, inf_dt, f"Scheduled Infusion #{n}", user_email)))

        # If a surveillance MRI is required prior to this infusion, schedule it 5 days before the infusion
        if n in mri_reqs:
            mri_dt = inf_dt - datetime.timedelta(days=5)
            mri_q = """
            INSERT INTO mris (
                patient_pk, scheduled_date, mri_date, status, target_before_infusion,
                mri_type, no_aria_confirmed, aria_e_present, aria_h_present,
                proceed_to_next_infusion, notes, created_by
            )
            SELECT %s, %s, %s, 'scheduled', %s, 'scheduled surveillance', FALSE, FALSE, FALSE, TRUE, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM mris
                WHERE patient_pk = %s AND target_before_infusion = %s
            );
            """
            queries.append((
                mri_q,
                (
                    patient_pk, mri_dt, mri_dt, n,
                    f"Required Surveillance MRI prior to Infusion #{n}", user_email,
                    patient_pk, n
                )
            ))

    execute_transaction(queries, user_email)
    return True

# ==============================================================================
# UNIFIED MRI + ARIA CRUD & SYNCHRONIZATION
# ==============================================================================

def _build_mri_aria_sync_queries(
    patient_pk, mri_date, mri_type, status, scheduled_date, target_before_infusion,
    no_aria_confirmed, aria_e_present, aria_h_present,
    radiographic_severity_e, radiographic_severity_h, symptom_severity,
    other_findings, other_findings_details, proceed_to_next_infusion,
    aria_e_status, aria_h_status, overall_aria_status, therapy_action,
    monthly_mri_required, revert_to_original_mri_schedule, restart_mri_schedule,
    unscheduled_reason, notes, user_email, existing_mri_pk=None
):
    """
    Constructs the atomic SQL queries that keep `mris`, `aria_events`, and `patients.therapy_status`
    100% synchronized whenever an MRI/ARIA record is created or updated.
    """
    queries = []
    sched_dt = scheduled_date or mri_date

    if status == "scheduled":
        # Scheduled scan in the future: only write/update the MRI row without altering current active therapy/ARIA state
        if existing_mri_pk:
            q = """
            UPDATE mris
            SET scheduled_date = %s, mri_date = %s, status = 'scheduled',
                target_before_infusion = %s, mri_type = %s, unscheduled_reason = %s, notes = %s
            WHERE mri_pk = %s
            RETURNING mri_pk;
            """
            queries.append((q, (sched_dt, mri_date, target_before_infusion, mri_type, unscheduled_reason, notes, existing_mri_pk)))
        else:
            q = """
            INSERT INTO mris (
                patient_pk, scheduled_date, mri_date, status, target_before_infusion,
                mri_type, unscheduled_reason, notes, created_by
            ) VALUES (%s, %s, %s, 'scheduled', %s, %s, %s, %s, %s)
            RETURNING mri_pk;
            """
            queries.append((q, (patient_pk, sched_dt, mri_date, target_before_infusion, mri_type, unscheduled_reason, notes, user_email)))
        return queries

    # Completed scan normalization
    if no_aria_confirmed:
        aria_e_present = False
        aria_h_present = False
        radiographic_severity_e = None
        radiographic_severity_h = None

    has_aria_findings = bool(aria_e_present or aria_h_present)

    # Determine overall ARIA status
    if not overall_aria_status:
        if has_aria_findings:
            if aria_e_status == "resolved" and (not aria_h_present or aria_h_status == "resolved"):
                overall_aria_status = "resolved"
            elif aria_e_status in ("improved", "worsened"):
                overall_aria_status = aria_e_status
            elif aria_h_status == "worsened":
                overall_aria_status = "worsened"
            else:
                overall_aria_status = "active"
        elif mri_type == "ARIA follow-up" or no_aria_confirmed:
            if aria_e_status == "resolved" or no_aria_confirmed:
                overall_aria_status = "resolved"

    # Determine therapy action
    if not therapy_action:
        therapy_action = "continue" if proceed_to_next_infusion else "hold"

    if therapy_action in ("hold", "discontinue"):
        proceed_to_next_infusion = False
    elif therapy_action == "continue":
        proceed_to_next_infusion = True

    if existing_mri_pk:
        mri_q = """
        UPDATE mris
        SET scheduled_date = %s,
            mri_date = %s,
            status = 'completed',
            target_before_infusion = %s,
            mri_type = %s,
            no_aria_confirmed = %s,
            aria_e_present = %s,
            aria_h_present = %s,
            radiographic_severity_e = %s,
            radiographic_severity_h = %s,
            symptom_severity = %s,
            other_findings = %s,
            other_findings_details = %s,
            proceed_to_next_infusion = %s,
            aria_e_status = %s,
            aria_h_status = %s,
            overall_aria_status = %s,
            therapy_action = %s,
            monthly_mri_required = %s,
            revert_to_original_mri_schedule = %s,
            restart_mri_schedule = %s,
            unscheduled_reason = %s,
            notes = %s
        WHERE mri_pk = %s
        RETURNING mri_pk;
        """
        mri_params = (
            sched_dt, mri_date, target_before_infusion, mri_type, no_aria_confirmed,
            aria_e_present, aria_h_present,
            radiographic_severity_e if aria_e_present else None,
            radiographic_severity_h if aria_h_present else None,
            symptom_severity, other_findings, other_findings_details if other_findings else None,
            proceed_to_next_infusion, aria_e_status, aria_h_status, overall_aria_status,
            therapy_action, bool(monthly_mri_required), revert_to_original_mri_schedule,
            restart_mri_schedule, unscheduled_reason, notes, existing_mri_pk
        )
        queries.append((mri_q, mri_params))
    else:
        mri_q = """
        INSERT INTO mris (
            patient_pk, scheduled_date, mri_date, status, target_before_infusion,
            mri_type, no_aria_confirmed, aria_e_present, aria_h_present,
            radiographic_severity_e, radiographic_severity_h, symptom_severity,
            other_findings, other_findings_details, proceed_to_next_infusion,
            aria_e_status, aria_h_status, overall_aria_status, therapy_action,
            monthly_mri_required, revert_to_original_mri_schedule, restart_mri_schedule,
            unscheduled_reason, notes, created_by
        ) VALUES (
            %s, %s, %s, 'completed', %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
        RETURNING mri_pk;
        """
        mri_params = (
            patient_pk, sched_dt, mri_date, target_before_infusion,
            mri_type, no_aria_confirmed, aria_e_present, aria_h_present,
            radiographic_severity_e if aria_e_present else None,
            radiographic_severity_h if aria_h_present else None,
            symptom_severity,
            other_findings, other_findings_details if other_findings else None, proceed_to_next_infusion,
            aria_e_status, aria_h_status, overall_aria_status, therapy_action,
            bool(monthly_mri_required), revert_to_original_mri_schedule, restart_mri_schedule,
            unscheduled_reason, notes, user_email
        )
        queries.append((mri_q, mri_params))

    return queries

def record_mri_and_aria(
    patient_pk, mri_date, mri_type, no_aria_confirmed=False,
    aria_e_present=False, aria_h_present=False,
    radiographic_severity_e=None, radiographic_severity_h=None,
    symptom_severity="none", other_findings=False, other_findings_details=None,
    proceed_to_next_infusion=True, aria_e_status=None, aria_h_status=None,
    overall_aria_status=None, therapy_action=None, monthly_mri_required=False,
    revert_to_original_mri_schedule=False, restart_mri_schedule=False,
    unscheduled_reason=None, notes="", user_email="demo@clinic.local",
    status="completed", scheduled_date=None, target_before_infusion=None,
    existing_mri_pk=None
):
    """
    Unified function to record or update an MRI scan and automatically synchronize
    `aria_events` and `patients.therapy_status` in a single transaction.
    """
    ensure_schema_migrations()
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_user', %s, true);", (user_email,))

            queries = _build_mri_aria_sync_queries(
                patient_pk, mri_date, mri_type, status, scheduled_date, target_before_infusion,
                no_aria_confirmed, aria_e_present, aria_h_present,
                radiographic_severity_e, radiographic_severity_h, symptom_severity,
                other_findings, other_findings_details, proceed_to_next_infusion,
                aria_e_status, aria_h_status, overall_aria_status, therapy_action,
                monthly_mri_required, revert_to_original_mri_schedule, restart_mri_schedule,
                unscheduled_reason, notes, user_email, existing_mri_pk=existing_mri_pk
            )

            mri_pk = existing_mri_pk
            for q, params in queries:
                cur.execute(q, params)
                if cur.description:
                    row = cur.fetchone()
                    if row:
                        mri_pk = row[0]

            if status == "completed":
                if no_aria_confirmed:
                    aria_e_present = False
                    aria_h_present = False

                has_aria = bool(aria_e_present or aria_h_present)
                is_resolved_followup = (
                    mri_type == "ARIA follow-up"
                    or overall_aria_status == "resolved"
                    or (aria_e_status == "resolved" and aria_h_status in ("resolved", None))
                )

                if not therapy_action:
                    therapy_action = "continue" if proceed_to_next_infusion else "hold"

                eff_aria_status = overall_aria_status
                if not eff_aria_status:
                    if is_resolved_followup and not has_aria:
                        eff_aria_status = "resolved"
                    elif has_aria:
                        if aria_e_status == "resolved" and (not aria_h_present or aria_h_status == "resolved"):
                            eff_aria_status = "resolved"
                        elif aria_e_status in ("improved", "worsened"):
                            eff_aria_status = aria_e_status
                        else:
                            eff_aria_status = "active"

                # Sync aria_events table if ARIA is present OR if this scan updates/resolves an ARIA follow-up
                if has_aria or mri_type == "ARIA follow-up" or eff_aria_status in ("active", "improved", "worsened", "resolved"):
                    eff_status = eff_aria_status or ("resolved" if not has_aria else "active")
                    eff_monthly = False if eff_status == "resolved" else bool(monthly_mri_required)
                    sev_e = (radiographic_severity_e or "mild") if aria_e_present else None
                    sev_h = (radiographic_severity_h or "mild") if aria_h_present else None
                    sym_sev = symptom_severity or "none"

                    # Check if an aria_event is already linked to this mri_pk
                    cur.execute("SELECT aria_event_pk FROM aria_events WHERE mri_pk = %s;", (mri_pk,))
                    existing_aria = cur.fetchone()
                    if existing_aria:
                        cur.execute("""
                            UPDATE aria_events
                            SET aria_date = %s,
                                aria_e = %s,
                                aria_h = %s,
                                radiographic_severity_e = %s,
                                radiographic_severity_h = %s,
                                symptom_severity = %s,
                                status = %s,
                                therapy_status = %s,
                                monthly_mri_required = %s,
                                notes = %s
                            WHERE aria_event_pk = %s;
                        """, (
                            mri_date, aria_e_present, aria_h_present,
                            sev_e, sev_h, sym_sev, eff_status, therapy_action,
                            eff_monthly, notes, existing_aria[0]
                        ))
                    elif has_aria or mri_type == "ARIA follow-up":
                        cur.execute("""
                            INSERT INTO aria_events (
                                patient_pk, mri_pk, aria_date, aria_e, aria_h,
                                radiographic_severity_e, radiographic_severity_h,
                                symptom_severity, status, therapy_status,
                                monthly_mri_required, notes, created_by
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """, (
                            patient_pk, mri_pk, mri_date, aria_e_present, aria_h_present,
                            sev_e, sev_h, sym_sev, eff_status, therapy_action,
                            eff_monthly, notes, user_email
                        ))

                    # If resolved, also mark any earlier active ARIA events for this patient as resolved
                    if eff_status == "resolved":
                        cur.execute("""
                            UPDATE aria_events
                            SET status = 'resolved', monthly_mri_required = FALSE
                            WHERE patient_pk = %s AND aria_date <= %s AND status != 'resolved';
                        """, (patient_pk, mri_date))
                else:
                    # If edited to "No ARIA" on a regular surveillance scan, remove any aria_event tied to this mri_pk
                    cur.execute("DELETE FROM aria_events WHERE mri_pk = %s;", (mri_pk,))

                # Synchronize patient therapy_status in patients table
                active_flag = (therapy_action != "discontinue")
                cur.execute("""
                    UPDATE patients
                    SET therapy_status = %s,
                        active = %s,
                        updated_by = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE patient_pk = %s;
                """, (therapy_action, active_flag, user_email, patient_pk))

            conn.commit()
            return mri_pk
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_mri(mri_pk, user_email="demo@clinic.local"):
    """Deletes an MRI record (and any linked ARIA event via ON DELETE CASCADE)."""
    query = "DELETE FROM mris WHERE mri_pk = %s RETURNING mri_pk;"
    res = execute_transaction([(query, (mri_pk,))], user_email)
    return res[0][0] if res else None

# Legacy compatibility wrappers
def record_mri(patient_pk, mri_date, mri_type, no_aria_confirmed, aria_e_present, aria_h_present, other_findings,
               other_findings_details, proceed_to_next_infusion, aria_e_status, aria_h_status,
               revert_to_original_mri_schedule, restart_mri_schedule, unscheduled_reason, notes, user_email):
    return record_mri_and_aria(
        patient_pk=patient_pk, mri_date=mri_date, mri_type=mri_type,
        no_aria_confirmed=no_aria_confirmed, aria_e_present=aria_e_present, aria_h_present=aria_h_present,
        other_findings=other_findings, other_findings_details=other_findings_details,
        proceed_to_next_infusion=proceed_to_next_infusion,
        aria_e_status=aria_e_status, aria_h_status=aria_h_status,
        revert_to_original_mri_schedule=revert_to_original_mri_schedule,
        restart_mri_schedule=restart_mri_schedule,
        unscheduled_reason=unscheduled_reason, notes=notes, user_email=user_email
    )

def record_aria_event(patient_pk, aria_date, aria_e, aria_h, radiographic_severity_e, radiographic_severity_h,
                      symptom_severity, status, therapy_status, monthly_mri_required, notes, user_email):
    return record_mri_and_aria(
        patient_pk=patient_pk, mri_date=aria_date, mri_type="ARIA follow-up",
        no_aria_confirmed=not (aria_e or aria_h),
        aria_e_present=aria_e, aria_h_present=aria_h,
        radiographic_severity_e=radiographic_severity_e, radiographic_severity_h=radiographic_severity_h,
        symptom_severity=symptom_severity,
        proceed_to_next_infusion=(therapy_status == "continue"),
        overall_aria_status=status, therapy_action=therapy_status,
        monthly_mri_required=monthly_mri_required, notes=notes, user_email=user_email
    )

# ==============================================================================
# DISCONTINUATION CRUD
# ==============================================================================

def record_discontinuation(patient_pk, discontinuation_date, reason, other_reason_details, follow_up_mri_required, notes, user_email):
    """Records a patient's discontinuation of therapy and updates their status in the patients table."""
    queries = []

    discon_query = """
    INSERT INTO discontinuation_events (
        patient_pk, discontinuation_date, reason, other_reason_details, follow_up_mri_required, notes, created_by
    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING discontinuation_pk;
    """
    discon_params = (
        patient_pk, discontinuation_date, reason, other_reason_details, follow_up_mri_required, notes, user_email
    )
    queries.append((discon_query, discon_params))

    update_patient_query = """
    UPDATE patients 
    SET therapy_status = 'discontinue', active = FALSE, updated_by = %s, updated_at = CURRENT_TIMESTAMP 
    WHERE patient_pk = %s;
    """
    queries.append((update_patient_query, (user_email, patient_pk)))

    res = execute_transaction(queries, user_email)
    return res[0][0] if res else None

def update_discontinuation(discontinuation_pk, discontinuation_date, reason, other_reason_details, follow_up_mri_required, notes, user_email="demo@clinic.local"):
    """Updates an existing discontinuation record."""
    query = """
    UPDATE discontinuation_events
    SET discontinuation_date = %s,
        reason = %s,
        other_reason_details = %s,
        follow_up_mri_required = %s,
        notes = %s
    WHERE discontinuation_pk = %s
    RETURNING discontinuation_pk;
    """
    params = (discontinuation_date, reason, other_reason_details if reason == "other" else None, follow_up_mri_required, notes, discontinuation_pk)
    res = execute_transaction([(query, params)], user_email)
    return res[0][0] if res else None

def delete_discontinuation(discontinuation_pk, patient_pk, user_email="demo@clinic.local"):
    """Deletes a discontinuation event and restores the patient to active/continue status."""
    queries = [
        ("DELETE FROM discontinuation_events WHERE discontinuation_pk = %s;", (discontinuation_pk,)),
        (
            "UPDATE patients SET therapy_status = 'continue', active = TRUE, updated_by = %s, updated_at = CURRENT_TIMESTAMP WHERE patient_pk = %s;",
            (user_email, patient_pk)
        )
    ]
    execute_transaction(queries, user_email)
    return True

# ==============================================================================
# PHONE CALLS CRUD
# ==============================================================================

def record_phone_call(patient_pk, call_date, call_reason, call_outcome, follow_up_required, follow_up_date=None, follow_up_confirmed=False, parent_call_pk=None, notes=None, user_email="demo@clinic.local"):
    """
    Records a follow-up phone call for a patient, auto-incrementing call_number per patient.
    If parent_call_pk is supplied, links to that call and automatically marks the parent call's
    follow_up_confirmed as True in the same transaction.
    """
    insert_query = """
    INSERT INTO phone_calls (
        patient_pk, call_number, call_date, call_reason, call_outcome, 
        follow_up_required, follow_up_date, follow_up_confirmed, 
        parent_call_pk, notes, created_by
    ) VALUES (
        %s,
        (SELECT COALESCE(MAX(call_number), 0) + 1 FROM phone_calls WHERE patient_pk = %s),
        %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    RETURNING phone_call_pk, call_number;
    """
    insert_params = (
        patient_pk, patient_pk, call_date, call_reason, call_outcome,
        follow_up_required, follow_up_date, follow_up_confirmed,
        parent_call_pk, notes, user_email
    )

    queries = [(insert_query, insert_params)]

    if parent_call_pk:
        update_parent_query = """
        UPDATE phone_calls
        SET follow_up_confirmed = TRUE
        WHERE phone_call_pk = %s;
        """
        queries.append((update_parent_query, (parent_call_pk,)))

    res = execute_transaction(queries, user_email)
    return res[0][0] if res else None

def update_phone_call(phone_call_pk, call_date, call_reason, call_outcome, follow_up_required, follow_up_date, follow_up_confirmed, notes, user_email="demo@clinic.local"):
    """Updates an existing phone call record."""
    query = """
    UPDATE phone_calls
    SET call_date = %s,
        call_reason = %s,
        call_outcome = %s,
        follow_up_required = %s,
        follow_up_date = %s,
        follow_up_confirmed = %s,
        notes = %s
    WHERE phone_call_pk = %s
    RETURNING phone_call_pk;
    """
    params = (call_date, call_reason, call_outcome, follow_up_required, follow_up_date if follow_up_required else None, follow_up_confirmed, notes, phone_call_pk)
    res = execute_transaction([(query, params)], user_email)
    return res[0][0] if res else None

def delete_phone_call(phone_call_pk, user_email="demo@clinic.local"):
    """Deletes a phone call record."""
    query = "DELETE FROM phone_calls WHERE phone_call_pk = %s RETURNING phone_call_pk;"
    res = execute_transaction([(query, (phone_call_pk,))], user_email)
    return res[0][0] if res else None

def confirm_phone_call_follow_up(phone_call_pk, follow_up_confirmed=True, user_email="demo@clinic.local"):
    """Updates the follow-up confirmation status for an existing phone call."""
    query = """
    UPDATE phone_calls
    SET follow_up_confirmed = %s
    WHERE phone_call_pk = %s
    RETURNING phone_call_pk;
    """
    params = (follow_up_confirmed, phone_call_pk)
    res = execute_transaction([(query, params)], user_email)
    return res[0][0] if res else None

def get_phone_calls_by_patient(patient_pk):
    """Retrieves all phone call records for a patient, newest first, including linked parent call info."""
    ensure_schema_migrations()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    c.phone_call_pk,
                    c.call_number,
                    c.call_date,
                    c.call_reason,
                    c.call_outcome,
                    c.follow_up_required,
                    c.follow_up_date,
                    c.follow_up_confirmed,
                    c.parent_call_pk,
                    p.call_number as parent_call_number,
                    p.call_date as parent_call_date,
                    c.notes,
                    c.created_at,
                    c.created_by
                FROM phone_calls c
                LEFT JOIN phone_calls p ON c.parent_call_pk = p.phone_call_pk
                WHERE c.patient_pk = %s
                ORDER BY c.call_number DESC, c.call_date DESC;
            """, (patient_pk,))
            return cur.fetchall()
    finally:
        conn.close()

def get_patient_history(patient_pk):
    """
    Retrieves the complete historical timelines and scheduled events for a patient across all tracking tables.
    """
    ensure_schema_migrations()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Get infusions (both scheduled and completed, ordered by infusion_number ASC for schedule view)
            cur.execute("""
                SELECT infusion_pk, infusion_number, scheduled_date, infusion_date, status,
                       reaction_severity, premedication_reminder, notes, created_at, created_by
                FROM infusions
                WHERE patient_pk = %s
                ORDER BY infusion_number ASC, infusion_date ASC;
            """, (patient_pk,))
            infusions = cur.fetchall()

            # 2. Get MRIs (with joined ARIA event info if present)
            cur.execute("""
                SELECT m.mri_pk, m.scheduled_date, m.mri_date, m.status, m.target_before_infusion,
                       m.mri_type, m.no_aria_confirmed, m.aria_e_present, m.aria_h_present,
                       COALESCE(m.radiographic_severity_e, a.radiographic_severity_e) as radiographic_severity_e,
                       COALESCE(m.radiographic_severity_h, a.radiographic_severity_h) as radiographic_severity_h,
                       COALESCE(m.symptom_severity, a.symptom_severity) as symptom_severity,
                       m.other_findings, m.other_findings_details, m.proceed_to_next_infusion,
                       m.aria_e_status, m.aria_h_status,
                       COALESCE(m.overall_aria_status, a.status) as overall_aria_status,
                       COALESCE(m.therapy_action, a.therapy_status) as therapy_action,
                       COALESCE(m.monthly_mri_required, a.monthly_mri_required, FALSE) as monthly_mri_required,
                       m.revert_to_original_mri_schedule, m.restart_mri_schedule,
                       m.unscheduled_reason, m.notes, m.created_at, m.created_by,
                       a.aria_event_pk
                FROM mris m
                LEFT JOIN aria_events a ON a.mri_pk = m.mri_pk
                WHERE m.patient_pk = %s
                ORDER BY m.mri_date DESC, m.created_at DESC;
            """, (patient_pk,))
            mris = cur.fetchall()

            # 3. Get ARIA events
            cur.execute("""
                SELECT aria_event_pk, mri_pk, aria_date, aria_e, aria_h,
                       radiographic_severity_e, radiographic_severity_h,
                       symptom_severity, status, therapy_status, monthly_mri_required,
                       notes, created_at, created_by
                FROM aria_events
                WHERE patient_pk = %s
                ORDER BY aria_date DESC, created_at DESC;
            """, (patient_pk,))
            arias = cur.fetchall()

            # 4. Get discontinuation events
            cur.execute("""
                SELECT discontinuation_pk, discontinuation_date, reason, other_reason_details,
                       follow_up_mri_required, notes, created_at, created_by
                FROM discontinuation_events
                WHERE patient_pk = %s
                ORDER BY discontinuation_date DESC, created_at DESC;
            """, (patient_pk,))
            discon = cur.fetchall()

            # 5. Get phone calls
            cur.execute("""
                SELECT 
                    c.phone_call_pk,
                    c.call_number,
                    c.call_date,
                    c.call_reason,
                    c.call_outcome,
                    c.follow_up_required,
                    c.follow_up_date,
                    c.follow_up_confirmed,
                    c.parent_call_pk,
                    p.call_number as parent_call_number,
                    p.call_date as parent_call_date,
                    c.notes,
                    c.created_at,
                    c.created_by
                FROM phone_calls c
                LEFT JOIN phone_calls p ON c.parent_call_pk = p.phone_call_pk
                WHERE c.patient_pk = %s
                ORDER BY c.call_number DESC, c.call_date DESC;
            """, (patient_pk,))
            calls = cur.fetchall()

            # 6. Get audit logs (including deleted records whose patient_pk appears in old_value)
            cur.execute("""
                SELECT audit_pk, table_name, record_pk, action, changed_by, changed_at, old_value, new_value
                FROM audit_log
                WHERE (table_name = 'patients' AND record_pk = %s)
                   OR (old_value->>'patient_pk' = %s)
                   OR (new_value->>'patient_pk' = %s)
                ORDER BY changed_at DESC;
            """, (str(patient_pk), str(patient_pk), str(patient_pk)))
            audit = cur.fetchall()

            return {
                "infusions": infusions,
                "mris": mris,
                "aria_events": arias,
                "discontinuations": discon,
                "phone_calls": calls,
                "audit_logs": audit
            }
    finally:
        conn.close()
