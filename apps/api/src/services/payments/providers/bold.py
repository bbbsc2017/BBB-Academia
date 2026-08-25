"""
Bold (Colombia) — Payment Links API.
https://developers.bold.co/pagos-en-linea/api-link-de-pagos (checkout)
https://developers.bold.co/webhook (webhook)

This uses Bold's server-to-server Payment Links API (POST /online/link/v1,
`Authorization: x-api-key <identity key>`), NOT the client-side embedded
Payment Button — that flow signs an `integrity_signature` with the secret
key and is a different integration path we don't use here. Webhook events
follow Bold's CloudEvents envelope. For Payment Links, Bold returns the
generated `LNK_*` value at `data.metadata.reference`, so it is stored on the
pending enrollment for webhook lookup. The event id for idempotency is the
top-level `id`.
"""
import base64
import hashlib
import hmac
import json
import os
from typing import Any, Optional, TYPE_CHECKING

import httpx
from sqlmodel import select

from config.config import get_learnhouse_config
from src.db.payments.config import PaymentProviderEnum, PaymentsConfig
from src.db.payments.enrollments import PaymentsEnrollment
from src.db.payments.offers import PaymentsOffer
from src.db.users import PublicUser
from src.services.webhooks.crypto import decrypt_secret
from src.services.payments.providers.base import (
    PaymentProvider,
    PaymentProviderError,
    ProviderEvent,
    WebhookOutcome,
    WebhookVerificationError,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


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
        # These are the LEARNHOUSE_BOLD_* env/config.yaml fallback, used when
        # no dashboard-entered override exists — see _resolve_credentials.
        self._env_api_key = cfg.bold_api_key
        self._env_webhook_secret = cfg.bold_webhook_secret
        api_base = os.environ.get(
            "LEARNHOUSE_BOLD_API_BASE_URL", "https://integrations.api.bold.co"
        ).rstrip("/")
        self._client = httpx.AsyncClient(base_url=api_base, timeout=15.0)

    async def _resolve_credentials(
        self, db_session: "Optional[AsyncSession]"
    ) -> tuple[Optional[str], Optional[str]]:
        """(api_key, webhook_secret), preferring credentials entered through
        the dashboard (encrypted in PaymentsConfig.provider_config — see
        services/payments/config.py::update_provider_credentials) over the
        LEARNHOUSE_BOLD_* env/config.yaml values captured at __init__. This
        deployment is single-tenant, so there is at most one BOLD
        PaymentsConfig row with provider_config set — no org_id needed to
        disambiguate."""
        api_key, webhook_secret = self._env_api_key, self._env_webhook_secret
        if db_session is None:
            return api_key, webhook_secret

        config = (await db_session.execute(
            select(PaymentsConfig).where(
                PaymentsConfig.provider == PaymentProviderEnum.BOLD,
                PaymentsConfig.provider_config.isnot(None),
            )
        )).scalars().first()
        stored = config.provider_config if config else None
        if not stored:
            return api_key, webhook_secret

        if stored.get("bold_api_key"):
            api_key = decrypt_secret(stored["bold_api_key"])
        if stored.get("bold_webhook_secret"):
            webhook_secret = decrypt_secret(stored["bold_webhook_secret"])
        return api_key, webhook_secret

    async def create_checkout(
        self,
        offer: PaymentsOffer,
        enrollment: PaymentsEnrollment,
        redirect_uri: str,
        buyer: PublicUser,
        db_session: "Optional[AsyncSession]" = None,
    ) -> str:
        api_key, _ = await self._resolve_credentials(db_session)
        if not api_key:
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
                headers={"Authorization": f"x-api-key {api_key}"},
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
        payment_link = _get_nested(data, ["payload", "payment_link"])
        if not url or not payment_link:
            raise PaymentProviderError("Bold checkout response missing payload.url or payload.payment_link")

        # Payment Links webhooks identify API-created links by their LNK_* id,
        # not by the `reference` supplied when creating the link.
        if db_session is not None:
            enrollment.provider_specific_data = {
                **(enrollment.provider_specific_data or {}),
                "bold_payment_link": str(payment_link),
            }
            db_session.add(enrollment)
            await db_session.commit()
        return url

    async def verify_and_parse_webhook(
        self, raw_body: bytes, headers: dict[str, str], db_session: "Optional[AsyncSession]" = None
    ) -> ProviderEvent:
        normalized = _normalize_headers(headers)
        signature = normalized.get("x-bold-signature")
        if not signature:
            raise WebhookVerificationError("Missing Bold webhook signature")

        _, webhook_secret = await self._resolve_credentials(db_session)
        if not webhook_secret:
            raise WebhookVerificationError("Bold webhook secret is not configured")

        # Bold signs the base64-encoded body, not the raw bytes, and sends
        # the digest as hex.
        expected = hmac.new(
            webhook_secret.encode(),
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

        # Keep numeric references working for links created by earlier code,
        # but resolve the LNK_* id used by Bold's Payment Links API.
        try:
            enrollment_id = int(enrollment_ref)
        except (TypeError, ValueError):
            if db_session is None:
                raise WebhookVerificationError("Bold webhook requires a database session to resolve payment link")
            enrollments = (await db_session.execute(
                select(PaymentsEnrollment).where(
                    PaymentsEnrollment.provider == PaymentProviderEnum.BOLD,
                )
            )).scalars().all()
            enrollment = next(
                (
                    item for item in enrollments
                    if (item.provider_specific_data or {}).get("bold_payment_link") == str(enrollment_ref)
                ),
                None,
            )
            if not enrollment or enrollment.id is None:
                raise WebhookVerificationError("Bold webhook references an unknown payment link")
            enrollment_id = enrollment.id

        event_type = str(payload.get("type") or "").upper()
        outcome = _EVENT_OUTCOMES.get(event_type, "ignored")

        return ProviderEvent(
            outcome=outcome,
            enrollment_id=enrollment_id,
            provider_event_id=str(event_id),
            provider_specific_data={
                "provider": "BOLD",
                "bold_payment_link": str(enrollment_ref),
                "raw_event": payload,
            },
        )
