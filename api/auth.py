"""
Verifies the Supabase-issued JWT the frontend sends on authenticated
requests. Newer Supabase projects sign access tokens asymmetrically (ES256,
verified via the project's public JWKS) rather than the legacy shared-secret
HS256 scheme, so this tries JWKS first and falls back to the HS256 secret for
older projects — either way, the backend verifies identity locally without
round-tripping to Supabase on every request.
"""

import os

import jwt
from fastapi import Header, HTTPException

_jwks_client = None


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        supabase_url = os.environ.get("SUPABASE_URL")
        if not supabase_url:
            raise HTTPException(500, "SUPABASE_URL is not set in the environment")
        _jwks_client = jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def get_current_user(authorization: str = Header(default=None)) -> str:
    """FastAPI dependency: returns the Supabase user id (the `sub` claim)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    payload = None
    last_error = None

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(token, signing_key.key, algorithms=["ES256", "RS256"], audience="authenticated")
    except jwt.InvalidTokenError as exc:
        last_error = exc

    if payload is None:
        secret = os.environ.get("SUPABASE_JWT_SECRET")
        if secret:
            try:
                payload = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
            except jwt.InvalidTokenError as exc:
                last_error = exc

    if payload is None:
        raise HTTPException(401, f"Invalid or expired token: {last_error}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Token has no subject")
    return user_id
