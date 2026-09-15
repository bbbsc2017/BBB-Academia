import logging

from fastapi import HTTPException, Request
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.organizations import Organization
from src.db.users import AnonymousUser, PublicUser, User
from src.security.auth import resolve_acting_user_id
from src.security.org_auth import is_org_admin, is_org_member
from src.services.auth.bbbsc import fetch_bbbsc_participants, provision_or_sync_bbbsc_user

logger = logging.getLogger(__name__)


async def _require_org_admin(org_id: int, current_user, db_session: AsyncSession) -> Organization:
    if isinstance(current_user, AnonymousUser):
        raise HTTPException(status_code=401, detail="Authentication required")

    org = (await db_session.execute(
        select(Organization).where(Organization.id == org_id)
    )).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    acting_user_id = resolve_acting_user_id(current_user)
    if not await is_org_member(acting_user_id, org.id, db_session):
        raise HTTPException(status_code=403, detail="You must be a member of this organization")
    if not await is_org_admin(acting_user_id, org.id, db_session):
        raise HTTPException(
            status_code=403,
            detail="Only administrators and maintainers can import bbbsc participants",
        )
    return org


async def list_bbbsc_participants(
    request: Request,
    org_id: int,
    db_session: AsyncSession,
    current_user: PublicUser | AnonymousUser,
    page: int = 1,
    limit: int = 50,
    search: str = "",
) -> dict:
    await _require_org_admin(org_id, current_user, db_session)

    limit = min(limit, 100)
    page = max(page, 1)

    data = await fetch_bbbsc_participants(page=page, limit=limit, search=search)
    if data is None:
        raise HTTPException(
            status_code=502,
            detail="bbbsc is unreachable or not configured — try again later",
        )

    items = data.get("items", [])
    emails = [
        (item.get("email") or "").strip().lower()
        for item in items
        if item.get("email")
    ]

    existing_emails: set[str] = set()
    if emails:
        existing_users = (await db_session.execute(
            select(User.email).where(func.lower(User.email).in_(emails))
        )).scalars().all()
        existing_emails = {e.strip().lower() for e in existing_users if e}

    for item in items:
        email = (item.get("email") or "").strip().lower()
        item["already_exists_in_learnhouse"] = email in existing_emails

    return {
        "items": items,
        "total": data.get("total", len(items)),
        "page": data.get("page", page),
        "limit": data.get("limit", limit),
    }


async def import_bbbsc_participants(
    request: Request,
    org_id: int,
    participants: list[dict],
    db_session: AsyncSession,
    current_user: PublicUser | AnonymousUser,
) -> dict:
    await _require_org_admin(org_id, current_user, db_session)

    imported_user_ids: list[int] = []
    skipped: list[str] = []

    for participant in participants:
        email = (participant.get("email") or "").strip()
        if not email:
            continue
        try:
            user = await provision_or_sync_bbbsc_user(
                request, db_session, participant, sync_role=False
            )
        except Exception:
            logger.exception("Failed to import bbbsc participant %s", email)
            user = None

        if user is None:
            skipped.append(email)
        else:
            imported_user_ids.append(user.id)

    return {
        "detail": f"{len(imported_user_ids)} participant(s) imported",
        "imported_user_ids": imported_user_ids,
        "skipped_emails": skipped,
    }
