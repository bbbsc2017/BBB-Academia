from datetime import datetime
from typing import Literal

from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.organizations import Organization
from src.db.payments.config import PaymentsConfig
from src.db.payments.groups import PaymentsGroup
from src.db.payments.offers import (
    PaymentsOffer,
    PaymentsOfferCreate,
    PaymentsOfferRead,
    PaymentsOfferResource,
    PaymentsOfferUpdate,
)
from src.db.usergroups import UserGroupCreate
from src.db.users import AnonymousUser, APITokenUser, InternalUser, PublicUser
from src.security.org_auth import require_org_membership, require_org_role_permission
from src.security.rbac.rbac import authorization_verify_if_user_is_anon
from src.security.superadmin import is_user_superadmin
from src.services.users.usergroups import (
    add_resources_to_usergroup,
    create_usergroup,
    remove_resources_from_usergroup,
)

_ACTION_PERMISSION_MAP: dict[str, str] = {
    "create": "action_create",
    "read": "action_read",
    "update": "action_update",
    "delete": "action_delete",
}


async def _to_offer_read(offer: PaymentsOffer, db_session: AsyncSession) -> PaymentsOfferRead:
    config = (await db_session.execute(
        select(PaymentsConfig).where(PaymentsConfig.id == offer.payments_config_id)
    )).scalars().first()
    provider = config.provider if config else None
    return PaymentsOfferRead.model_validate({**offer.model_dump(), "provider": provider})


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


async def _get_offer_or_404(offer_id_or_uuid: int | str, org_id: int, db_session: AsyncSession) -> PaymentsOffer:
    if isinstance(offer_id_or_uuid, int) or offer_id_or_uuid.isdigit():
        statement = select(PaymentsOffer).where(PaymentsOffer.id == int(offer_id_or_uuid), PaymentsOffer.org_id == org_id)
    else:
        statement = select(PaymentsOffer).where(PaymentsOffer.offer_uuid == offer_id_or_uuid, PaymentsOffer.org_id == org_id)
    offer = (await db_session.execute(statement)).scalars().first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


async def get_offers(
    request: Request,
    org_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
    page: int = 1,
    limit: int = 20,
) -> list[PaymentsOfferRead]:
    await rbac_check(org_id, current_user, "read", db_session)
    statement = (
        select(PaymentsOffer)
        .where(PaymentsOffer.org_id == org_id, PaymentsOffer.is_archived == False)
        .order_by(PaymentsOffer.creation_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    offers = (await db_session.execute(statement)).scalars().all()
    return [await _to_offer_read(o, db_session) for o in offers]


async def get_offer(
    request: Request,
    org_id: int,
    offer_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> PaymentsOfferRead:
    await rbac_check(org_id, current_user, "read", db_session)
    offer = await _get_offer_or_404(offer_id, org_id, db_session)
    return await _to_offer_read(offer, db_session)


async def create_offer(
    request: Request,
    org_id: int,
    offer_create: PaymentsOfferCreate,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
    payments_config_id: int | None = None,
) -> PaymentsOfferRead:
    await rbac_check(org_id, current_user, "create", db_session)
    await require_org_membership(
        current_user.created_by_user_id if isinstance(current_user, APITokenUser) else current_user.id,
        org_id, db_session,
    )

    org = (await db_session.execute(select(Organization).where(Organization.id == org_id))).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # The frontend's CreateOfferForm doesn't collect a provider — an org
    # with a single active PaymentsConfig just uses it. payments_config_id
    # stays available for orgs juggling multiple active providers at once.
    if payments_config_id is not None:
        config = (await db_session.execute(
            select(PaymentsConfig).where(PaymentsConfig.id == payments_config_id, PaymentsConfig.org_id == org_id)
        )).scalars().first()
    else:
        config = (await db_session.execute(
            select(PaymentsConfig)
            .where(PaymentsConfig.org_id == org_id, PaymentsConfig.active == True)
            .order_by(PaymentsConfig.creation_date.desc())
        )).scalars().first()
    if not config:
        raise HTTPException(status_code=400, detail="No active payment provider configured for this organization")

    if offer_create.payments_group_id is not None:
        group = (await db_session.execute(
            select(PaymentsGroup).where(PaymentsGroup.id == offer_create.payments_group_id, PaymentsGroup.org_id == org_id)
        )).scalars().first()
        if not group:
            raise HTTPException(status_code=404, detail="Payments group not found")

    # Subscriptions are billed at a fixed recurring amount — customer_choice
    # (pay-what-you-want) doesn't make sense for recurring billing.
    price_type = offer_create.price_type
    if offer_create.offer_type.value == "subscription":
        from src.db.payments.offers import PriceTypeEnum
        price_type = PriceTypeEnum.fixed_price

    # The UserGroup that will gate every resource behind this offer.
    usergroup_read = await create_usergroup(
        request, db_session, current_user,
        UserGroupCreate(
            name=f"Offer: {offer_create.name}",
            description="Auto-created access group for a payments offer.",
            org_id=org_id,
        ),
    )

    offer = PaymentsOffer(
        org_id=org_id,
        payments_config_id=config.id,
        usergroup_id=usergroup_read.id,
        payments_group_id=offer_create.payments_group_id,
        name=offer_create.name,
        description=offer_create.description or "",
        offer_type=offer_create.offer_type,
        price_type=price_type,
        benefits=offer_create.benefits or "",
        amount=offer_create.amount,
        currency=offer_create.currency,
        is_publicly_listed=offer_create.is_publicly_listed,
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db_session.add(offer)
    await db_session.commit()
    await db_session.refresh(offer)

    if offer_create.resource_uuids:
        for resource_uuid in offer_create.resource_uuids:
            db_session.add(PaymentsOfferResource(
                offer_id=offer.id, resource_uuid=resource_uuid, org_id=org_id,
                creation_date=str(datetime.now()),
            ))
        await db_session.commit()
        # Actually gate access: link each resource to the offer's UserGroup.
        await add_resources_to_usergroup(
            request, db_session, current_user, usergroup_read.id, ",".join(offer_create.resource_uuids),
        )

    return await _to_offer_read(offer, db_session)


async def update_offer(
    request: Request,
    org_id: int,
    offer_id: int,
    offer_update: PaymentsOfferUpdate,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> PaymentsOfferRead:
    await rbac_check(org_id, current_user, "update", db_session)
    offer = await _get_offer_or_404(offer_id, org_id, db_session)

    update_data = offer_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(offer, key, value)
    offer.update_date = str(datetime.now())

    db_session.add(offer)
    await db_session.commit()
    await db_session.refresh(offer)
    return await _to_offer_read(offer, db_session)


async def archive_offer(
    request: Request,
    org_id: int,
    offer_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    """Soft-delete: hide the offer without touching its enrollment history."""
    await rbac_check(org_id, current_user, "delete", db_session)
    offer = await _get_offer_or_404(offer_id, org_id, db_session)
    offer.is_archived = True
    offer.is_publicly_listed = False
    offer.update_date = str(datetime.now())
    db_session.add(offer)
    await db_session.commit()


async def add_resource_to_offer(
    request: Request,
    org_id: int,
    offer_id: int,
    resource_uuid: str,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    await rbac_check(org_id, current_user, "update", db_session)
    offer = await _get_offer_or_404(offer_id, org_id, db_session)

    existing = (await db_session.execute(
        select(PaymentsOfferResource).where(
            PaymentsOfferResource.offer_id == offer_id,
            PaymentsOfferResource.resource_uuid == resource_uuid,
        )
    )).scalars().first()
    if not existing:
        db_session.add(PaymentsOfferResource(
            offer_id=offer_id, resource_uuid=resource_uuid, org_id=org_id,
            creation_date=str(datetime.now()),
        ))
        await db_session.commit()

    await add_resources_to_usergroup(request, db_session, current_user, offer.usergroup_id, resource_uuid)


async def remove_resource_from_offer(
    request: Request,
    org_id: int,
    offer_id: int,
    resource_uuid: str,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    await rbac_check(org_id, current_user, "update", db_session)
    offer = await _get_offer_or_404(offer_id, org_id, db_session)

    link = (await db_session.execute(
        select(PaymentsOfferResource).where(
            PaymentsOfferResource.offer_id == offer_id,
            PaymentsOfferResource.resource_uuid == resource_uuid,
        )
    )).scalars().first()
    if link:
        await db_session.delete(link)
        await db_session.commit()

    await remove_resources_from_usergroup(request, db_session, current_user, offer.usergroup_id, resource_uuid)


# --- Public (no-auth) reads --------------------------------------------------

async def get_public_offer(org_id: int, offer_id_or_uuid: str, db_session: AsyncSession) -> PaymentsOfferRead:
    offer = await _get_offer_or_404(offer_id_or_uuid, org_id, db_session)
    if offer.is_archived or not offer.is_publicly_listed:
        raise HTTPException(status_code=404, detail="Offer not found")
    return await _to_offer_read(offer, db_session)


async def get_public_offers_listing(org_id: int, db_session: AsyncSession) -> list[PaymentsOfferRead]:
    statement = select(PaymentsOffer).where(
        PaymentsOffer.org_id == org_id,
        PaymentsOffer.is_archived == False,
        PaymentsOffer.is_publicly_listed == True,
    ).order_by(PaymentsOffer.creation_date.desc())
    offers = (await db_session.execute(statement)).scalars().all()
    return [await _to_offer_read(o, db_session) for o in offers]


async def get_offers_by_resource(
    org_id: int,
    resource_uuid: str,
    db_session: AsyncSession,
    current_user: PublicUser | AnonymousUser | APITokenUser | None = None,
) -> list[PaymentsOfferRead]:
    """Every non-archived offer that grants access to a given resource,
    either directly (PaymentsOfferResource) or via its bundled group
    (PaymentsGroupResource) — used to show purchase options on a locked
    course/podcast/etc.

    current_user is optional (this is a public, unauthenticated-callable
    endpoint) — when a real user is present, each returned offer's
    has_access reflects whether THEY already have an active enrollment for
    it, so a caller can tell "already paid, just hasn't started yet" apart
    from "never paid" instead of conflating the two (see the mobile/desktop
    course-actions bug this fixed: both used "has a trail run" as a stand-in
    for "has access", so a buyer who paid but hadn't clicked Start yet was
    shown the buy-now prompt again)."""
    from src.db.payments.groups import PaymentsGroupResource

    direct_stmt = (
        select(PaymentsOffer)
        .join(PaymentsOfferResource, PaymentsOfferResource.offer_id == PaymentsOffer.id)
        .where(
            PaymentsOffer.org_id == org_id,
            PaymentsOffer.is_archived == False,
            PaymentsOfferResource.resource_uuid == resource_uuid,
        )
    )
    via_group_stmt = (
        select(PaymentsOffer)
        .join(PaymentsGroupResource, PaymentsGroupResource.group_id == PaymentsOffer.payments_group_id)
        .where(
            PaymentsOffer.org_id == org_id,
            PaymentsOffer.is_archived == False,
            PaymentsGroupResource.resource_uuid == resource_uuid,
        )
    )
    direct = (await db_session.execute(direct_stmt)).scalars().all()
    via_group = (await db_session.execute(via_group_stmt)).scalars().all()

    user_id = current_user.id if isinstance(current_user, (PublicUser, APITokenUser)) else None

    seen_ids: set[int] = set()
    result: list[PaymentsOfferRead] = []
    for offer in [*direct, *via_group]:
        if offer.id in seen_ids:
            continue
        seen_ids.add(offer.id)
        offer_read = await _to_offer_read(offer, db_session)
        if user_id is not None and offer.id is not None:
            from src.services.payments.enrollments import has_active_enrollment
            offer_read.has_access = await has_active_enrollment(user_id, offer.id, db_session)
        result.append(offer_read)
    return result
