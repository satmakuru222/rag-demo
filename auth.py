import os
import secrets
import httpx
import streamlit as st
from jose import jwt

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
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
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()

def _decode_token(id_token: str) -> dict:
    jwks = httpx.get(JWKS_URL, timeout=10).json()
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
        try:
            tokens = _exchange_code(params["code"])
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
            st.error(f"Login failed: {e}")
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
