import os
import streamlit as st
import msal

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
SCOPES = ["User.Read"]


def load_auth_config() -> dict:
    """
    Loads Microsoft Entra ID config from `.streamlit/secrets.toml` (`[auth]`)
    or from Posit Connect Cloud environment variables (`ENTRA_CLIENT_ID`, etc.).
    """
    config = {}

    if os.path.exists(SECRETS_PATH):
        try:
            import tomllib
            with open(SECRETS_PATH, "rb") as f:
                parsed = tomllib.load(f)
                if "auth" in parsed:
                    config.update(parsed["auth"])
        except Exception:
            pass

    try:
        if "auth" in st.secrets:
            config.update(dict(st.secrets["auth"]))
    except Exception:
        pass

    # Overlay Posit Connect Cloud environment variables if present
    if os.environ.get("ENTRA_CLIENT_ID"):
        config["client_id"] = os.environ["ENTRA_CLIENT_ID"]
    if os.environ.get("ENTRA_CLIENT_SECRET"):
        config["client_secret"] = os.environ["ENTRA_CLIENT_SECRET"]

    # Determine redirect_uri automatically based on whether we are on Posit Cloud or localhost
    if os.environ.get("ENTRA_REDIRECT_URI"):
        config["redirect_uri"] = os.environ["ENTRA_REDIRECT_URI"]
    elif os.environ.get("ENTRA_CLIENT_ID") and not os.path.exists(SECRETS_PATH):
        # Running on Posit Connect Cloud (must use root URL because Posit's Envoy proxy redirects /oauth2callback to / and drops query params)
        config["redirect_uri"] = "https://burnett013-patienttracker.share.connect.posit.cloud/"
    elif "redirect_uri" not in config:
        config["redirect_uri"] = "http://localhost:8501/oauth2callback"

    if "server_metadata_url" not in config:
        config["server_metadata_url"] = os.environ.get(
            "ENTRA_SERVER_METADATA_URL",
            "https://login.microsoftonline.com/consumers/v2.0/.well-known/openid-configuration",
        )

    return config


def is_entra_configured(config: dict) -> bool:
    """Checks whether Entra ID credentials are configured."""
    placeholders = {"", "xxx", "YOUR_CLIENT_ID_HERE", "YOUR_CLIENT_SECRET_HERE"}
    return (
        config.get("client_id", "") not in placeholders
        and config.get("client_secret", "") not in placeholders
    )


def _get_authority_from_metadata_url(metadata_url: str) -> str:
    """Extracts the MSAL authority URL from the OpenID Connect metadata document URL."""
    if "/v2.0/.well-known/openid-configuration" in metadata_url:
        return metadata_url.split("/v2.0/.well-known/openid-configuration")[0]
    return "https://login.microsoftonline.com/consumers"


def _build_msal_app(config: dict) -> msal.ConfidentialClientApplication:
    authority = _get_authority_from_metadata_url(config.get("server_metadata_url", ""))
    return msal.ConfidentialClientApplication(
        client_id=config["client_id"],
        client_credential=config["client_secret"],
        authority=authority,
    )


def handle_oauth_callback(config: dict):
    """
    Handles the OAuth2 redirect (`?code=...`) from Microsoft Entra ID on both
    localhost and Posit Connect Cloud without relying on server startup files.
    """
    query_params = st.query_params
    if "error" in query_params:
        st.error(
            f"**Microsoft Sign-In Error (`{query_params.get('error')}`):** "
            f"{query_params.get('error_description', '')}"
        )
        st.query_params.clear()
        return

    if "code" in query_params and "entra_user" not in st.session_state:
        auth_code = query_params["code"]
        st.query_params.clear()

        if not is_entra_configured(config):
            return

        with st.spinner("Signing you in with Microsoft Entra ID..."):
            msal_app = _build_msal_app(config)
            result = msal_app.acquire_token_by_authorization_code(
                code=auth_code,
                scopes=SCOPES,
                redirect_uri=config["redirect_uri"],
            )

        if "id_token_claims" in result:
            claims = result["id_token_claims"]
            email = (
                claims.get("email")
                or claims.get("preferred_username")
                or claims.get("upn")
                or "unknown@microsoft.com"
            )
            name = claims.get("name") or email
            st.session_state["entra_user"] = {
                "email": email,
                "username": email,
                "name": name,
                "oid": claims.get("oid") or claims.get("sub", "N/A"),
                "is_mock": False,
                "raw_claims": claims,
            }
            st.rerun()
        else:
            err = result.get("error", "Unknown Error")
            desc = result.get("error_description", str(result))
            st.error(f"**Microsoft Token Exchange Failed (`{err}`):**\n\n{desc}")


def get_logged_in_user() -> dict | None:
    """
    Returns the authenticated user details from:
      1. Active MSAL Entra ID session (`st.session_state["entra_user"]`)
      2. Official Streamlit Native Auth (`st.user.is_logged_in`)
      3. Reverse-proxy headers if deployed behind an enterprise auth proxy
    """
    if "entra_user" in st.session_state:
        return st.session_state["entra_user"]

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


def logout():
    """Logs the user out of the session."""
    st.session_state.pop("entra_user", None)
    if getattr(st.user, "is_logged_in", False):
        st.logout()
    else:
        st.rerun()


def render_auth_sidebar():
    """Renders the logged-in user badge and Log out button in the sidebar."""
    user = get_logged_in_user()
    if not user:
        return

    st.sidebar.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.sidebar.markdown("##### 🔐 Active Clinical Session")
    st.sidebar.info(f"👤 **{user['name']}**  \n`{user['email']}`")
    if st.sidebar.button("🚪 Log out", use_container_width=True):
        logout()


def verify_access() -> dict:
    """
    Enforces Microsoft Entra ID login across all pages of the Anti-Amyloid Tracker,
    renders the session badge in the sidebar, and returns the logged-in `user` dict.
    """
    config = load_auth_config()
    handle_oauth_callback(config)

    user = get_logged_in_user()
    if user:
        render_auth_sidebar()
        return user

    st.title("🧬 Anti-Amyloid Patient Tracking System")
    st.subheader("🔒 Clinical Sign-In Required")
    st.markdown(
        "Please sign in with your authorized **Microsoft Entra ID** account to access the "
        "Anti-Amyloid Patient Tracking System. All creations, updates, and deletions are "
        "automatically logged in the audit trail under your authenticated email."
    )

    if is_entra_configured(config):
        if os.path.exists(SECRETS_PATH):
            st.button(
                "🔑 Log in with Microsoft",
                on_click=st.login,
                type="primary",
            )
        else:
            msal_app = _build_msal_app(config)
            auth_url = msal_app.get_authorization_request_url(
                scopes=SCOPES,
                redirect_uri=config["redirect_uri"],
                prompt="select_account",
            )
            st.link_button(
                "🔑 Log in with Microsoft",
                url=auth_url,
                type="primary",
            )
    else:
        st.error(
            "Microsoft Entra ID is not configured yet. On Posit Connect Cloud, add "
            "`ENTRA_CLIENT_ID` and `ENTRA_CLIENT_SECRET` in your Posit Content Settings → Variables."
        )

    st.stop()
