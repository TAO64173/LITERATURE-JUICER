"""Clerk JWT verification for FastAPI.

Verifies Bearer tokens from the Authorization header using Clerk's JWKS endpoint
or a PEM public key.

Env vars:
  CLERK_JWKS_URL — Clerk's JWKS endpoint (e.g. https://your-app.clerk.accounts.dev/.well-known/jwks.json)
  CLERK_PEM_PUBLIC_KEY — Alternative: PEM-encoded public key string
  CLERK_SECRET_KEY — Clerk secret key for fetching user info (optional, used when email missing from JWT)
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import jwt
import httpx
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

_CLERK_JWKS_URL = os.environ.get("CLERK_JWKS_URL", "")
_CLERK_PEM_PUBLIC_KEY = os.environ.get("CLERK_PEM_PUBLIC_KEY", "")
_CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")


@lru_cache(maxsize=1)
def _fetch_jwks() -> dict:
    """Fetch and cache Clerk's JWKS."""
    if not _CLERK_JWKS_URL:
        raise RuntimeError("CLERK_JWKS_URL not set in environment")
    resp = httpx.get(_CLERK_JWKS_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _get_signing_key(token: str):
    """Get the signing key for a JWT (from JWKS or PEM)."""
    if _CLERK_PEM_PUBLIC_KEY:
        return _CLERK_PEM_PUBLIC_KEY

    jwks = _fetch_jwks()
    unverified = jwt.get_unverified_header(token)
    kid = unverified.get("kid")
    if not kid:
        raise ValueError("Token missing 'kid' header")

    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key)

    raise ValueError(f"No matching key found for kid={kid}")


def _fetch_email_from_clerk(clerk_user_id: str) -> str:
    """Fetch user email from Clerk API when JWT doesn't include it."""
    if not _CLERK_SECRET_KEY:
        logger.warning("[auth] CLERK_SECRET_KEY not set, cannot fetch email for %s", clerk_user_id)
        return ""
    try:
        resp = httpx.get(
            f"https://api.clerk.com/v1/users/{clerk_user_id}",
            headers={
                "Authorization": f"Bearer {_CLERK_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            user_data = resp.json()
            email_addresses = user_data.get("email_addresses", [])
            primary_email_id = user_data.get("primary_email_address_id", "")
            for em in email_addresses:
                if em.get("id") == primary_email_id:
                    return em.get("email_address", "")
            # Fallback to first email
            if email_addresses:
                return email_addresses[0].get("email_address", "")
        else:
            logger.warning("[auth] Clerk API returned %d for user %s", resp.status_code, clerk_user_id)
    except Exception as e:
        logger.warning("[auth] Failed to fetch email from Clerk: %s", e)
    return ""


def verify_clerk_token(request: Request) -> dict:
    """FastAPI dependency: verify Clerk JWT and return the decoded payload.

    The payload['sub'] field is the Clerk user ID (e.g. 'user_2abc123').
    Ensures 'email' field is populated (fetches from Clerk API if missing from JWT).
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("[auth] Missing or invalid Authorization header")
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[7:]

    try:
        key = _get_signing_key(token)
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        logger.warning("[auth] Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning("[auth] Invalid token: %s", e)
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except Exception as e:
        logger.warning("[auth] Auth error: %s", e)
        raise HTTPException(status_code=401, detail=f"Auth error: {e}")

    clerk_user_id = payload.get("sub", "")
    email = payload.get("email", "")

    # Clerk JWT may not include email by default — fetch from API if missing
    if not email and clerk_user_id:
        logger.info("[auth] Email missing from JWT for %s, fetching from Clerk API", clerk_user_id)
        email = _fetch_email_from_clerk(clerk_user_id)
        if email:
            payload["email"] = email
            logger.info("[auth] Got email from Clerk API: %s", email)
        else:
            logger.warning("[auth] Could not determine email for user %s", clerk_user_id)

    logger.info("[auth] Verified user: sub=%s email=%s", clerk_user_id, email)
    return payload
