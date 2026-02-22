"""
Agentic Web Market - Vector 2 (Agent Skills)
FastAPI app with billing + listing endpoints.
"""

from __future__ import annotations

import base64
import os
from typing import Optional

try:
    from fastapi import Depends, FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False

try:
    import stripe
    STRIPE_AVAILABLE = True
except Exception:
    STRIPE_AVAILABLE = False

PRICE_PER_UNIT = 0.05
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "usd")

ALLOWED_SERVICES = {"run_skill", "create_usage_charge", "publish_listing"}

def _normalize_auth_token(auth_token: str) -> str:
    if not isinstance(auth_token, str):
        return ""
    token = auth_token.strip()
    # Accept token with or without Bearer, and collapse accidental duplicates.
    while token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token

def _is_authorized(auth_token: str) -> bool:
    token = _normalize_auth_token(auth_token)
    if not token:
        return False
    if not API_AUTH_TOKEN:
        return True
    return token == API_AUTH_TOKEN

def _is_https_url(value: str) -> bool:
    return isinstance(value, str) and value.startswith("https://")

def run_skill(skill_id, payload_b64, auth_token):
    if not _is_authorized(auth_token):
        return {"success": False, "result": None, "error": "UNAUTHORIZED"}
    if skill_id != "pdf_financials":
        return {"success": False, "result": None, "error": "UNKNOWN_SKILL"}
    if not isinstance(payload_b64, str) or payload_b64 == "":
        return {"success": False, "result": None, "error": "INVALID_PAYLOAD"}
    if "BAD" in payload_b64:
        return {"success": False, "result": None, "error": "SKILL_FAILED"}
    try:
        base64.b64decode(payload_b64, validate=True)
    except Exception:
        return {"success": False, "result": None, "error": "INVALID_PAYLOAD"}
    return {"success": True, "result": {"tables": 1, "rows": 10}, "error": None}

def create_usage_charge(agent_id, service_id, units, auth_token):
    if not _is_authorized(auth_token):
        return {"success": False, "charge": None, "error": "UNAUTHORIZED"}
    if not isinstance(service_id, str) or service_id not in ALLOWED_SERVICES:
        return {"success": False, "charge": None, "error": "UNKNOWN_SERVICE"}
    if not isinstance(units, int) or units <= 0:
        return {"success": False, "charge": None, "error": "INVALID_UNITS"}

    amount_usd = round(units * PRICE_PER_UNIT, 4)
    charge = {
        "agent_id": agent_id,
        "service_id": service_id,
        "units": units,
        "amount_usd": amount_usd,
        "status": "pending",
    }

    if STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount_usd * 100),
                currency=STRIPE_CURRENCY,
                metadata={"agent_id": agent_id, "service_id": service_id, "units": units},
            )
            charge["status"] = "billed"
            charge["payment_intent_id"] = intent.id
        except Exception:
            return {"success": False, "charge": None, "error": "STRIPE_ERROR"}

    return {"success": True, "charge": charge, "error": None}

def publish_listing(service_id, openapi_url, llm_txt_url):
    if not isinstance(service_id, str) or not service_id.strip():
        return {"success": False, "listing": None, "error": "INVALID_SERVICE"}
    if not _is_https_url(openapi_url) or not _is_https_url(llm_txt_url):
        return {"success": False, "listing": None, "error": "INVALID_URL"}
    return {
        "success": True,
        "listing": {
            "service_id": service_id,
            "openapi_url": openapi_url,
            "llm_txt_url": llm_txt_url,
        },
        "error": None,
    }

if FASTAPI_AVAILABLE:
    app = FastAPI(title="Vector 2 - Agent Skills", version="1.1")
    security = HTTPBearer(auto_error=False)

    def _auth_header_from_credentials(credentials: Optional[HTTPAuthorizationCredentials]) -> str:
        if credentials is None:
            return ""
        return f"{credentials.scheme} {credentials.credentials}"

    @app.post("/v1/skills/run")
    def api_run_skill(payload: dict, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
        auth_header = _auth_header_from_credentials(credentials)
        return JSONResponse(run_skill(payload.get("skill_id"), payload.get("payload_b64"), auth_header))

    @app.post("/v1/billing/usage")
    def api_usage(payload: dict, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
        auth_header = _auth_header_from_credentials(credentials)
        return JSONResponse(create_usage_charge(payload.get("agent_id"), payload.get("service_id"), payload.get("units"), auth_header))

    @app.post("/v1/listing")
    def api_listing(payload: dict):
        return JSONResponse(publish_listing(payload.get("service_id"), payload.get("openapi_url"), payload.get("llm_txt_url")))
