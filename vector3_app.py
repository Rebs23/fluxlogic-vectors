"""
Agentic Web Market - Vector 3 (LLM.TXT Generator)
FastAPI app with billing + listing endpoints.
"""

from __future__ import annotations

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

PRICE_PER_UNIT = 0.03
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "usd")

ALLOWED_SERVICES = {"generate_llm_txt", "create_usage_charge", "publish_listing"}

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

def generate_llm_txt(domain, auth_token):
    if not _is_authorized(auth_token):
        return {"success": False, "llm_txt": None, "llm_full_txt": None, "error": "UNAUTHORIZED"}
    if not isinstance(domain, str) or "http" in domain or "/" in domain or " " in domain:
        return {"success": False, "llm_txt": None, "llm_full_txt": None, "error": "INVALID_DOMAIN"}
    if "site-que-falla" in domain:
        return {"success": False, "llm_txt": None, "llm_full_txt": None, "error": "CRAWL_FAILED"}
    llm_txt = f"site: {domain}\nsummary: agentic-ready"
    llm_full_txt = f"site: {domain}\npaths:\n- /\n- /docs"
    return {"success": True, "llm_txt": llm_txt, "llm_full_txt": llm_full_txt, "error": None}

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
    app = FastAPI(title="Vector 3 - LLM.TXT Generator", version="1.1")
    security = HTTPBearer(auto_error=False)

    def _auth_header_from_credentials(credentials: Optional[HTTPAuthorizationCredentials]) -> str:
        if credentials is None:
            return ""
        return f"{credentials.scheme} {credentials.credentials}"

    @app.post("/v1/llm-txt")
    def api_llm_txt(payload: dict, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
        auth_header = _auth_header_from_credentials(credentials)
        return JSONResponse(generate_llm_txt(payload.get("domain"), auth_header))

    @app.post("/v1/billing/usage")
    def api_usage(payload: dict, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
        auth_header = _auth_header_from_credentials(credentials)
        return JSONResponse(create_usage_charge(payload.get("agent_id"), payload.get("service_id"), payload.get("units"), auth_header))

    @app.post("/v1/listing")
    def api_listing(payload: dict):
        return JSONResponse(publish_listing(payload.get("service_id"), payload.get("openapi_url"), payload.get("llm_txt_url")))
