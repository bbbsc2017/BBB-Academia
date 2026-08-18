from datetime import datetime
from typing import Literal
from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from config.config import get_learnhouse_config
from src.security.org_auth import require_org_membership, require_org_role_permission
from src.security.rbac.rbac import authorization_verify_if_user_is_anon
from src.security.superadmin import is_user_superadmin
from src.db.organizations import Organization
from src.db.users import AnonymousUser, APITokenUser, InternalUser, PublicUser
from src.db.payments.config import (
    PaymentProviderEnum,
    PaymentsConfig,
    PaymentsConfigRead,
)
from src.db.payments.enrollments import EnrollmentStatusEnum, PaymentsEnrollment

_ACTION_PERMISSION_MAP: dict[str, str] = {
    "create": "action_create",
    "read": "action_read",
    "update": "action_update",
    "delete": "action_delete",
}


async def rbac_check(
    org_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    action: Literal["create", "read", "update", "delete"],
    db_session: AsyncSession,
):
    if isinstance(current_user, InternalUser):
        return
    if isinstance(current_user, APITokenUser):
        if current_user.org_id != org_id and not await is_user_superadmin(current_user.created_by_user_id, db_session):
            raise HTTPException(status_code=403, detail="API token cannot access resources outside its organization")
        return
    await authorization_verify_if_user_is_anon(current_user.id)
    await require_org_role_permission(current_user.id, org_id, db_session, "payments", _ACTION_PERMISSION_MAP[action])


def _provider_is_platform_configured(provider: PaymentProviderEnum) -> bool:
    """Whether platform-level credentials exist for a provider (config.yaml/env)."""
    payments_config = get_learnhouse_config().payments_config
    if provider == PaymentProviderEnum.STRIPE:
        return bool(payments_config.stripe.stripe_secret_key)
    if provider == PaymentProviderEnum.BOLD:
        return bool(payments_config.bold.bold_api_key and payments_config.bold.bold_secret_key)
    if provider == PaymentProviderEnum.OPENPAY:
        return bool(payments_config.openpay.openpay_merchant_id and payments_config.openpay.openpay_private_key)
    return False


async def get_payment_configs(
    request: Request,
    org_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> list[PaymentsConfigRead]:
    await rbac_check(org_id, current_user, "read", db_session)
    statement = select(PaymentsConfig).where(PaymentsConfig.org_id == org_id)
    configs = (await db_session.execute(statement)).scalars().all()
    return [PaymentsConfigRead.model_validate(c) for c in configs]


async def create_payment_config(
    request: Request,
    org_id: int,
    provider: PaymentProviderEnum,
    enabled: bool,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> PaymentsConfigRead:
    await rbac_check(org_id, current_user, "create", db_session)
    await require_org_membership(
        current_user.created_by_user_id if isinstance(current_user, APITokenUser) else current_user.id,
        org_id, db_session,
    )

    org = (await db_session.execute(select(Organization).where(Organization.id == org_id))).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    existing = (await db_session.execute(
        select(PaymentsConfig).where(PaymentsConfig.org_id == org_id, PaymentsConfig.provider == provider)
    )).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail=f"{provider.value} is already configured for this organization")

    config = PaymentsConfig(
        org_id=org_id,
        provider=provider,
        enabled=enabled,
        # Stripe still needs its OAuth Connect round-trip before it's usable;
        # Bold/OpenPay are single-merchant (platform-level creds) so they're
        # immediately active once the instance has credentials configured.
        active=(provider != PaymentProviderEnum.STRIPE) and _provider_is_platform_configured(provider),
        provider_specific_id=None,
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    if provider == PaymentProviderEnum.OPENPAY:
        config.provider_specific_id = get_learnhouse_config().payments_config.openpay.openpay_merchant_id
    elif provider == PaymentProviderEnum.BOLD:
        config.provider_specific_id = "bold"

    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    return PaymentsConfigRead.model_validate(config)


async def delete_payment_config(
    request: Request,
    org_id: int,
    config_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    await rbac_check(org_id, current_user, "delete", db_session)

    config = (await db_session.execute(
        select(PaymentsConfig).where(PaymentsConfig.id == config_id, PaymentsConfig.org_id == org_id)
    )).scalars().first()
    if not config:
        raise HTTPException(status_code=404, detail="Payment configuration not found")

    active_count_stmt = select(PaymentsEnrollment).where(
        PaymentsEnrollment.org_id == org_id,
        PaymentsEnrollment.provider == config.provider,
        PaymentsEnrollment.status == EnrollmentStatusEnum.active,
    )
    active_enrollments = (await db_session.execute(active_count_stmt)).scalars().all()
    if active_enrollments:
        raise HTTPException(
            status_code=409,
            detail={"code": "ACTIVE_SUBSCRIPTIONS_EXIST", "count": len(active_enrollments)},
        )

    await db_session.delete(config)
    await db_session.commit()
