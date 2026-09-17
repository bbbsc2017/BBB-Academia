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

import base64
import binascii
import logging
import os
import random
import re
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi import Request
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.organizations import Organization
from src.db.user_organizations import UserOrganization
from src.db.users import AnonymousUser, User, UserCreate
from src.security.file_validation import (
    MIME_TO_SAFE_EXT,
    get_safe_filename,
    validate_image_content,
)
from src.security.rbac.constants import ADMIN_ROLE_ID, MAINTAINER_ROLE_ID
from src.services.users.users import create_user
from src.services.utils.upload_content import upload_content

logger = logging.getLogger(__name__)

# Global default role ids seeded by src/services/setup/setup.py — must stay
# in sync with that seed order (Admin=1, Maintainer=2, Instructor=3, User=4).
# ADMIN_ROLE_ID/MAINTAINER_ROLE_ID are the canonical constants (imported, not
# redefined); INSTRUCTOR/LEARNER have no canonical constant elsewhere in the
# codebase yet, so they stay local to this module.
BBBSC_ADMIN_ROLE_ID = ADMIN_ROLE_ID
BBBSC_MAINTAINER_ROLE_ID = MAINTAINER_ROLE_ID
BBBSC_INSTRUCTOR_ROLE_ID = 3
BBBSC_LEARNER_ROLE_ID = 4

_BBBSC_AVATAR_PATTERN = re.compile(
    r"^data:(image/(?:jpeg|png|gif|webp));base64,([A-Za-z0-9+/=\s]+)$",
    re.IGNORECASE,
)
_MAX_BBBSC_AVATAR_BYTES = 15 * 1024 * 1024


async def _store_bbbsc_avatar(data_uri: str | None, user_uuid: str) -> str | None:
    """Store a bbbsc data-URI avatar in LearnHouse's user media storage.

    bbbsc stores profile images as data URIs. LearnHouse serves local avatars
    by filename, so retaining the data URI in ``avatar_image`` would produce
    a broken image. Invalid or unavailable images are intentionally ignored so
    they can never prevent a participant from being imported.
    """
    if not data_uri or not isinstance(data_uri, str):
        return None

    match = _BBBSC_AVATAR_PATTERN.fullmatch(data_uri.strip())
    if not match:
        logger.warning("Ignoring invalid bbbsc avatar for user %s", user_uuid)
        return None

    content_type = match.group(1).lower()
    if content_type not in MIME_TO_SAFE_EXT:
        return None

    encoded = re.sub(r"\s+", "", match.group(2))
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        logger.warning("Ignoring malformed bbbsc avatar for user %s", user_uuid)
        return None

    if (
        not content
        or len(content) > _MAX_BBBSC_AVATAR_BYTES
        or not validate_image_content(content)
    ):
        logger.warning("Ignoring invalid bbbsc avatar content for user %s", user_uuid)
        return None

    filename = get_safe_filename(
        "", f"{uuid4()}_bbbsc_avatar", content_type=content_type
    )
    try:
        await upload_content(
            directory="avatars",
            type_of_dir="users",
            uuid=user_uuid,
            file_binary=content,
            file_and_format=filename,
        )
    except Exception:
        logger.warning(
            "Could not store bbbsc avatar for user %s", user_uuid, exc_info=True
        )
        return None

    return filename


async def verify_bbbsc_credentials(email: str, password: str) -> dict | None:
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

    # NestJS's @Post() defaults to 201 Created (no @HttpCode override on the
    # bbbsc side), so accept any 2xx rather than requiring exactly 200.
    if r.status_code < 200 or r.status_code >= 300:
        return None

    body = r.json()
    if not body.get("valid"):
        return None
    return body.get("user")


async def fetch_bbbsc_participants(
    page: int = 1, limit: int = 50, search: str = ""
) -> dict | None:
    """
    Ask bbbsc for a page of its "Participante" (role=STUDENT) users, for the
    LearnHouse dashboard's bulk-import feature. Same defensive posture as
    verify_bbbsc_credentials: never raises, returns None on any misconfiguration
    or network/HTTP error so the caller can surface a clean "bbbsc unreachable"
    message instead of a stack trace.
    """
    api_url = os.environ.get("BBBSC_API_URL")
    secret = os.environ.get("BBBSC_INTEGRATION_SECRET")
    if not api_url or not secret:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{api_url.rstrip('/')}/integrations/learnhouse/participants",
                params={"page": page, "limit": limit, "search": search},
                headers={"X-Internal-Secret": secret},
            )
    except httpx.HTTPError:
        logger.warning("bbbsc participants endpoint unreachable")
        return None

    if r.status_code < 200 or r.status_code >= 300:
        logger.warning("bbbsc participants endpoint returned %s", r.status_code)
        return None

    return r.json()


async def _get_default_org_id(db_session: AsyncSession) -> int | None:
    """Same lookup as GET /instance/info: slug=='default', else first org."""
    stmt = select(Organization).where(Organization.slug == "default")
    org = (await db_session.execute(stmt)).scalars().first()
    if not org:
        stmt = select(Organization).order_by(Organization.id).limit(1)
        org = (await db_session.execute(stmt)).scalars().first()
    return org.id if org else None


def _role_id_for_bbbsc_roles(roles: list) -> int:
    roles = roles or []
    # SUPER_ADMIN gets full, unrestricted control of LearnHouse (courses,
    # users, roles, org settings — everything), same as they already have
    # in bbbsc. INSTRUCTOR (without SUPER_ADMIN) is scoped to course
    # authoring only, per the Instructor role's rights in setup.py.
    if "SUPER_ADMIN" in roles:
        return BBBSC_ADMIN_ROLE_ID
    if "INSTRUCTOR" in roles:
        return BBBSC_INSTRUCTOR_ROLE_ID
    return BBBSC_LEARNER_ROLE_ID


async def _sync_membership_role(
    db_session: AsyncSession, user_id: int, org_id: int, role_id: int
) -> None:
    membership = (await db_session.execute(
        select(UserOrganization).where(
            (UserOrganization.user_id == user_id) & (UserOrganization.org_id == org_id)
        )
    )).scalars().first()
    now = str(datetime.now(UTC))
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
    *,
    role_id: int | None = None,
    sync_role: bool = True,
) -> User | None:
    """
    Find-or-create the LearnHouse User matching a bbbsc account.

    role_id: the LearnHouse role id to apply, already resolved by the caller
        (the push path — see ``/integrations/bbbsc/sync-role``). If omitted,
        falls back to ``_role_id_for_bbbsc_roles(bbbsc_user["roles"])`` — the
        pull-at-login path, kept for backward compatibility with a bbbsc
        deployment that hasn't started sending a precomputed role id yet.
    sync_role: if False, an EXISTING user's role is left untouched. Used by
        the course-assign flow (``/integrations/bbbsc/assign``), which must
        never demote an Admin/Instructor to Learner just because a course was
        granted to them — only an explicit role sync (login, or
        ``/integrations/bbbsc/sync-role``) should touch role_id. Does not
        affect a brand-new user's initial role, which is always applied.
    """
    email = (bbbsc_user.get("email") or "").strip().lower()
    if not email:
        return None

    org_id = await _get_default_org_id(db_session)
    if org_id is None:
        return None

    resolved_role_id = (
        role_id
        if role_id is not None
        else _role_id_for_bbbsc_roles(bbbsc_user.get("roles") or [])
    )

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
        avatar_filename = await _store_bbbsc_avatar(
            bbbsc_user.get("profileImageUrl"), user.user_uuid
        )
        if avatar_filename:
            user.avatar_image = avatar_filename
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)
        if resolved_role_id != BBBSC_LEARNER_ROLE_ID:
            # create_user always links with role_id=4; bump if bbbsc already
            # marked this account with a higher role at signup/assign time.
            await _sync_membership_role(db_session, user.id, org_id, resolved_role_id)
        return user

    if sync_role:
        await _sync_membership_role(db_session, user.id, org_id, resolved_role_id)

    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = datetime.now(UTC).isoformat()
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

    return user
