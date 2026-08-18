"""
Bold (Colombia) — Payment Links API.
https://developers.bold.co/pagos-en-linea/api-link-de-pagos (checkout)
https://developers.bold.co/webhook (webhook)

This uses Bold's server-to-server Payment Links API (POST /online/link/v1,
`Authorization: x-api-key <identity key>`), NOT the client-side embedded
Payment Button — that flow signs an `integrity_signature` with the secret
key and is a different integration path we don't use here. Webhook events
follow Bold's CloudEvents envelope: the merchant's own reference comes back
at `data.metadata.reference`, and the event id for idempotency is the
top-level `id`.
"""
import base64
import hashlib
import hmac
import json
import os
from typing import Any

import httpx

from config.config import get_learnhouse_config
from src.db.payments.enrollments import PaymentsEnrollment
from src.db.payments.offers import PaymentsOffer
from src.db.users import PublicUser
from src.services.payments.providers.base import (
    PaymentProvider,
    PaymentProviderError,
    ProviderEvent,
    WebhookOutcome,
    WebhookVerificationError,
)


def _normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k.lower(): v for k, v in headers.items()}


def _get_nested(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


# CloudEvents `type` values Bold's Payment Links product sends — see
# https://developers.bold.co/webhook. VOID_APPROVED means an approved sale
# was reversed (money back to the buyer), so it maps to "refunded" rather
# than "cancelled" (which is for pending enrollments that never paid).
_EVENT_OUTCOMES: dict[str, WebhookOutcome] = {
    "SALE_APPROVED": "activated",
    "SALE_REJECTED": "failed",
    "VOID_APPROVED": "refunded",
    "VOID_REJECTED": "ignored",
}


class BoldProvider(PaymentProvider):
    def __init__(self) -> None:
        cfg = get_learnhouse_config().payments_config.bold
        # Bold's dashboard calls this the "Identity key" — it's what
        # `Authorization: x-api-key` takes for Payment Links API calls.
        self._api_key = cfg.bold_api_key
        self._webhook_secret = cfg.bold_webhook_secret
        api_base = os.environ.get(
            "LEARNHOUSE_BOLD_API_BASE_URL", "https://integrations.api.bold.co"
        ).rstrip("/")
        self._client = httpx.AsyncClient(base_url=api_base, timeout=15.0)

    async def create_checkout(
        self,
        offer: PaymentsOffer,
        enrollment: PaymentsEnrollment,
        redirect_uri: str,
        buyer: PublicUser,
    ) -> str:
        if not self._api_key:
            raise PaymentProviderError("Bold is not configured: missing api_key")

        body = {
            "amount_type": "CLOSE",
            "amount": {
                "currency": offer.currency,
                "total_amount": offer.amount,
                "tip_amount": 0,
            },
            # Alphanumeric/underscore/hyphen, max 60 chars — enrollment.id fits easily.
            "reference": str(enrollment.id),
            "description": (offer.name or "Payment")[:100],
            "callback_url": redirect_uri,
            "payer_email": buyer.email,
        }

        try:
            response = await self._client.post(
                "/online/link/v1",
                json=body,
                headers={"Authorization": f"x-api-key {self._api_key}"},
            )
        except httpx.HTTPError as exc:
            raise PaymentProviderError(f"Bold checkout request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise PaymentProviderError("Bold checkout returned a non-JSON response") from exc

        errors = data.get("errors") or []
        if response.status_code >= 400 or errors:
            raise PaymentProviderError(f"Bold checkout failed: {errors or response.text}")

        url = _get_nested(data, ["payload", "url"])
        if not url:
            raise PaymentProviderError("Bold checkout response missing payload.url")
        return url

    async def verify_and_parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> ProviderEvent:
        normalized = _normalize_headers(headers)
        signature = normalized.get("x-bold-signature")
        if not signature:
            raise WebhookVerificationError("Missing Bold webhook signature")
        if not self._webhook_secret:
            raise WebhookVerificationError("Bold webhook secret is not configured")

        # Bold signs the base64-encoded body, not the raw bytes, and sends
        # the digest as hex.
        expected = hmac.new(
            self._webhook_secret.encode(),
            base64.b64encode(raw_body),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise WebhookVerificationError("Invalid Bold webhook signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise WebhookVerificationError("Invalid Bold webhook payload") from exc

        enrollment_ref = _get_nested(payload, ["data", "metadata", "reference"])
        if not enrollment_ref:
            raise WebhookVerificationError("Bold webhook missing data.metadata.reference")

        event_id = payload.get("id")
        if not event_id:
            raise WebhookVerificationError("Bold webhook missing event id")

        try:
            enrollment_id = int(enrollment_ref)
        except ValueError as exc:
            raise WebhookVerificationError("Bold enrollment reference must be numeric") from exc

        event_type = str(payload.get("type") or "").upper()
        outcome = _EVENT_OUTCOMES.get(event_type, "ignored")

        return ProviderEvent(
            outcome=outcome,
            enrollment_id=enrollment_id,
            provider_event_id=str(event_id),
            provider_specific_data={
                "provider": "BOLD",
                "raw_event": payload,
            },
        )
