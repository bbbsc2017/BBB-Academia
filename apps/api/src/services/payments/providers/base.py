"""
Provider abstraction — every payment gateway (Bold, OpenPay, ...) implements
this interface. The router/offers checkout endpoint is provider-agnostic: it
looks up the org's active PaymentsConfig, dispatches to get_provider(), and
never branches on provider type itself.

Concrete providers live alongside this file (bold.py, openpay.py — each
checked against its current merchant API docs before being trusted with
money-handling logic).

verify_and_parse_webhook is async and may return None: OpenPay Colombia
doesn't sign webhook payloads at all, so its implementation must call back
to Openpay's REST API to confirm a transaction's real status rather than
trusting the POST body, and must also handle Openpay's unrelated
"verification" handshake event (sent once when a webhook URL is registered)
by acknowledging it with no enrollment to act on — hence Optional.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from src.db.payments.config import PaymentProviderEnum
from src.db.payments.enrollments import PaymentsEnrollment
from src.db.payments.offers import PaymentsOffer
from src.db.users import PublicUser

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

WebhookOutcome = Literal["activated", "cancelled", "failed", "refunded", "ignored"]


@dataclass
class ProviderEvent:
    """A provider's webhook payload, normalized to what enrollments.py needs."""
    outcome: WebhookOutcome
    enrollment_id: int
    # The provider's own event/transaction id — used as the idempotency key
    # so a retried webhook delivery never double-processes the same event.
    provider_event_id: str
    provider_specific_data: dict[str, Any] = field(default_factory=dict)


class PaymentProviderError(Exception):
    """Raised for provider-side failures (bad credentials, API error, etc.)."""


class WebhookVerificationError(Exception):
    """Raised when a webhook's signature doesn't verify — the caller should
    respond 401/400 and must NOT process the payload."""


class PaymentProvider(ABC):
    @abstractmethod
    async def create_checkout(
        self,
        offer: PaymentsOffer,
        enrollment: PaymentsEnrollment,
        redirect_uri: str,
        buyer: PublicUser,
        db_session: AsyncSession | None = None,
    ) -> str:
        """Create a checkout session/link with the provider and return the
        URL to redirect the buyer to. `enrollment.id` must be embedded as the
        order/reference id so the webhook handler can look it back up.

        db_session: optional, passed through so a provider that supports
        dashboard-entered credentials (see BoldProvider) can look up its
        PaymentsConfig.provider_config override. Providers that only use
        env/config.yaml-level credentials (OpenPay) ignore it."""
        ...

    @abstractmethod
    async def verify_and_parse_webhook(
        self, raw_body: bytes, headers: dict[str, str], db_session: AsyncSession | None = None
    ) -> ProviderEvent | None:
        """Authenticate the webhook (via signature verification, or — for a
        provider that doesn't sign payloads — by calling back to the
        provider's REST API to fetch the transaction's real state) and
        return the normalized event. Returns None for a real-but-irrelevant
        notification (e.g. a webhook-registration handshake) that has no
        enrollment to act on; the caller should just 200 it. Raises
        WebhookVerificationError when the webhook can't be authenticated.

        db_session: see create_checkout — same dashboard-credentials lookup."""
        ...

    async def confirm_payment(
        self, enrollment: PaymentsEnrollment, db_session: AsyncSession | None = None
    ) -> bool:
        """Re-verify, server-side, whether a still-pending enrollment's
        payment actually succeeded — called when the buyer's browser returns
        from the provider's checkout page, as a safety net for when the
        provider's webhook is misconfigured, delayed, or never arrives.

        MUST call back to the provider's own API using data stored on the
        enrollment (never trust a client-supplied query param claiming
        success — see PaymentWall/checkout return handling). Returns True
        only when the provider confirms the payment is genuinely approved;
        the caller is responsible for calling activate_enrollment() itself.

        Default: not supported (caller falls back to webhook-only). Override
        in a provider whose API supports looking up a payment by reference."""
        return False


_PROVIDERS: dict[PaymentProviderEnum, PaymentProvider] = {}


def register_provider(provider: PaymentProviderEnum, implementation: PaymentProvider) -> None:
    _PROVIDERS[provider] = implementation


def get_provider(provider: PaymentProviderEnum) -> PaymentProvider:
    impl = _PROVIDERS.get(provider)
    if impl is None:
        raise PaymentProviderError(f"No provider implementation registered for {provider.value}")
    return impl
