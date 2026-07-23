import os
import secrets
import httpx
import streamlit as st
from jose import jwt
from dotenv import load_dotenv

load_dotenv()

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "https://localhost:8443")
# Use mkcert root CA so httpx trusts our local SSL cert
_CA_CERT = os.path.join(os.path.dirname(__file__), "certs", "rootCA.pem")
REALM = os.environ.get("KEYCLOAK_REALM", "rag-demo")
CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "rag-app")
CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:8501")

BASE = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect"
AUTH_URL = f"{BASE}/auth"
TOKEN_URL = f"{BASE}/token"
JWKS_URL = f"{BASE}/certs"

def _login_url(state: str) -> str:
    return (
        f"{AUTH_URL}?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid+email+profile"
        f"&state={state}"
    )

def _exchange_code(code: str) -> dict:
    resp = httpx.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, verify=_CA_CERT, timeout=10)
    if resp.status_code != 200:
        raise Exception(f"Token exchange failed ({resp.status_code}): {resp.text}")
    return resp.json()

def _decode_token(id_token: str) -> dict:
    jwks = httpx.get(JWKS_URL, verify=_CA_CERT, timeout=10).json()
    return jwt.decode(
        id_token,
        jwks,
        algorithms=["RS256"],
        audience=CLIENT_ID,
        options={"verify_at_hash": False},
    )

def require_auth() -> dict | None:
    """
    Call at top of app.py. Returns user dict or stops rendering.
    User dict: {id, email, name, roles}
    """
    if st.session_state.get("user"):
        return st.session_state["user"]

    params = st.query_params.to_dict()

    if "code" in params:
        # Guard: only exchange a code once — Keycloak invalidates after first use
        code = params["code"]
        if st.session_state.get("_exchanged_code") == code:
            st.error("Auth code already used. Click below to log in again.")
            state = secrets.token_urlsafe(16)
            st.markdown(f"[**Sign in again →**]({_login_url(state)})")
            st.stop()
            return None
        st.session_state["_exchanged_code"] = code
        try:
            tokens = _exchange_code(code)
            claims = _decode_token(tokens["id_token"])
            user = {
                "id": claims["sub"],
                "email": claims.get("email", ""),
                "name": claims.get("name", claims.get("preferred_username", "")),
                "roles": claims.get("realm_access", {}).get("roles", []),
            }
            st.session_state["user"] = user
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.session_state.pop("_exchanged_code", None)
            st.error(f"Login failed: {e}")
            state = secrets.token_urlsafe(16)
            st.markdown(f"[**Try logging in again →**]({_login_url(state)})")
            st.stop()
        return None

    state = secrets.token_urlsafe(16)
    st.session_state["oauth_state"] = state
    st.markdown("## 🔐 Sign in to continue")
    st.markdown(f"[**Sign in with your company account →**]({_login_url(state)})")
    st.stop()
    return None

def logout():
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()
