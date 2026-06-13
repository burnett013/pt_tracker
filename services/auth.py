import streamlit as st

def get_logged_in_user() -> dict:
    """
    Extracts the authenticated user details from Posit Connect request headers.
    Posit Connect populates these headers when configured with Microsoft Entra ID or other OIDC providers.
    Falls back to a configurable mock user during local development.
    """
    headers = st.context.headers
    
    # Check Posit Connect headers (both standard and lowercase casing)
    email = headers.get("X-Auth-Email") or headers.get("x-auth-email")
    username = headers.get("X-Auth-User") or headers.get("x-auth-user")
    name = headers.get("X-Auth-Name") or headers.get("x-auth-name")
    
    if email or username or name:
        return {
            "email": email or "",
            "username": username or email or "",
            "name": name or username or email or "Authenticated User",
            "is_mock": False
        }
    
    # Local fallback logic
    # Check if developer defined mock credentials in st.secrets
    mock_email = "local.dev@example.com"
    mock_name = "Local Developer"
    
    if "auth" in st.secrets:
        mock_email = st.secrets["auth"].get("mock_email", mock_email)
        mock_name = st.secrets["auth"].get("mock_name", mock_name)
        
    # We can also store the selected mock user in st.session_state if they override it in the UI
    if "dev_user_email" in st.session_state and st.session_state["dev_user_email"]:
        mock_email = st.session_state["dev_user_email"]
        mock_name = st.session_state.get("dev_user_name", "Local Dev User")
        
    return {
        "email": mock_email,
        "username": mock_email.split("@")[0],
        "name": mock_name,
        "is_mock": True
    }

def render_auth_sidebar():
    """Renders the authentication status in the sidebar, including a dev-override selector if in local dev mode."""
    user = get_logged_in_user()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Security & Session")
    
    if not user["is_mock"]:
        st.sidebar.success(f"🔒 Authenticated (Entra ID)")
        st.sidebar.text(f"User: {user['name']}")
        st.sidebar.text(f"Email: {user['email']}")
    else:
        st.sidebar.warning(f"🛠️ Dev Mode (No Headers)")
        
        # Interactive mock user switcher for testing
        mock_users = {
            "Dr. Sarah Jenkins (s.jenkins@clinic.org)": ("s.jenkins@clinic.org", "Dr. Sarah Jenkins"),
            "Nurse Alex Rivera (a.rivera@clinic.org)": ("a.rivera@clinic.org", "Nurse Alex Rivera"),
            "Local Developer (local.dev@example.com)": ("local.dev@example.com", "Local Developer"),
        }
        
        selected_label = st.sidebar.selectbox(
            "Simulate User for Auditing:",
            options=list(mock_users.keys()),
            index=2 # Defaults to Local Developer
        )
        
        email, name = mock_users[selected_label]
        st.session_state["dev_user_email"] = email
        st.session_state["dev_user_name"] = name
        
        # Checkbox to simulate membership in the approved group
        sim_approved = st.sidebar.checkbox(
            "Simulate 'approved_users' group",
            value=st.session_state.get("dev_user_approved", True),
            help="Uncheck this to test the Access Denied screen locally."
        )
        st.session_state["dev_user_approved"] = sim_approved
        
        st.sidebar.caption("Audit logs will record operations under this user.")

def verify_access():
    """
    Verifies if the current authenticated user belongs to the 'approved_users' group.
    Halts Streamlit page execution and shows an Access Denied message if unauthorized.
    """
    user = get_logged_in_user()
    
    # In Posit Connect, groups are passed in the 'X-Auth-Groups' header (comma-separated list)
    headers = st.context.headers
    raw_groups = headers.get("X-Auth-Groups") or headers.get("x-auth-groups") or ""
    
    # Clean the groups list (lowercase for comparison)
    user_groups = [g.strip().lower() for g in raw_groups.split(",") if g.strip()]
    
    # Local fallback logic for developers
    if user.get("is_mock"):
        # Retrieve the checkbox status from session state (defaults to True)
        if st.session_state.get("dev_user_approved", True):
            user_groups.append("approved_users")
            
    if "approved_users" not in user_groups:
        st.markdown("""
        <div style="padding: 2rem; background-color: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 8px; margin-top: 2rem;">
            <h2 style="color: #ef4444; margin-top: 0; font-weight: 700;">⛔ Access Denied</h2>
            <p>You do not have permission to view the <strong>Anti-Amyloid Patient Tracking App</strong>.</p>
            <p>Your user account must be a member of the <strong>approved_users</strong> security group in Microsoft Entra ID.</p>
            <hr style="border: 0; border-top: 1px solid rgba(239, 68, 68, 0.2); margin: 1.5rem 0;" />
            <p style="font-size: 0.85rem; opacity: 0.8;">If you believe this is an error, please contact your clinical IT administrator or study coordinator.</p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()
