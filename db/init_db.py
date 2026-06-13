#!/usr/bin/env python3
import os
import sys
import psycopg2

# Adjust path to find config
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
SCHEMA_PATH = os.path.join(SCRIPT_DIR, "schema.sql")

def load_db_config():
    """Loads database config from Streamlit secrets.toml or environment variables."""
    # Attempt to load from Streamlit secrets
    if os.path.exists(SECRETS_PATH):
        try:
            import tomllib
            with open(SECRETS_PATH, "rb") as f:
                config = tomllib.load(f)
                if "postgres" in config:
                    return config["postgres"]
        except Exception as e:
            print(f"Warning: Could not parse {SECRETS_PATH}: {e}")
    
    # Fallback to standard environment variables
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", 5432)),
        "database": os.environ.get("PGDATABASE", "project_elisabeth"),
        "user": os.environ.get("PGUSER", os.environ.get("USER", "")),
        "password": os.environ.get("PGPASSWORD", "")
    }

def init_db():
    config = load_db_config()
    print(f"Connecting to database '{config.get('database')}' on '{config.get('host')}:{config.get('port')}' as user '{config.get('user')}'...")
    
    try:
        conn = psycopg2.connect(
            host=config.get("host"),
            port=config.get("port"),
            dbname=config.get("database"),
            user=config.get("user"),
            password=config.get("password")
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        print(f"Reading schema from {SCHEMA_PATH}...")
        with open(SCHEMA_PATH, "r") as f:
            schema_sql = f.read()
            
        print("Executing schema...")
        cursor.execute(schema_sql)
        print("Database schema successfully initialized!")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    success = init_db()
    sys.exit(0 if success else 1)
