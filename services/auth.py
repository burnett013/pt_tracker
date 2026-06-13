import streamlit as st

def get_logged_in_user() -> dict:
    """
    Returns the authenticated user details from headers if present,
    or a default Demo User fallback to support write audits.
    """
    headers = st.context.headers
    
    # Try reading Connect headers
    email = headers.get("X-Auth-Email") or headers.get("x-auth-email")
    username = headers.get("X-Auth-User") or headers.get("x-auth-user")
    name = headers.get("X-Auth-Name") or headers.get("x-auth-name")
    
    if email or username or name:
        return {
            "email": email or "",
            "username": username or email or "",
            "name": name or username or email or "Demo User",
            "is_mock": False
        }
    
    # Simple demo fallback
    return {
        "email": "demo.user@example.com",
        "username": "demo_user",
        "name": "Demo User",
        "is_mock": True
    }

def render_auth_sidebar():
    """Renders a simplified session label in the sidebar for the demo."""
    user = get_logged_in_user()
    st.sidebar.markdown("---")
    st.sidebar.subheader("Session & Auditing")
    st.sidebar.info(f"👤 Active: {user['name']} ({user['email']})")

def verify_access():
    """Bypassed for demonstration purposes. Allows unrestricted access."""
    pass
