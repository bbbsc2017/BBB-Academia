"""
Enrollment lifecycle — the single place that translates a payment event
(from any provider) into actual product access.

Granting/revoking access is ALWAYS just adding/removing UserGroupUser rows.
security/rbac/rbac.py's check_usergroup_access() already reads UserGroupUser
membership to decide access (and already special-cases a denied resource
that belongs to a paid offer to raise 402) — so nothing here ever touches
the lock/RBAC engine directly, it only maintains the UserGroup membership
that engine already trusts.
"""
import logging
from datetime import datetime

from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.payments.config import PaymentProviderEnum
from src.db.payments.enrollments import (
    EnrollmentStatusEnum,
    PaymentsEnrollment,
    PaymentsEnrollmentRead,
)
from src.db.payments.groups import PaymentsGroup
from src.db.payments.offers import PaymentsOffer
from src.db.user_organizations import UserOrganization
from src.db.usergroup_user import UserGroupUser
from src.db.users import AnonymousUser, APITokenUser, InternalUser, PublicUser, User
from src.security.org_auth import require_org_role_permission
from src.security.rbac.rbac import authorization_verify_if_user_is_anon
from src.security.superadmin import is_user_superadmin

logger = logging.getLogger(__name__)

# Default "Learner" role — matches join_org()'s auto-join role
# (src/services/orgs/join.py) and create_user()'s default membership role.
_LEARNER_ROLE_ID = 4


async def _ensure_org_membership(user_id: int, org_id: int, db_session: AsyncSession) -> None:
    """Auto-join the org (as Learner) if the buyer isn't already a member —
    a purchase must never silently fail to grant access just because the
    buyer hadn't joined the org yet."""
    existing = (await db_session.execute(
        select(UserOrganization).where(UserOrganization.user_id == user_id, UserOrganization.org_id == org_id)
    )).scalars().first()
    if existing:
        return
    db_session.add(UserOrganization(
        user_id=user_id, org_id=org_id, role_id=_LEARNER_ROLE_ID,
        creation_date=str(datetime.now()), update_date=str(datetime.now()),
    ))
    await db_session.commit()


async def _grant_usergroup(user_id: int, usergroup_id: int, org_id: int, db_session: AsyncSession) -> None:
    existing = (await db_session.execute(
        select(UserGroupUser).where(UserGroupUser.usergroup_id == usergroup_id, UserGroupUser.user_id == user_id)
    )).scalars().first()
    if existing:
        return
    db_session.add(UserGroupUser(
        usergroup_id=usergroup_id, user_id=user_id, org_id=org_id,
        creation_date=str(datetime.now()), update_date=str(datetime.now()),
    ))
    await db_session.commit()


async def _revoke_usergroup(user_id: int, usergroup_id: int, db_session: AsyncSession) -> None:
    link = (await db_session.execute(
        select(UserGroupUser).where(UserGroupUser.usergroup_id == usergroup_id, UserGroupUser.user_id == user_id)
    )).scalars().first()
    if link:
        await db_session.delete(link)
        await db_session.commit()


async def create_pending_enrollment(
    offer: PaymentsOffer,
    user_id: int,
    org_id: int,
    provider: PaymentProviderEnum,
    db_session: AsyncSession,
) -> PaymentsEnrollment:
    """Called at checkout initiation, before redirecting to the provider —
    the enrollment id becomes the order/reference id passed to Bold/OpenPay
    so the webhook handler can look it back up unambiguously."""
    enrollment = PaymentsEnrollment(
        offer_id=offer.id,
        user_id=user_id,
        org_id=org_id,
        status=EnrollmentStatusEnum.pending,
        provider=provider,
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db_session.add(enrollment)
    await db_session.commit()
    await db_session.refresh(enrollment)
    return enrollment


async def activate_enrollment(
    enrollment_id: int,
    db_session: AsyncSession,
    provider_specific_data: dict | None = None,
) -> PaymentsEnrollment:
    """Payment confirmed by the provider — grant access. Idempotent: calling
    this twice for the same enrollment (e.g. a retried webhook) is a no-op
    the second time since _grant_usergroup skips existing memberships."""
    enrollment = (await db_session.execute(
        select(PaymentsEnrollment).where(PaymentsEnrollment.id == enrollment_id)
    )).scalars().first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    offer = (await db_session.execute(
        select(PaymentsOffer).where(PaymentsOffer.id == enrollment.offer_id)
    )).scalars().first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer for this enrollment no longer exists")

    await _ensure_org_membership(enrollment.user_id, enrollment.org_id, db_session)
    await _grant_usergroup(enrollment.user_id, offer.usergroup_id, enrollment.org_id, db_session)

    if offer.payments_group_id:
        group = (await db_session.execute(
            select(PaymentsGroup).where(PaymentsGroup.id == offer.payments_group_id)
        )).scalars().first()
        if group and group.usergroup_id:
            await _grant_usergroup(enrollment.user_id, group.usergroup_id, enrollment.org_id, db_session)

    enrollment.status = EnrollmentStatusEnum.active
    if provider_specific_data:
        enrollment.provider_specific_data = {**(enrollment.provider_specific_data or {}), **provider_specific_data}
    enrollment.update_date = str(datetime.now())
    db_session.add(enrollment)
    await db_session.commit()
    await db_session.refresh(enrollment)
    logger.info("Enrollment %s activated for user %s (offer %s)", enrollment.id, enrollment.user_id, offer.id)
    return enrollment


async def _deactivate_enrollment(
    enrollment_id: int,
    new_status: EnrollmentStatusEnum,
    db_session: AsyncSession,
    provider_specific_data: dict | None = None,
) -> PaymentsEnrollment:
    enrollment = (await db_session.execute(
        select(PaymentsEnrollment).where(PaymentsEnrollment.id == enrollment_id)
    )).scalars().first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    was_active = enrollment.status == EnrollmentStatusEnum.active

    if was_active:
        offer = (await db_session.execute(
            select(PaymentsOffer).where(PaymentsOffer.id == enrollment.offer_id)
        )).scalars().first()
        if offer:
            await _revoke_usergroup(enrollment.user_id, offer.usergroup_id, db_session)
            if offer.payments_group_id:
                group = (await db_session.execute(
                    select(PaymentsGroup).where(PaymentsGroup.id == offer.payments_group_id)
                )).scalars().first()
                if group and group.usergroup_id:
                    await _revoke_usergroup(enrollment.user_id, group.usergroup_id, db_session)

    enrollment.status = new_status
    if provider_specific_data:
        enrollment.provider_specific_data = {**(enrollment.provider_specific_data or {}), **provider_specific_data}
    enrollment.update_date = str(datetime.now())
    db_session.add(enrollment)
    await db_session.commit()
    await db_session.refresh(enrollment)
    logger.info("Enrollment %s -> %s for user %s", enrollment.id, new_status.value, enrollment.user_id)
    return enrollment


async def cancel_enrollment(enrollment_id: int, db_session: AsyncSession, provider_specific_data: dict | None = None) -> PaymentsEnrollment:
    return await _deactivate_enrollment(enrollment_id, EnrollmentStatusEnum.cancelled, db_session, provider_specific_data)


async def fail_enrollment(enrollment_id: int, db_session: AsyncSession, provider_specific_data: dict | None = None) -> PaymentsEnrollment:
    return await _deactivate_enrollment(enrollment_id, EnrollmentStatusEnum.failed, db_session, provider_specific_data)


async def refund_enrollment(enrollment_id: int, db_session: AsyncSession, provider_specific_data: dict | None = None) -> PaymentsEnrollment:
    return await _deactivate_enrollment(enrollment_id, EnrollmentStatusEnum.refunded, db_session, provider_specific_data)


# --- Admin / learner reads ---------------------------------------------------

async def get_org_customers(
    request: Request,
    org_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> list[dict]:
    if isinstance(current_user, InternalUser):
        pass
    elif isinstance(current_user, APITokenUser):
        if current_user.org_id != org_id and not await is_user_superadmin(current_user.created_by_user_id, db_session):
            raise HTTPException(status_code=403, detail="API token cannot access resources outside its organization")
    else:
        await authorization_verify_if_user_is_anon(current_user.id)
        await require_org_role_permission(current_user.id, org_id, db_session, "payments", "action_read")

    statement = (
        select(PaymentsEnrollment, User, PaymentsOffer)
        .join(User, User.id == PaymentsEnrollment.user_id)
        .join(PaymentsOffer, PaymentsOffer.id == PaymentsEnrollment.offer_id)
        .where(PaymentsEnrollment.org_id == org_id)
        .order_by(PaymentsEnrollment.creation_date.desc())
    )
    rows = (await db_session.execute(statement)).all()

    return [
        {
            "enrollment_id": enrollment.id,
            "status": enrollment.status.value,
            "provider": enrollment.provider.value,
            "creation_date": enrollment.creation_date,
            "user": {
                "user_uuid": user.user_uuid,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "email": user.email,
                "avatar_image": user.avatar_image,
            },
            "offer": {
                "name": offer.name,
                "offer_type": offer.offer_type.value,
                "amount": offer.amount,
                "currency": offer.currency,
            },
        }
        for enrollment, user, offer in rows
    ]


async def get_user_enrollments(
    org_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> list[PaymentsEnrollmentRead]:
    await authorization_verify_if_user_is_anon(current_user.id if not isinstance(current_user, APITokenUser) else current_user.created_by_user_id)
    user_id = current_user.created_by_user_id if isinstance(current_user, APITokenUser) else current_user.id
    statement = select(PaymentsEnrollment).where(
        PaymentsEnrollment.org_id == org_id, PaymentsEnrollment.user_id == user_id,
    ).order_by(PaymentsEnrollment.creation_date.desc())
    enrollments = (await db_session.execute(statement)).scalars().all()
    return [PaymentsEnrollmentRead.model_validate(e) for e in enrollments]


async def check_enrollment_access(resource_uuid: str, user_id: int, db_session: AsyncSession) -> bool:
    """Called from security/rbac/rbac.py as a resilience fallback: a user
    with an ACTIVE paid enrollment for this resource gets access even if
    their UserGroupUser row is missing/was removed (e.g. an admin edited
    the UserGroup directly) — payment status is the source of truth, group
    membership is just the mechanism access is normally granted through."""
    from src.db.payments.groups import PaymentsGroupResource
    from src.db.payments.offers import PaymentsOffer, PaymentsOfferResource

    direct_stmt = (
        select(PaymentsEnrollment)
        .join(PaymentsOffer, PaymentsOffer.id == PaymentsEnrollment.offer_id)
        .join(PaymentsOfferResource, PaymentsOfferResource.offer_id == PaymentsOffer.id)
        .where(
            PaymentsEnrollment.user_id == user_id,
            PaymentsEnrollment.status == EnrollmentStatusEnum.active,
            PaymentsOfferResource.resource_uuid == resource_uuid,
        )
    )
    via_group_stmt = (
        select(PaymentsEnrollment)
        .join(PaymentsOffer, PaymentsOffer.id == PaymentsEnrollment.offer_id)
        .join(PaymentsGroupResource, PaymentsGroupResource.group_id == PaymentsOffer.payments_group_id)
        .where(
            PaymentsEnrollment.user_id == user_id,
            PaymentsEnrollment.status == EnrollmentStatusEnum.active,
            PaymentsGroupResource.resource_uuid == resource_uuid,
        )
    )
    direct = (await db_session.execute(direct_stmt)).scalars().first()
    if direct:
        return True
    via_group = (await db_session.execute(via_group_stmt)).scalars().first()
    return via_group is not None
