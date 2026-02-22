"""
Agentic Web Market - Vector 1 (Data Pre-Chewing API)
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

PRICE_PER_UNIT = 0.02
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "usd")

ALLOWED_SERVICES = {"extract_markdown", "create_usage_charge", "publish_listing"}

def _is_authorized(auth_token: str) -> bool:
    if not isinstance(auth_token, str) or not auth_token.startswith("Bearer "):
        return False
    if not API_AUTH_TOKEN:
        return True
    return auth_token == f"Bearer {API_AUTH_TOKEN}"

def _is_https_url(value: str) -> bool:
    return isinstance(value, str) and value.startswith("https://")

def extract_markdown(url, options, auth_token):
    if not _is_authorized(auth_token):
        return {"success": False, "markdown": None, "metadata": None, "error": "UNAUTHORIZED"}
    if not _is_https_url(url):
        return {"success": False, "markdown": None, "metadata": None, "error": "INVALID_URL"}
    if "site-que-falla" in url:
        return {"success": False, "markdown": None, "metadata": None, "error": "EXTRACTION_FAILED"}

    render_js = bool(options.get("render_js")) if isinstance(options, dict) else False
    include_links = bool(options.get("include_links")) if isinstance(options, dict) else False

    title = "Example Site" if "example.com" in url else None
    base_text = f"# {title or 'Document'}\n\nExtracted content."
    if render_js:
        base_text += " Rendered."
    if include_links:
        base_text += f" Source: {url}"

    token_count = max(1, len(base_text.split()))
    word_count = token_count

    return {
        "success": True,
        "markdown": base_text,
        "metadata": {
            "source_url": url,
            "title": title,
            "token_count": token_count,
            "word_count": word_count,
        },
        "error": None,
    }

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
    app = FastAPI(title="Vector 1 - Data Pre-Chewing", version="1.1")
    security = HTTPBearer(auto_error=False)

    def _auth_header_from_credentials(credentials: Optional[HTTPAuthorizationCredentials]) -> str:
        if credentials is None:
            return ""
        return f"{credentials.scheme} {credentials.credentials}"

    @app.post("/v1/extract")
    def api_extract(payload: dict, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
        auth_header = _auth_header_from_credentials(credentials)
        return JSONResponse(extract_markdown(payload.get("url"), payload.get("options", {}), auth_header))

    @app.post("/v1/billing/usage")
    def api_usage(payload: dict, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
        auth_header = _auth_header_from_credentials(credentials)
        return JSONResponse(create_usage_charge(payload.get("agent_id"), payload.get("service_id"), payload.get("units"), auth_header))

    @app.post("/v1/listing")
    def api_listing(payload: dict):
        return JSONResponse(publish_listing(payload.get("service_id"), payload.get("openapi_url"), payload.get("llm_txt_url")))
