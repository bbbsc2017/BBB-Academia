"""
OpenPay Colombia (openpay.co) — hosted "redirect" charge flow.
https://docs.openpay.co/docs/api/ (charges), https://docs.openpay.co/docs/webhooks.html

Two things make OpenPay's integration shape different from Bold's:

1. OpenPay does NOT sign webhook payloads at all — there is no HMAC/signature
   header to check. Trusting a POSTed `status`/`type` directly would let
   anyone forge a "charge.succeeded" webhook and grant themselves free
   access. So verify_and_parse_webhook only uses the webhook body to learn
   *which* transaction to look at, then calls back to OpenPay's REST API
   (Basic Auth: private key as username, blank password) to fetch that
   transaction's real, authoritative status — the activate/cancel/fail
   decision is made from THAT response, never from the webhook body.

2. Registering a webhook URL makes OpenPay immediately POST a one-off
   `{"type": "verification", "verification_code": "..."}` handshake (the
   code then has to be pasted back into the OpenPay dashboard by a human).
   That event has no transaction/order tied to it, so it can't become a
   ProviderEvent — verify_and_parse_webhook returns None for it and the
   router just 200s.

Charge status strings below (`completed`/`in_progress`/`cancelled`/
`refunded`/`failed`) are the standard OpenPay/Conekta-family values; worth
double-checking against real sandbox responses during end-to-end testing.

Subscriptions are intentionally out of scope: this integration only ever
needs to handle one-time payments, and OpenPay's recurring billing would
need a persisted Customer + a tokenized card (via their client-side JS SDK)
anyway — a different UX from this redirect-checkout flow. create_checkout
raises a clear error if a subscription offer somehow reaches it.
"""
import json
import os
from typing import Any, Optional

import httpx

from config.config import get_learnhouse_config
from src.db.payments.enrollments import PaymentsEnrollment
from src.db.payments.offers import OfferTypeEnum, PaymentsOffer
from src.db.users import PublicUser
from src.services.payments.providers.base import (
    PaymentProvider,
    PaymentProviderError,
    ProviderEvent,
    WebhookOutcome,
    WebhookVerificationError,
)


def _get_nested(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


# OpenPay/Conekta-family charge `status` values, from GET /charges/{id}.
_STATUS_OUTCOMES: dict[str, WebhookOutcome] = {
    "completed": "activated",
    "cancelled": "cancelled",
    "failed": "failed",
    "refunded": "refunded",
    "in_progress": "ignored",
    "charge_pending": "ignored",
}


class OpenPayProvider(PaymentProvider):
    def __init__(self) -> None:
        cfg = get_learnhouse_config().payments_config.openpay
        self._merchant_id = cfg.openpay_merchant_id
        self._private_key = cfg.openpay_private_key
        api_base = os.environ.get(
            "LEARNHOUSE_OPENPAY_API_BASE_URL",
            "https://api.openpay.co" if cfg.openpay_production else "https://sandbox-api.openpay.co",
        ).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=f"{api_base}/v1/{self._merchant_id}",
            auth=(self._private_key or "", ""),
            timeout=15.0,
        )

    async def create_checkout(
        self,
        offer: PaymentsOffer,
        enrollment: PaymentsEnrollment,
        redirect_uri: str,
        buyer: PublicUser,
    ) -> str:
        if not self._merchant_id or not self._private_key:
            raise PaymentProviderError("OpenPay is not configured: missing merchant_id/private_key")
        if offer.offer_type == OfferTypeEnum.subscription:
            raise PaymentProviderError(
                "OpenPay subscriptions require a tokenized-card flow that isn't implemented yet"
            )

        body = {
            "method": "card",
            "amount": offer.amount,
            "currency": offer.currency,
            "description": (offer.name or "Payment")[:250],
            "order_id": str(enrollment.id),
            "confirm": False,
            "send_email": False,
            "redirect_url": redirect_uri,
            "customer": {
                # OpenPay rejects an empty customer.name — first_name is blank
                # for some real accounts (e.g. ones created before it was
                # required), so fall back to username rather than send "".
                "name": buyer.first_name or buyer.username,
                "last_name": buyer.last_name or "-",
                "email": buyer.email,
            },
        }

        try:
            response = await self._client.post("/charges", json=body)
        except httpx.HTTPError as exc:
            raise PaymentProviderError(f"OpenPay checkout request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise PaymentProviderError("OpenPay checkout returned a non-JSON response") from exc

        if response.status_code >= 400:
            raise PaymentProviderError(f"OpenPay checkout failed: {data}")

        url = _get_nested(data, ["payment_method", "url"])
        if not url:
            raise PaymentProviderError("OpenPay checkout response missing payment_method.url")
        return url

    async def _fetch_charge(self, charge_id: str) -> dict[str, Any]:
        try:
            response = await self._client.get(f"/charges/{charge_id}")
        except httpx.HTTPError as exc:
            raise WebhookVerificationError(f"Could not confirm OpenPay charge {charge_id}: {exc}") from exc
        if response.status_code >= 400:
            raise WebhookVerificationError(
                f"OpenPay charge lookup for {charge_id} failed with {response.status_code}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise WebhookVerificationError("OpenPay charge lookup returned a non-JSON response") from exc

    async def verify_and_parse_webhook(
        self, raw_body: bytes, headers: dict[str, str]
    ) -> Optional[ProviderEvent]:
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise WebhookVerificationError("Invalid OpenPay webhook payload") from exc

        # One-off handshake sent when the webhook URL is registered — no
        # transaction attached, nothing to reconcile, no API call needed.
        if str(payload.get("type") or "") == "verification":
            return None

        if not self._merchant_id or not self._private_key:
            raise WebhookVerificationError("OpenPay is not configured: missing merchant_id/private_key")

        transaction_id = _get_nested(payload, ["transaction", "id"])
        if not transaction_id:
            raise WebhookVerificationError("OpenPay webhook missing transaction.id")

        # The webhook body itself is unsigned and untrusted — fetch the
        # transaction's real state from OpenPay's API instead of trusting
        # whatever status this POST claims.
        confirmed = await self._fetch_charge(str(transaction_id))

        enrollment_ref = confirmed.get("order_id")
        if not enrollment_ref:
            raise WebhookVerificationError("OpenPay charge missing order_id")

        try:
            enrollment_id = int(enrollment_ref)
        except ValueError as exc:
            raise WebhookVerificationError("OpenPay order_id must be numeric") from exc

        status = str(confirmed.get("status") or "").lower()
        outcome = _STATUS_OUTCOMES.get(status, "ignored")

        return ProviderEvent(
            outcome=outcome,
            enrollment_id=enrollment_id,
            provider_event_id=str(transaction_id),
            provider_specific_data={
                "provider": "OPENPAY",
                "confirmed_charge": confirmed,
            },
        )
