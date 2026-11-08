import os
import streamlit as st

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")


def ensure_posit_secrets_file():
    """
    On Posit Connect Cloud, `.streamlit/secrets.toml` is not in GitHub (.gitignore).
    If `ENTRA_CLIENT_ID` and `ENTRA_CLIENT_SECRET` are set in Posit Environment Variables
    and `.streamlit/secrets.toml` does not exist yet, this automatically generates
    `.streamlit/secrets.toml` at startup so Streamlit's native `st.login()` works seamlessly!
    """
    if os.path.exists(SECRETS_PATH):
        return

    client_id = os.environ.get("ENTRA_CLIENT_ID", "")
    client_secret = os.environ.get("ENTRA_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return

    redirect_uri = os.environ.get(
        "ENTRA_REDIRECT_URI",
        "https://burnett013-patienttracker.share.connect.posit.cloud/oauth2callback",
    )
    cookie_secret = os.environ.get(
        "ENTRA_COOKIE_SECRET",
        "f8d9a2c4b6e109384756a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5a",
    )
    server_metadata_url = os.environ.get(
        "ENTRA_SERVER_METADATA_URL",
        "https://login.microsoftonline.com/consumers/v2.0/.well-known/openid-configuration",
    )

    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    with open(SECRETS_PATH, "w") as f:
        f.write(
            f'[auth]\n'
            f'redirect_uri = "{redirect_uri}"\n'
            f'cookie_secret = "{cookie_secret}"\n'
            f'client_id = "{client_id}"\n'
            f'client_secret = "{client_secret}"\n'
            f'server_metadata_url = "{server_metadata_url}"\n'
        )


def load_auth_config() -> dict:
    """Loads [auth] config from .streamlit/secrets.toml or Posit environment variables."""
    ensure_posit_secrets_file()
    try:
        if "auth" in st.secrets:
            return dict(st.secrets["auth"])
    except Exception:
        pass

    if os.path.exists(SECRETS_PATH):
        try:
            import tomllib
            with open(SECRETS_PATH, "rb") as f:
                config = tomllib.load(f)
                if "auth" in config:
                    return config["auth"]
        except Exception:
            pass

    return {}


def is_entra_configured(config: dict) -> bool:
    """Checks whether Entra ID credentials are configured under [auth] in secrets.toml."""
    placeholders = {"", "xxx", "YOUR_CLIENT_ID_HERE", "YOUR_CLIENT_SECRET_HERE"}
    return (
        config.get("client_id", "") not in placeholders
        and config.get("client_secret", "") not in placeholders
        and bool(config.get("server_metadata_url", ""))
    )


def get_logged_in_user() -> dict | None:
    """
    Returns the authenticated user details from:
      1. Official Streamlit Native Auth (`st.user.is_logged_in` via Microsoft Entra ID)
      2. Reverse-proxy headers if deployed behind an enterprise auth proxy
      3. None if not logged in
    """
    ensure_posit_secrets_file()

    # 1. Official Streamlit Native Auth (`st.login` / `st.user`)
    if getattr(st.user, "is_logged_in", False):
        claims = st.user.to_dict() if hasattr(st.user, "to_dict") else dict(st.user)
        email = (
            claims.get("email")
            or claims.get("preferred_username")
            or claims.get("upn")
            or "unknown@microsoft.com"
        )
        name = claims.get("name") or email
        return {
            "email": email,
            "username": email,
            "name": name,
            "oid": claims.get("oid") or claims.get("sub", "N/A"),
            "is_mock": False,
            "raw_claims": claims,
        }

    # 2. Reverse-proxy headers (e.g. enterprise Posit Connect or Azure App Service EasyAuth)
    headers = st.context.headers
    email = (
        headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
        or headers.get("X-Auth-Email")
        or headers.get("x-auth-email")
    )
    username = headers.get("X-Auth-User") or headers.get("x-auth-user")
    name = headers.get("X-Auth-Name") or headers.get("x-auth-name")

    if email or username or name:
        resolved_email = email or username or ""
        return {
            "email": resolved_email,
            "username": username or resolved_email,
            "name": name or username or resolved_email,
            "oid": headers.get("X-MS-CLIENT-PRINCIPAL-ID", "proxy"),
            "is_mock": False,
            "raw_claims": dict(headers),
        }

    return None


def render_auth_sidebar():
    """Renders the logged-in user badge and Log out button in the sidebar."""
    user = get_logged_in_user()
    if not user:
        return

    st.sidebar.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.sidebar.markdown("##### 🔐 Active Clinical Session")
    st.sidebar.info(f"👤 **{user['name']}**  \n`{user['email']}`")
    if getattr(st.user, "is_logged_in", False):
        st.sidebar.button("🚪 Log out", on_click=st.logout, use_container_width=True)


def verify_access() -> dict:
    """
    Enforces Microsoft Entra ID login across all pages of the Anti-Amyloid Tracker,
    renders the session badge in the sidebar, and returns the logged-in `user` dict.
    """
    ensure_posit_secrets_file()
    user = get_logged_in_user()
    if user:
        render_auth_sidebar()
        return user

    config = load_auth_config()
    st.title("🧬 Anti-Amyloid Patient Tracking System")
    st.subheader("🔒 Clinical Sign-In Required")
    st.markdown(
        "Please sign in with your authorized **Microsoft Entra ID** account to access the "
        "Anti-Amyloid Patient Tracking System. All creations, updates, and deletions are "
        "automatically logged in the audit trail under your authenticated email."
    )

    if is_entra_configured(config):
        st.button(
            "🔑 Log in with Microsoft",
            on_click=st.login,
            type="primary",
        )
    else:
        st.error(
            "Microsoft Entra ID is not configured yet. On Posit Connect Cloud, add "
            "`ENTRA_CLIENT_ID` and `ENTRA_CLIENT_SECRET` in your Posit Content Settings → Variables."
        )

    st.stop()
