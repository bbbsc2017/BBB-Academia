"""
Delegated authentication against bbbsc (C:\\Users\\xBills\\bbbsc).

bbbsc is where every user (student or staff) is actually registered. Rather
than maintaining a second password for LearnHouse, ``authenticate_user`` in
``src/security/auth.py`` falls back to this module whenever a local lookup
fails, so the SAME email/password a user already has in bbbsc logs them into
LearnHouse transparently — no separate signup, no extra button.

Mirrors the JIT-provisioning pattern already used for Google OAuth
(``signWithGoogle`` in ``src/services/auth/utils.py``): find-or-create a
LearnHouse ``User`` keyed by email, reusing ``create_user`` so the normal
signup side-effects (default org membership, welcome email, deployment-mode
email-verification rules) stay identical to any other signup path.
"""

import logging
import os
import random
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Request
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.organizations import Organization
from src.db.user_organizations import UserOrganization
from src.db.users import AnonymousUser, User, UserCreate
from src.services.users.users import create_user

logger = logging.getLogger(__name__)

# Global default role ids seeded by src/services/setup/setup.py — must stay
# in sync with that seed order (Admin=1, Maintainer=2, Instructor=3, User=4).
BBBSC_INSTRUCTOR_ROLE_ID = 3
BBBSC_LEARNER_ROLE_ID = 4


async def verify_bbbsc_credentials(email: str, password: str) -> Optional[dict]:
    """
    Ask bbbsc's internal endpoint whether (email, password) is a valid,
    active bbbsc account. Returns the bbbsc user dict on success, else None.
    Never raises — any failure (misconfiguration, network, bad credentials)
    is treated as "not a bbbsc user" so the caller falls through to the
    normal 401.
    """
    api_url = os.environ.get("BBBSC_API_URL")
    secret = os.environ.get("BBBSC_INTEGRATION_SECRET")
    if not api_url or not secret:
        return None

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(
                f"{api_url.rstrip('/')}/integrations/learnhouse/verify-credentials",
                json={"email": email, "password": password},
                headers={"X-Internal-Secret": secret},
            )
    except httpx.HTTPError:
        logger.warning("bbbsc credential verification endpoint unreachable")
        return None

    if r.status_code != 200:
        return None

    body = r.json()
    if not body.get("valid"):
        return None
    return body.get("user")


async def _get_default_org_id(db_session: AsyncSession) -> Optional[int]:
    """Same lookup as GET /instance/info: slug=='default', else first org."""
    stmt = select(Organization).where(Organization.slug == "default")
    org = (await db_session.execute(stmt)).scalars().first()
    if not org:
        stmt = select(Organization).order_by(Organization.id).limit(1)
        org = (await db_session.execute(stmt)).scalars().first()
    return org.id if org else None


def _role_id_for_bbbsc_roles(roles: list) -> int:
    return BBBSC_INSTRUCTOR_ROLE_ID if "INSTRUCTOR" in (roles or []) else BBBSC_LEARNER_ROLE_ID


async def _sync_membership_role(
    db_session: AsyncSession, user_id: int, org_id: int, role_id: int
) -> None:
    membership = (await db_session.execute(
        select(UserOrganization).where(
            (UserOrganization.user_id == user_id) & (UserOrganization.org_id == org_id)
        )
    )).scalars().first()
    now = str(datetime.now())
    if not membership:
        db_session.add(UserOrganization(
            user_id=user_id, org_id=org_id, role_id=role_id,
            creation_date=now, update_date=now,
        ))
        await db_session.commit()
    elif membership.role_id != role_id:
        membership.role_id = role_id
        membership.update_date = now
        db_session.add(membership)
        await db_session.commit()


async def provision_or_sync_bbbsc_user(
    request: Request,
    db_session: AsyncSession,
    bbbsc_user: dict,
) -> Optional[User]:
    """
    Find-or-create the LearnHouse User matching a bbbsc account, and keep its
    org membership role in sync with bbbsc's INSTRUCTOR flag on every call
    (a docente promoted/demoted in bbbsc takes effect on next login).
    """
    email = (bbbsc_user.get("email") or "").strip().lower()
    if not email:
        return None

    org_id = await _get_default_org_id(db_session)
    if org_id is None:
        return None

    role_id = _role_id_for_bbbsc_roles(bbbsc_user.get("roles") or [])

    user = (await db_session.execute(
        select(User).where(func.lower(User.email) == email)
    )).scalars().first()

    if not user:
        first_name = bbbsc_user.get("firstName") or ""
        last_name = bbbsc_user.get("lastName") or ""
        name_parts = [p for p in (first_name, last_name) if p]
        if not name_parts:
            name_parts = [email.split("@")[0] if "@" in email else "user"]
        # Wide random suffix — same collision-avoidance reasoning as
        # signWithGoogle: a narrow suffix makes collisions likely for common
        # names, and a collision here would 400 on username instead of email.
        username = "".join(name_parts) + str(random.randint(100000, 999999))

        user_object = UserCreate(
            email=email,
            username=username,
            password="",
            first_name=first_name,
            last_name=last_name,
        )
        # AnonymousUser as the acting principal: create_user's rbac_check
        # short-circuits to allow "create user_x" for anonymous callers
        # (the same self-signup permission any new account goes through).
        await create_user(
            request, db_session, AnonymousUser(), user_object, org_id,
            is_oauth=True, signup_provider="bbbsc",
        )
        user = (await db_session.execute(
            select(User).where(func.lower(User.email) == email)
        )).scalars().first()
        if user is None:
            return None
        if role_id != BBBSC_LEARNER_ROLE_ID:
            # create_user always links with role_id=4; bump to Instructor if
            # bbbsc already marked this account as INSTRUCTOR at signup time.
            await _sync_membership_role(db_session, user.id, org_id, role_id)
        return user

    await _sync_membership_role(db_session, user.id, org_id, role_id)

    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc).isoformat()
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

    return user
