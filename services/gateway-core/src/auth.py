"""
JWT Authentication and Authorization Module

Implements Zero Trust authentication using JWT tokens with
role-based access control (RBAC) for tactical operations.
"""

import os
from dataclasses import dataclass

from fastapi import HTTPException, Header, Depends
from jose import jwt, JWTError
import structlog

logger = structlog.get_logger()

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "development-secret-change-in-production")
JWT_ALGORITHM = "HS256"

# Role-Permission Mapping
ROLE_PERMISSIONS = {
    "operator": ["message:send", "message:read", "node:status"],
    "supervisor": ["message:send", "message:read", "message:delete", "node:status", "audit:read"],
    "admin": ["message:send", "message:read", "message:delete", "node:status", "node:manage", "config:write", "audit:read", "audit:export"],
    "service": ["message:send", "message:read", "node:status", "internal:call"]
}


@dataclass
class JWTClaims:
    """Validated JWT claims."""
    subject: str
    node_id: str
    role: str
    permissions: list[str]
    classification_level: str
    raw_token: str


def verify_jwt(authorization: str = Header(None)) -> JWTClaims:
    """
    Verify and decode JWT token from Authorization header.

    Implements NIST 800-53 IA-2 (Identification and Authentication)
    """
    if not authorization:
        logger.warning("Missing authorization header")
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Authorization header required"
                }
            }
        )

    # Extract token from Bearer scheme
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning("Invalid authorization format")
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Invalid authorization header format. Use 'Bearer <token>'"
                }
            }
        )

    token = parts[1]

    try:
        # Decode and verify JWT
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require_exp": True, "require_sub": True, "verify_aud": False}
        )

        # Extract claims
        subject = payload.get("sub")
        node_id = payload.get("node_id", subject)
        role = payload.get("role", "operator")
        classification_level = payload.get("classification_level", "UNCLASSIFIED")

        # Get permissions from role
        permissions = ROLE_PERMISSIONS.get(role, [])

        # Override with explicit permissions if provided
        if "permissions" in payload:
            permissions = payload["permissions"]

        logger.info(
            "JWT validated",
            subject=subject,
            node_id=node_id,
            role=role
        )

        return JWTClaims(
            subject=subject,
            node_id=node_id,
            role=role,
            permissions=permissions,
            classification_level=classification_level,
            raw_token=token
        )

    except JWTError as e:
        logger.warning("JWT validation failed", error=str(e))
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": f"Token validation failed: {str(e)}"
                }
            }
        )


def require_permission(permission: str):
    """
    Dependency that requires a specific permission.

    Implements NIST 800-53 AC-3 (Access Enforcement)

    Usage:
        @app.get("/endpoint")
        async def endpoint(claims: JWTClaims = Depends(require_permission("message:send"))):
            ...
    """
    def permission_checker(claims: JWTClaims = Depends(verify_jwt)) -> JWTClaims:
        if permission not in claims.permissions:
            logger.warning(
                "Permission denied",
                subject=claims.subject,
                required=permission,
                granted=claims.permissions
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": f"Permission '{permission}' required"
                    }
                }
            )
        return claims

    return permission_checker


def require_classification(level: str):
    """
    Dependency that requires a minimum classification level.

    Classification hierarchy: UNCLASSIFIED < CONFIDENTIAL < SECRET < TOP_SECRET
    """
    classification_hierarchy = {
        "UNCLASSIFIED": 0,
        "CONFIDENTIAL": 1,
        "SECRET": 2,
        "TOP_SECRET": 3
    }

    def classification_checker(claims: JWTClaims = Depends(verify_jwt)) -> JWTClaims:
        user_level = classification_hierarchy.get(claims.classification_level, 0)
        required_level = classification_hierarchy.get(level, 0)

        if user_level < required_level:
            logger.warning(
                "Classification level insufficient",
                subject=claims.subject,
                required=level,
                user_level=claims.classification_level
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": f"Classification level '{level}' required"
                    }
                }
            )
        return claims

    return classification_checker
