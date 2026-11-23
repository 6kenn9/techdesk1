from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from ..core.config import GOOGLE_CLIENT_ID

def verify_credential(credential: str) -> dict:
    if not GOOGLE_CLIENT_ID:
        raise ValueError("not configured")
    claims = id_token.verify_oauth2_token(credential, google_requests.Request(), GOOGLE_CLIENT_ID)
    if not claims.get("email") or not claims.get("email_verified"):
        raise ValueError("email is not verified")
    return claims
