from datetime import datetime
from typing import Literal
from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.security.org_auth import require_org_membership, require_org_role_permission
from src.security.rbac.rbac import authorization_verify_if_user_is_anon
from src.security.superadmin import is_user_superadmin
from src.db.organizations import Organization
from src.db.usergroups import UserGroup
from src.db.users import AnonymousUser, APITokenUser, InternalUser, PublicUser
from src.db.payments.groups import (
    PaymentsGroup,
    PaymentsGroupCreate,
    PaymentsGroupRead,
    PaymentsGroupResource,
    PaymentsGroupUpdate,
)

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


async def _get_group_or_404(group_id: int, org_id: int, db_session: AsyncSession) -> PaymentsGroup:
    group = (await db_session.execute(
        select(PaymentsGroup).where(PaymentsGroup.id == group_id, PaymentsGroup.org_id == org_id)
    )).scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Payments group not found")
    return group


async def get_groups(
    request: Request,
    org_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> list[PaymentsGroupRead]:
    await rbac_check(org_id, current_user, "read", db_session)
    statement = select(PaymentsGroup).where(PaymentsGroup.org_id == org_id).order_by(PaymentsGroup.creation_date.desc())
    groups = (await db_session.execute(statement)).scalars().all()
    return [PaymentsGroupRead.model_validate(g) for g in groups]


async def create_group(
    request: Request,
    org_id: int,
    group_create: PaymentsGroupCreate,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> PaymentsGroupRead:
    await rbac_check(org_id, current_user, "create", db_session)
    await require_org_membership(
        current_user.created_by_user_id if isinstance(current_user, APITokenUser) else current_user.id,
        org_id, db_session,
    )

    org = (await db_session.execute(select(Organization).where(Organization.id == org_id))).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    group = PaymentsGroup(
        org_id=org_id,
        name=group_create.name,
        description=group_create.description or "",
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return PaymentsGroupRead.model_validate(group)


async def update_group(
    request: Request,
    org_id: int,
    group_id: int,
    group_update: PaymentsGroupUpdate,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> PaymentsGroupRead:
    await rbac_check(org_id, current_user, "update", db_session)
    group = await _get_group_or_404(group_id, org_id, db_session)

    update_data = group_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)
    group.update_date = str(datetime.now())

    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return PaymentsGroupRead.model_validate(group)


async def delete_group(
    request: Request,
    org_id: int,
    group_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    await rbac_check(org_id, current_user, "delete", db_session)
    group = await _get_group_or_404(group_id, org_id, db_session)
    await db_session.delete(group)
    await db_session.commit()


async def add_resource_to_group(
    request: Request,
    org_id: int,
    group_id: int,
    resource_uuid: str,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    await rbac_check(org_id, current_user, "update", db_session)
    await _get_group_or_404(group_id, org_id, db_session)

    existing = (await db_session.execute(
        select(PaymentsGroupResource).where(
            PaymentsGroupResource.group_id == group_id,
            PaymentsGroupResource.resource_uuid == resource_uuid,
        )
    )).scalars().first()
    if existing:
        return

    db_session.add(PaymentsGroupResource(
        group_id=group_id,
        resource_uuid=resource_uuid,
        org_id=org_id,
        creation_date=str(datetime.now()),
    ))
    await db_session.commit()


async def remove_resource_from_group(
    request: Request,
    org_id: int,
    group_id: int,
    resource_uuid: str,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    await rbac_check(org_id, current_user, "update", db_session)
    await _get_group_or_404(group_id, org_id, db_session)

    link = (await db_session.execute(
        select(PaymentsGroupResource).where(
            PaymentsGroupResource.group_id == group_id,
            PaymentsGroupResource.resource_uuid == resource_uuid,
        )
    )).scalars().first()
    if link:
        await db_session.delete(link)
        await db_session.commit()


async def get_group_resources(
    request: Request,
    org_id: int,
    group_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> list[str]:
    await rbac_check(org_id, current_user, "read", db_session)
    await _get_group_or_404(group_id, org_id, db_session)
    statement = select(PaymentsGroupResource).where(PaymentsGroupResource.group_id == group_id)
    links = (await db_session.execute(statement)).scalars().all()
    return [link.resource_uuid for link in links]


async def sync_group_usergroup(
    request: Request,
    org_id: int,
    group_id: int,
    usergroup_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> PaymentsGroupRead:
    """Link a PaymentsGroup to an existing (org-owned) UserGroup. Buying an
    offer that references this group will also add the buyer to that
    UserGroup — e.g. to grant a "VIP community" membership that isn't itself
    modeled as a PaymentsGroupResource."""
    await rbac_check(org_id, current_user, "update", db_session)
    group = await _get_group_or_404(group_id, org_id, db_session)

    usergroup = (await db_session.execute(
        select(UserGroup).where(UserGroup.id == usergroup_id, UserGroup.org_id == org_id)
    )).scalars().first()
    if not usergroup:
        raise HTTPException(status_code=404, detail="User group not found")

    group.usergroup_id = usergroup_id
    group.update_date = str(datetime.now())
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return PaymentsGroupRead.model_validate(group)


async def unsync_group_usergroup(
    request: Request,
    org_id: int,
    group_id: int,
    current_user: PublicUser | AnonymousUser | InternalUser | APITokenUser,
    db_session: AsyncSession,
) -> PaymentsGroupRead:
    await rbac_check(org_id, current_user, "update", db_session)
    group = await _get_group_or_404(group_id, org_id, db_session)
    group.usergroup_id = None
    group.update_date = str(datetime.now())
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return PaymentsGroupRead.model_validate(group)
