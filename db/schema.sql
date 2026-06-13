-- Anti-Amyloid Tracker Database Schema

-- Enable UUID extension if needed (gen_random_uuid is built-in for pg 13+, but good to have)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop tables if they exist (clean setup)
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS discontinuation_events CASCADE;
DROP TABLE IF EXISTS aria_events CASCADE;
DROP TABLE IF EXISTS mris CASCADE;
DROP TABLE IF EXISTS infusions CASCADE;
DROP TABLE IF EXISTS patients CASCADE;

-- 1. Patients Table
CREATE TABLE patients (
    patient_pk UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mrn TEXT UNIQUE NOT NULL,
    drug TEXT NOT NULL CHECK (drug IN ('lecanemab', 'donanemab')),
    apoe_status TEXT CHECK (apoe_status IN ('non-carrier', 'heterozygote', 'homozygote', 'unknown')),
    baseline_mri_done BOOLEAN NOT NULL DEFAULT FALSE,
    cms_registry_number TEXT,
    infusion_location TEXT CHECK (infusion_location IN ('Talis', 'Vivo', 'UT North')),
    therapy_status TEXT NOT NULL DEFAULT 'continue' CHECK (therapy_status IN ('continue', 'hold', 'discontinue')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_at TIMESTAMP,
    updated_by TEXT,
    CONSTRAINT mrn_format_chk CHECK (mrn ~ '^M00[0-9]{7}$')
);

-- 2. Infusions Table
CREATE TABLE infusions (
    infusion_pk UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_pk UUID NOT NULL REFERENCES patients(patient_pk) ON DELETE CASCADE,
    infusion_number INTEGER NOT NULL,
    infusion_date DATE NOT NULL,
    infusion_reaction BOOLEAN NOT NULL DEFAULT FALSE,
    premedication_reminder BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    UNIQUE (patient_pk, infusion_number),
    UNIQUE (patient_pk, infusion_date)
);

-- 3. MRIs Table
CREATE TABLE mris (
    mri_pk UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_pk UUID NOT NULL REFERENCES patients(patient_pk) ON DELETE CASCADE,
    mri_date DATE NOT NULL,
    mri_type TEXT NOT NULL CHECK (mri_type IN ('scheduled surveillance', 'ARIA follow-up')),
    aria_e_present BOOLEAN,
    aria_h_present BOOLEAN,
    other_findings BOOLEAN,
    other_findings_details TEXT,
    proceed_to_next_infusion BOOLEAN,
    aria_e_status TEXT CHECK (aria_e_status IN ('stable', 'improved', 'worsened', 'resolved')),
    aria_h_status TEXT CHECK (aria_h_status IN ('stable', 'worsened', 'resolved')),
    revert_to_original_mri_schedule BOOLEAN,
    restart_mri_schedule BOOLEAN,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

-- 4. ARIA Events Table
CREATE TABLE aria_events (
    aria_event_pk UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_pk UUID NOT NULL REFERENCES patients(patient_pk) ON DELETE CASCADE,
    aria_date DATE NOT NULL,
    aria_e BOOLEAN,
    aria_h BOOLEAN,
    radiographic_severity TEXT CHECK (radiographic_severity IN ('mild', 'moderate', 'severe')),
    symptom_severity TEXT CHECK (symptom_severity IN ('none', 'mild', 'moderate', 'severe')),
    status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
    therapy_status TEXT NOT NULL CHECK (therapy_status IN ('continue', 'hold', 'discontinue')),
    monthly_mri_required BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

-- 5. Discontinuation Events Table
CREATE TABLE discontinuation_events (
    discontinuation_pk UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_pk UUID NOT NULL REFERENCES patients(patient_pk) ON DELETE CASCADE,
    discontinuation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    reason TEXT NOT NULL CHECK (
        reason IN (
            'stroke',
            'DVT',
            'MI',
            'pulmonary embolism',
            'non-compliance',
            'disease progression',
            'other'
        )
    ),
    other_reason_details TEXT,
    follow_up_mri_required BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

-- 6. Audit Log Table
CREATE TABLE audit_log (
    audit_pk UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name TEXT NOT NULL,
    record_pk TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('insert', 'update', 'delete')),
    changed_by TEXT,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    old_value JSONB,
    new_value JSONB
);

-- Audit Trigger Function
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
        END CASE;
    ELSIF TG_OP = 'DELETE' THEN
        old_val := to_jsonb(OLD);
        CASE tbl_name
            WHEN 'patients' THEN rec_pk := OLD.patient_pk::text;
            WHEN 'infusions' THEN rec_pk := OLD.infusion_pk::text;
            WHEN 'mris' THEN rec_pk := OLD.mri_pk::text;
            WHEN 'aria_events' THEN rec_pk := OLD.aria_event_pk::text;
            WHEN 'discontinuation_events' THEN rec_pk := OLD.discontinuation_pk::text;
        END CASE;
    END IF;

    IF usr IS NULL OR usr = '' THEN
        usr := session_user;
    END IF;

    INSERT INTO audit_log (table_name, record_pk, action, changed_by, old_value, new_value)
    VALUES (tbl_name, rec_pk, lower(act), usr, old_val, new_val);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Bind Audit Triggers to tables
CREATE TRIGGER audit_patients_trigger
AFTER INSERT OR UPDATE OR DELETE ON patients
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_infusions_trigger
AFTER INSERT OR UPDATE OR DELETE ON infusions
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_mris_trigger
AFTER INSERT OR UPDATE OR DELETE ON mris
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_aria_events_trigger
AFTER INSERT OR UPDATE OR DELETE ON aria_events
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_discontinuation_events_trigger
AFTER INSERT OR UPDATE OR DELETE ON discontinuation_events
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
