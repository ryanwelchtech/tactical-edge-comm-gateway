"""
Tactical Edge Communications Gateway - Crypto Service

Centralized encryption/decryption service using AES-256-GCM
with PBKDF2 key derivation for tactical message protection.
"""

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import structlog

from .crypto_engine import CryptoEngine

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

# Prometheus metrics
ENCRYPT_TOTAL = Counter('tacedge_encrypt_total', 'Total encryption operations', ['status'])
DECRYPT_TOTAL = Counter('tacedge_decrypt_total', 'Total decryption operations', ['status'])
CRYPTO_LATENCY = Histogram(
    'tacedge_crypto_latency_seconds',
    'Cryptographic operation latency',
    ['operation'],
    buckets=[.001, .005, .01, .025, .05, .1, .25]
)

crypto_engine: CryptoEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global crypto_engine
    
    logger.info("Starting Crypto Service")
    
    # Initialize crypto engine
    master_key = os.getenv("ENCRYPTION_KEY", "development-key-change-in-production")
    crypto_engine = CryptoEngine(master_key)
    
    yield
    
    logger.info("Shutting down Crypto Service")


app = FastAPI(
    title="TacEdge Crypto Service",
    description="AES-256-GCM encryption service for tactical communications",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class EncryptRequest(BaseModel):
    """Encryption request."""
    plaintext: str = Field(..., min_length=1, max_length=65536)
    classification: str = Field(default="UNCLASSIFIED")


class EncryptResponse(BaseModel):
    """Encryption response."""
    ciphertext: str
    nonce: str
    tag: str
    algorithm: str = "AES-256-GCM"
    version: str = "v1"


class DecryptRequest(BaseModel):
    """Decryption request."""
    ciphertext: str
    nonce: str
    tag: str


class DecryptResponse(BaseModel):
    """Decryption response."""
    plaintext: str
    verified: bool


class VerifyRequest(BaseModel):
    """Integrity verification request."""
    ciphertext: str
    nonce: str
    tag: str


class VerifyResponse(BaseModel):
    """Integrity verification response."""
    valid: bool
    reason: str = None


class HealthResponse(BaseModel):
    """Service health status."""
    status: str
    version: str
    algorithm: str
    key_derivation: str


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Liveness probe endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        algorithm="AES-256-GCM",
        key_derivation="PBKDF2-SHA256"
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe endpoint."""
    if crypto_engine is None:
        return {"ready": False, "reason": "Crypto engine not initialized"}
    return {"ready": True}


@app.get("/metrics", tags=["Observability"])
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/api/v1/encrypt", response_model=EncryptResponse, tags=["Cryptography"])
async def encrypt_message(request: EncryptRequest):
    """
    Encrypt a message payload using AES-256-GCM.
    
    Implements NIST 800-53 SC-13 (Cryptographic Protection)
    """
    start_time = time.time()
    
    try:
        result = crypto_engine.encrypt(request.plaintext)
        
        latency = time.time() - start_time
        CRYPTO_LATENCY.labels(operation="encrypt").observe(latency)
        ENCRYPT_TOTAL.labels(status="success").inc()
        
        logger.info(
            "Message encrypted",
            classification=request.classification,
            latency_ms=int(latency * 1000)
        )
        
        return EncryptResponse(
            ciphertext=result["ciphertext"],
            nonce=result["nonce"],
            tag=result["tag"]
        )
        
    except Exception as e:
        ENCRYPT_TOTAL.labels(status="error").inc()
        logger.error("Encryption failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Encryption failed: {str(e)}")


@app.post("/api/v1/decrypt", response_model=DecryptResponse, tags=["Cryptography"])
async def decrypt_message(request: DecryptRequest):
    """
    Decrypt a previously encrypted message.
    
    Implements NIST 800-53 SC-13 (Cryptographic Protection)
    """
    start_time = time.time()
    
    try:
        plaintext = crypto_engine.decrypt(
            ciphertext=request.ciphertext,
            nonce=request.nonce,
            tag=request.tag
        )
        
        latency = time.time() - start_time
        CRYPTO_LATENCY.labels(operation="decrypt").observe(latency)
        DECRYPT_TOTAL.labels(status="success").inc()
        
        logger.info("Message decrypted", latency_ms=int(latency * 1000))
        
        return DecryptResponse(
            plaintext=plaintext,
            verified=True
        )
        
    except ValueError as e:
        DECRYPT_TOTAL.labels(status="verification_failed").inc()
        logger.warning("Decryption verification failed", error=str(e))
        raise HTTPException(status_code=400, detail="Message integrity verification failed")
        
    except Exception as e:
        DECRYPT_TOTAL.labels(status="error").inc()
        logger.error("Decryption failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Decryption failed: {str(e)}")


@app.post("/api/v1/verify", response_model=VerifyResponse, tags=["Cryptography"])
async def verify_integrity(request: VerifyRequest):
    """
    Verify message integrity without decryption.
    
    Implements NIST 800-53 SI-7 (Software, Firmware, and Information Integrity)
    """
    try:
        is_valid = crypto_engine.verify(
            ciphertext=request.ciphertext,
            nonce=request.nonce,
            tag=request.tag
        )
        
        return VerifyResponse(
            valid=is_valid,
            reason=None if is_valid else "Tag verification failed"
        )
        
    except Exception as e:
        logger.error("Verification failed", error=str(e))
        return VerifyResponse(
            valid=False,
            reason=str(e)
        )


@app.on_event("startup")
async def startup_event():
    app.state.start_time = time.time()
    logger.info("Crypto Service started")

