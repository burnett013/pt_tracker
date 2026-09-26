import os
import psycopg2
import psycopg2.extras
import streamlit as st

# Path configuration for loading secrets locally
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")

def load_db_config():
    """Loads database config from Streamlit secrets.toml or environment variables."""
    # Attempt to load from Streamlit secrets (which are parsed by Streamlit automatically in st.secrets)
    try:
        if "postgres" in st.secrets:
            return st.secrets["postgres"]
    except Exception:
        # No secrets.toml found — fall through to env vars
        pass
        
    # Manual parsing of secrets.toml if st.secrets is not populated (e.g. CLI run of sub-scripts)
    if os.path.exists(SECRETS_PATH):
        try:
            import tomllib
            with open(SECRETS_PATH, "rb") as f:
                config = tomllib.load(f)
                if "postgres" in config:
                    return config["postgres"]
        except Exception:
            pass

    # Fallback to standard environment variables
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

def execute_transaction(queries_with_params, user_email="system"):
    """
    Executes multiple SQL operations inside a single database transaction.
    Sets the session variable 'app.current_user' so audit triggers capture the username.
    
    queries_with_params: list of tuples (sql_query_string, parameters_tuple)
    Returns: The output of the last query executed, if any.
    """
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            # Set the user context for triggers
            cur.execute('SET LOCAL "app.current_user" = %s;', (user_email,))
            
            last_result = None
            for query, params in queries_with_params:
                cur.execute(query, params)
                try:
                    if cur.description:
                        last_result = cur.fetchall()
                except psycopg2.ProgrammingError:
                    # Query doesn't return results
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
    This runs a single optimized JOIN query suitable for feeding the dashboard and lookup logic.
    """
    sql = """
    WITH latest_infusion AS (
        SELECT DISTINCT ON (patient_pk) *
        FROM infusions
        ORDER BY patient_pk, infusion_number DESC, infusion_date DESC
    ),
    reaction_summary AS (
        SELECT patient_pk, bool_or(reaction_severity != 'none') as has_prior_reaction
        FROM infusions
        GROUP BY patient_pk
    ),
    latest_mri AS (
        SELECT DISTINCT ON (patient_pk) *
        FROM mris
        ORDER BY patient_pk, mri_date DESC, created_at DESC
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
        COALESCE(r.has_prior_reaction, FALSE) as has_prior_reaction,
        m.mri_date as last_mri_date,
        m.mri_type as last_mri_type,
        m.proceed_to_next_infusion as last_mri_proceed,
        a.aria_date as last_aria_date,
        a.status as last_aria_status,
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
    LEFT JOIN reaction_summary r ON p.patient_pk = r.patient_pk
    LEFT JOIN latest_mri m ON p.patient_pk = m.patient_pk
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
            results = cur.fetchall()
            return results
    finally:
        conn.close()

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

def record_infusion(patient_pk, infusion_number, infusion_date, reaction_severity, premedication_reminder, notes, user_email):
    """Records a patient infusion event with reaction severity rating."""
    query = """
    INSERT INTO infusions (patient_pk, infusion_number, infusion_date, reaction_severity, premedication_reminder, notes, created_by)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING infusion_pk;
    """
    params = (patient_pk, infusion_number, infusion_date, reaction_severity, premedication_reminder, notes, user_email)
    res = execute_transaction([(query, params)], user_email)
    return res[0][0] if res else None

def record_mri(patient_pk, mri_date, mri_type, no_aria_confirmed, aria_e_present, aria_h_present, other_findings, 
               other_findings_details, proceed_to_next_infusion, aria_e_status, aria_h_status, 
               revert_to_original_mri_schedule, restart_mri_schedule, unscheduled_reason, notes, user_email):
    """Records an MRI scan event with support for no-ARIA confirmation and unscheduled surveillance."""
    
    queries = []
    
    # Insert the MRI record
    mri_query = """
    INSERT INTO mris (
        patient_pk, mri_date, mri_type, no_aria_confirmed, aria_e_present, aria_h_present, other_findings, 
        other_findings_details, proceed_to_next_infusion, aria_e_status, aria_h_status, 
        revert_to_original_mri_schedule, restart_mri_schedule, unscheduled_reason, notes, created_by
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING mri_pk;
    """
    mri_params = (
        patient_pk, mri_date, mri_type, no_aria_confirmed, aria_e_present, aria_h_present, other_findings,
        other_findings_details, proceed_to_next_infusion, aria_e_status, aria_h_status,
        revert_to_original_mri_schedule, restart_mri_schedule, unscheduled_reason, notes, user_email
    )
    queries.append((mri_query, mri_params))
    
    # If proceed to next infusion is False, we might want to put the patient on therapy hold automatically!
    # If proceed to next infusion is True, and they were on hold, we can check if they revert to continue.
    if proceed_to_next_infusion is False:
        update_patient_query = "UPDATE patients SET therapy_status = 'hold', updated_by = %s, updated_at = CURRENT_TIMESTAMP WHERE patient_pk = %s;"
        queries.append((update_patient_query, (user_email, patient_pk)))
        
    res = execute_transaction(queries, user_email)
    return res[0][0] if res else None

def record_aria_event(patient_pk, aria_date, aria_e, aria_h, radiographic_severity_e, radiographic_severity_h,
                      symptom_severity, status, therapy_status, monthly_mri_required, notes, user_email):
    """Records an ARIA event with separate E/H radiographic severities and updates the patient's overall therapy status."""
    queries = []
    
    # Insert the ARIA event
    aria_query = """
    INSERT INTO aria_events (
        patient_pk, aria_date, aria_e, aria_h, radiographic_severity_e, radiographic_severity_h,
        symptom_severity, status, therapy_status, monthly_mri_required, notes, created_by
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING aria_event_pk;
    """
    aria_params = (
        patient_pk, aria_date, aria_e, aria_h, radiographic_severity_e, radiographic_severity_h,
        symptom_severity, status, therapy_status, monthly_mri_required, notes, user_email
    )
    queries.append((aria_query, aria_params))
    
    # Update patient therapy status
    update_patient_query = """
    UPDATE patients 
    SET therapy_status = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP 
    WHERE patient_pk = %s;
    """
    queries.append((update_patient_query, (therapy_status, user_email, patient_pk)))
    
    res = execute_transaction(queries, user_email)
    return res[0][0] if res else None

def record_discontinuation(patient_pk, discontinuation_date, reason, other_reason_details, follow_up_mri_required, notes, user_email):
    """Records a patient's discontinuation of therapy and updates their status in the patients table."""
    queries = []
    
    # Insert discontinuation record
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
    
    # Update patient status to discontinue and set active = FALSE
    update_patient_query = """
    UPDATE patients 
    SET therapy_status = 'discontinue', active = FALSE, updated_by = %s, updated_at = CURRENT_TIMESTAMP 
    WHERE patient_pk = %s;
    """
    queries.append((update_patient_query, (user_email, patient_pk)))
    
    res = execute_transaction(queries, user_email)
    return res[0][0] if res else None

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
        # Automatically mark parent call as confirmed
        update_parent_query = """
        UPDATE phone_calls
        SET follow_up_confirmed = TRUE
        WHERE phone_call_pk = %s;
        """
        queries.append((update_parent_query, (parent_call_pk,)))
        
    res = execute_transaction(queries, user_email)
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
    Retrieves the complete historical timelines for a patient across all tracking events.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Get infusions
            cur.execute("""
                SELECT infusion_pk, infusion_number, infusion_date, reaction_severity, premedication_reminder, notes, created_at, created_by
                FROM infusions WHERE patient_pk = %s ORDER BY infusion_number DESC, infusion_date DESC;
            """, (patient_pk,))
            infusions = cur.fetchall()
            
            # 2. Get MRIs
            cur.execute("""
                SELECT mri_pk, mri_date, mri_type, no_aria_confirmed, aria_e_present, aria_h_present, other_findings, 
                       other_findings_details, proceed_to_next_infusion, aria_e_status, aria_h_status, 
                       revert_to_original_mri_schedule, restart_mri_schedule, unscheduled_reason, notes, created_at, created_by
                FROM mris WHERE patient_pk = %s ORDER BY mri_date DESC, created_at DESC;
            """, (patient_pk,))
            mris = cur.fetchall()
            
            # 3. Get ARIA events
            cur.execute("""
                SELECT aria_event_pk, aria_date, aria_e, aria_h, radiographic_severity_e, radiographic_severity_h, 
                       symptom_severity, status, therapy_status, monthly_mri_required, notes, created_at, created_by
                FROM aria_events WHERE patient_pk = %s ORDER BY aria_date DESC, created_at DESC;
            """, (patient_pk,))
            arias = cur.fetchall()
            
            # 4. Get discontinuation events
            cur.execute("""
                SELECT discontinuation_pk, discontinuation_date, reason, other_reason_details, follow_up_mri_required, notes, created_at, created_by
                FROM discontinuation_events WHERE patient_pk = %s ORDER BY discontinuation_date DESC, created_at DESC;
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
            
            # 6. Get audit logs
            cur.execute("""
                SELECT audit_pk, table_name, record_pk, action, changed_by, changed_at, old_value, new_value
                FROM audit_log
                WHERE (table_name = 'patients' AND record_pk = %s)
                   OR (table_name = 'infusions' AND record_pk IN (SELECT infusion_pk::text FROM infusions WHERE patient_pk = %s))
                   OR (table_name = 'mris' AND record_pk IN (SELECT mri_pk::text FROM mris WHERE patient_pk = %s))
                   OR (table_name = 'aria_events' AND record_pk IN (SELECT aria_event_pk::text FROM aria_events WHERE patient_pk = %s))
                   OR (table_name = 'discontinuation_events' AND record_pk IN (SELECT discontinuation_pk::text FROM discontinuation_events WHERE patient_pk = %s))
                   OR (table_name = 'phone_calls' AND record_pk IN (SELECT phone_call_pk::text FROM phone_calls WHERE patient_pk = %s))
                ORDER BY changed_at DESC;
            """, (str(patient_pk), patient_pk, patient_pk, patient_pk, patient_pk, patient_pk))
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

def update_therapy_status(patient_pk, therapy_status, user_email):
    """Directly updates a patient's therapy status (e.g. from hold to continue)."""
    query = """
    UPDATE patients 
    SET therapy_status = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP 
    WHERE patient_pk = %s;
    """
    params = (therapy_status, user_email, patient_pk)
    execute_transaction([(query, params)], user_email)
