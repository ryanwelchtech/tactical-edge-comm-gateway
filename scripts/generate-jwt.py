#!/usr/bin/env python3
"""
JWT Token Generator for TacEdge Gateway

Generates JWT tokens for testing and development.
"""

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta

try:
    from jose import jwt
except ImportError:
    print("Error: python-jose not installed. Run: pip install python-jose[cryptography]")
    sys.exit(1)

# Default secret (override with JWT_SECRET env var)
DEFAULT_SECRET = "development-secret-change-in-production"

# Role-Permission Mapping
ROLE_PERMISSIONS = {
    "operator": ["message:send", "message:read", "node:status"],
    "supervisor": ["message:send", "message:read", "message:delete", "node:status", "audit:read"],
    "admin": ["message:send", "message:read", "message:delete", "node:status", "node:manage", "config:write", "audit:read", "audit:export"],
    "service": ["message:send", "message:read", "node:status", "internal:call"]
}


def generate_token(
    node_id: str,
    role: str,
    secret: str,
    expiry_hours: int = 24,
    classification: str = "UNCLASSIFIED"
) -> str:
    """
    Generate a JWT token for TacEdge Gateway.
    
    Args:
        node_id: Node identifier (e.g., NODE-ALPHA)
        role: User role (operator, supervisor, admin, service)
        secret: JWT signing secret
        expiry_hours: Token validity in hours
        classification: Classification level
    
    Returns:
        Encoded JWT token string
    """
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(hours=expiry_hours)
    
    permissions = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["operator"])
    
    payload = {
        "iss": "tacedge-gateway",
        "sub": node_id,
        "aud": "tacedge-services",
        "exp": int(expiry.timestamp()),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "jti": f"token-{now.strftime('%Y%m%d%H%M%S')}",
        "role": role,
        "permissions": permissions,
        "node_id": node_id,
        "classification_level": classification
    }
    
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict:
    """Decode and display token contents."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Generate JWT tokens for TacEdge Gateway"
    )
    parser.add_argument(
        "--node", "-n",
        default="NODE-ALPHA",
        help="Node identifier (default: NODE-ALPHA)"
    )
    parser.add_argument(
        "--role", "-r",
        choices=["operator", "supervisor", "admin", "service"],
        default="operator",
        help="User role (default: operator)"
    )
    parser.add_argument(
        "--expiry", "-e",
        type=int,
        default=24,
        help="Token validity in hours (default: 24)"
    )
    parser.add_argument(
        "--classification", "-c",
        choices=["UNCLASSIFIED", "CONFIDENTIAL", "SECRET", "TOP_SECRET"],
        default="UNCLASSIFIED",
        help="Classification level (default: UNCLASSIFIED)"
    )
    parser.add_argument(
        "--secret", "-s",
        default=os.getenv("JWT_SECRET", DEFAULT_SECRET),
        help="JWT signing secret (default: from JWT_SECRET env var)"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Show decoded token contents"
    )
    
    args = parser.parse_args()
    
    # Generate token
    token = generate_token(
        node_id=args.node,
        role=args.role,
        secret=args.secret,
        expiry_hours=args.expiry,
        classification=args.classification
    )
    
    print("\n" + "=" * 60)
    print("TacEdge Gateway - JWT Token Generator")
    print("=" * 60)
    print(f"\nNode:           {args.node}")
    print(f"Role:           {args.role}")
    print(f"Classification: {args.classification}")
    print(f"Expires in:     {args.expiry} hours")
    print(f"\n{'=' * 60}")
    print("\nToken:")
    print(token)
    print(f"\n{'=' * 60}")
    
    if args.debug:
        print("\nDecoded Token:")
        decoded = decode_token(token, args.secret)
        import json
        print(json.dumps(decoded, indent=2, default=str))
    
    print("\nUsage:")
    print(f'  curl -H "Authorization: Bearer {token[:50]}..." ...')
    print()


if __name__ == "__main__":
    main()

