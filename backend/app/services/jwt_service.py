import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import jwt
from fastapi import HTTPException, status
from backend.app.core.config import settings, get_jwt_secret
from backend.app.core.logging_config import logger

class JWTService:
    """
    Dedicated cryptographic service for generating and validating short-lived JWT access tokens
    and managing secure opaque refresh tokens.
    """

    @staticmethod
    def create_access_token(
        user_id: str,
        role: str,
        expires_delta: Optional[timedelta] = None
    ) -> tuple[str, str]:
        """
        Creates a signed short-lived JWT access token with minimal necessary claims.
        Returns (token_string, jti).
        """
        now = datetime.now(timezone.utc)
        duration = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire_time = now + duration
        jti = f"jwt_{uuid.uuid4().hex}"

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "role": str(role),
            "type": "access",
            "jti": jti,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(expire_time.timestamp())
        }

        secret = get_jwt_secret()
        token = jwt.encode(payload, secret, algorithm=settings.JWT_ALGORITHM)
        return token, jti

    @staticmethod
    def decode_access_token(token: str) -> dict[str, Any]:
        """
        Decodes and verifies a JWT access token.
        Enforces algorithm whitelist, expiration, and payload structure.
        Raises HTTPException(401) on any failure.
        """
        secret = get_jwt_secret()
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[settings.JWT_ALGORITHM],
                options={"require": ["exp", "sub", "role", "jti", "type"]}
            )
            if payload.get("type") != "access":
                logger.warning(f"Invalid token type presented: {payload.get('type')}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type."
                )
            return payload
        except jwt.ExpiredSignatureError:
            logger.info("Access token signature expired.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token expired. Please refresh token."
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or malformed authentication token."
            )

    @staticmethod
    def generate_refresh_token() -> str:
        """
        Generates a cryptographically random 256-bit opaque refresh token.
        """
        return f"refr_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_token(token: str) -> str:
        """
        Computes SHA-256 hash of opaque token for secure server-side storage.
        """
        return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

jwt_service = JWTService()

