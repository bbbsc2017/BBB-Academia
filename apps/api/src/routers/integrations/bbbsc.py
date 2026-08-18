"""
bbbsc integration router.

Called by bbbsc_admin's "Cursos LearnHouse" screen (not the LearnHouse
dashboard) so staff can list LearnHouse courses and grant a specific course
to a specific student without leaving bbbsc_admin. Authenticated via an
org-scoped API token (``Authorization: Bearer lh_...``), same as the Zapier
integration — no plan gate, since this is core plumbing for how the org's
users get access, not an add-on.

Course access is modeled exactly like any other course-level grant: a
per-course UserGroup (created lazily, one per course) that the student is
added to, with a UserGroupResource linking that group to the course_uuid —
the same mechanism ``services/courses/lock_usergroups.py`` uses for locked
chapters/activities.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.courses.courses import Course
from src.db.roles import Role, RoleTypeEnum
from src.db.user_organizations import UserOrganization
from src.db.usergroup_user import UserGroupUser
from src.db.usergroups import UserGroup, UserGroupCreate
from src.db.users import APITokenUser, User
from src.security.auth import get_current_user
from src.services.auth.bbbsc import provision_or_sync_bbbsc_user
from src.services.courses.lock_usergroups import _attach_usergroup
from src.services.roles.roles import validate_rights_shape
from src.services.users.usergroups import create_usergroup

router = APIRouter()


def _require_api_token(current_user) -> APITokenUser:
    if not isinstance(current_user, APITokenUser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bbbsc integration endpoints require an API token (Authorization: Bearer lh_...)",
        )
    return current_user


async def _bbbsc_context(
    current_user=Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    api_user = _require_api_token(current_user)
    return api_user, db_session


class BbbscCourseItem(BaseModel):
    id: int
    course_uuid: str
    name: str


class BbbscAssignRequest(BaseModel):
    student_email: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    course_uuid: str


class BbbscAssignResponse(BaseModel):
    detail: str
    user_id: int
    usergroup_uuid: str


@router.get(
    "/courses",
    response_model=List[BbbscCourseItem],
    summary="List courses for bbbsc",
    description="List courses in the caller's organization, for the bbbsc_admin course picker.",
)
async def bbbsc_list_courses(
    limit: int = 100,
    ctx=Depends(_bbbsc_context),
) -> List[BbbscCourseItem]:
    api_user, db_session = ctx
    query = (
        select(Course)
        .where(Course.org_id == api_user.org_id)
        .order_by(Course.name)
        .limit(max(1, min(limit, 500)))
    )
    courses = (await db_session.execute(query)).scalars().all()
    return [
        BbbscCourseItem(id=c.id or 0, course_uuid=c.course_uuid, name=c.name)
        for c in courses
    ]


async def _get_or_create_course_usergroup(
    request: Request,
    db_session: AsyncSession,
    api_user: APITokenUser,
    course: Course,
) -> UserGroup:
    group_name = f"Curso: {course.name}"
    existing = (await db_session.execute(
        select(UserGroup).where(
            UserGroup.org_id == api_user.org_id,
            UserGroup.name == group_name,
        )
    )).scalars().first()
    if existing:
        return existing

    created = await create_usergroup(
        request,
        db_session,
        api_user,
        UserGroupCreate(
            name=group_name,
            description=f"Acceso automático al curso '{course.name}' (asignado desde bbbsc)",
            org_id=api_user.org_id,
        ),
    )
    group = (await db_session.execute(
        select(UserGroup).where(UserGroup.id == created.id)
    )).scalars().first()
    if not group:
        raise HTTPException(status_code=500, detail="Could not create course user group")
    return group


@router.post(
    "/assign",
    response_model=BbbscAssignResponse,
    summary="Assign a course to a student",
    description=(
        "Grant a student access to a specific course. JIT-provisions the LearnHouse "
        "user if they've never logged in yet (same provisioning path as first login "
        "via bbbsc credentials), then adds them to a per-course user group."
    ),
)
async def bbbsc_assign_course(
    request: Request,
    payload: BbbscAssignRequest,
    ctx=Depends(_bbbsc_context),
) -> BbbscAssignResponse:
    api_user, db_session = ctx

    course = (await db_session.execute(
        select(Course).where(
            Course.course_uuid == payload.course_uuid,
            Course.org_id == api_user.org_id,
        )
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Reuses the same JIT-provisioning path as first login via bbbsc — a
    # brand-new student defaults to the Learner role (see
    # _role_id_for_bbbsc_roles). sync_role=False: assigning a course must
    # NEVER touch the role of a student who already has an account — this
    # endpoint isn't a role sync, and previously passing "roles": [] here
    # would silently demote an existing Admin/Instructor to Learner.
    user = await provision_or_sync_bbbsc_user(
        request,
        db_session,
        {
            "email": payload.student_email,
            "firstName": payload.first_name,
            "lastName": payload.last_name,
        },
        sync_role=False,
    )
    if not user or user.id is None:
        raise HTTPException(status_code=500, detail="Could not provision student account")

    group = await _get_or_create_course_usergroup(request, db_session, api_user, course)

    existing_membership = (await db_session.execute(
        select(UserGroupUser).where(
            UserGroupUser.usergroup_id == group.id,
            UserGroupUser.user_id == user.id,
        )
    )).scalars().first()
    if not existing_membership:
        db_session.add(UserGroupUser(
            usergroup_id=group.id,
            user_id=user.id,
            org_id=api_user.org_id,
            creation_date=str(datetime.now()),
            update_date=str(datetime.now()),
        ))
        await db_session.commit()

    await _attach_usergroup(course.course_uuid, api_user.org_id, group.id, db_session)

    return BbbscAssignResponse(
        detail="Course assigned",
        user_id=user.id,
        usergroup_uuid=group.usergroup_uuid,
    )


async def _find_course_usergroup(
    db_session: AsyncSession,
    api_user: APITokenUser,
    course: Course,
) -> Optional[UserGroup]:
    """Read-only counterpart to ``_get_or_create_course_usergroup`` — used by
    unassign, which must never provision a group/course access that never
    existed in the first place."""
    return (await db_session.execute(
        select(UserGroup).where(
            UserGroup.org_id == api_user.org_id,
            UserGroup.name == f"Curso: {course.name}",
        )
    )).scalars().first()


class BbbscUnassignRequest(BaseModel):
    student_email: str
    course_uuid: str


class BbbscUnassignResponse(BaseModel):
    detail: str
    user_id: int


@router.post(
    "/unassign",
    response_model=BbbscUnassignResponse,
    summary="Revoke a student's access to a course",
    description=(
        "Remove a single student's access to a specific course. Only removes "
        "that student's own membership in the course's user group — other "
        "students granted the same course keep their access untouched."
    ),
)
async def bbbsc_unassign_course(
    payload: BbbscUnassignRequest,
    ctx=Depends(_bbbsc_context),
) -> BbbscUnassignResponse:
    api_user, db_session = ctx

    course = (await db_session.execute(
        select(Course).where(
            Course.course_uuid == payload.course_uuid,
            Course.org_id == api_user.org_id,
        )
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    email = payload.student_email.strip().lower()
    user = (await db_session.execute(
        select(User).where(func.lower(User.email) == email)
    )).scalars().first()
    if not user or user.id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    group = await _find_course_usergroup(db_session, api_user, course)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student has no access to this course")

    # Deletes only THIS student's membership row — the UserGroupResource
    # linking the group to the course stays intact, so every other student
    # granted access to the same course keeps it.
    membership = (await db_session.execute(
        select(UserGroupUser).where(
            UserGroupUser.usergroup_id == group.id,
            UserGroupUser.user_id == user.id,
        )
    )).scalars().first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student has no access to this course")

    await db_session.delete(membership)
    await db_session.commit()

    return BbbscUnassignResponse(detail="Course access revoked", user_id=user.id)


class BbbscSyncRoleRequest(BaseModel):
    email: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    learnhouse_role_id: int


class BbbscSyncRoleResponse(BaseModel):
    detail: str
    user_id: int
    role_id: int


@router.post(
    "/sync-role",
    response_model=BbbscSyncRoleResponse,
    summary="Push a user's LearnHouse role from bbbsc",
    description=(
        "Reflect a role change made in bbbsc immediately, instead of waiting "
        "for the user's next login. JIT-provisions the LearnHouse user if "
        "they've never logged in yet."
    ),
)
async def bbbsc_sync_role(
    request: Request,
    payload: BbbscSyncRoleRequest,
    ctx=Depends(_bbbsc_context),
) -> BbbscSyncRoleResponse:
    api_user, db_session = ctx

    user = await provision_or_sync_bbbsc_user(
        request,
        db_session,
        {
            "email": payload.email,
            "firstName": payload.first_name,
            "lastName": payload.last_name,
        },
        role_id=payload.learnhouse_role_id,
    )
    if not user or user.id is None:
        raise HTTPException(status_code=500, detail="Could not provision user")

    # Applies immediately: the RBAC engine resolves roles from the DB on
    # every request, gated only by this 10-minute session cache — without
    # invalidating it, the old role would still be honoured for up to 10
    # minutes after bbbsc pushed the change.
    from src.routers.users import _invalidate_session_cache
    _invalidate_session_cache(user.id)

    return BbbscSyncRoleResponse(
        detail="Role synced",
        user_id=user.id,
        role_id=payload.learnhouse_role_id,
    )


class BbbscSyncRoleRightsRequest(BaseModel):
    learnhouse_role_id: int
    rights: dict


class BbbscSyncRoleRightsResponse(BaseModel):
    detail: str
    role_id: int


@router.post(
    "/sync-role-rights",
    response_model=BbbscSyncRoleRightsResponse,
    summary="Push a global role's rights matrix from bbbsc",
    description=(
        "Overwrite the `rights` of one of LearnHouse's 4 fixed global roles "
        "(Admin=1, Maintainer=2, Instructor=3, User=4) with the payload bbbsc's "
        "admin defined for it. Writes directly to the Role table, bypassing the "
        "TYPE_GLOBAL edit guard in services/roles/roles.py — that guard exists "
        "to stop a human LearnHouse admin from editing these roles now that "
        "bbbsc owns their definition, not to block this sync."
    ),
)
async def bbbsc_sync_role_rights(
    payload: BbbscSyncRoleRightsRequest,
    ctx=Depends(_bbbsc_context),
) -> BbbscSyncRoleRightsResponse:
    # TYPE_GLOBAL roles have no org_id (they're shared, not per-org) — nothing
    # further to scope by org here; the API token itself is the authorization
    # boundary (enforced by _bbbsc_context/get_current_user).
    _, db_session = ctx

    role = (await db_session.execute(
        select(Role).where(
            Role.id == payload.learnhouse_role_id,
            Role.role_type == RoleTypeEnum.TYPE_GLOBAL,
        )
    )).scalars().first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Global role not found")

    # Deep-merge rather than overwrite: bbbsc's admin UI only exposes a subset
    # of LearnHouse's resources (courses, coursechapters, activities, media,
    # usergroups, roles, dashboard) — it deliberately doesn't manage
    # users/folders/organizations at the role-rights level — AND within a
    # resource it only ever sends the specific action(s) an admin actually
    # toggled (e.g. {"courses": {"action_create": true}}, not the full
    # 7-action shape). validate_rights_shape requires all 10 top-level keys
    # with their FULL action set, so both the resource-level and action-level
    # gaps are filled in from this role's current rights before validating —
    # a shallow merge would instead let a single-action payload wipe out every
    # other action already set for that resource.
    existing_rights = (
        role.rights
        if isinstance(role.rights, dict)
        else (role.rights.model_dump() if role.rights else {})
    )
    merged_rights = dict(existing_rights)
    for key, value in (payload.rights or {}).items():
        if isinstance(value, dict) and isinstance(merged_rights.get(key), dict):
            merged_rights[key] = {**merged_rights[key], **value}
        else:
            merged_rights[key] = value
    rights_dict = validate_rights_shape(merged_rights)

    role.rights = rights_dict
    role.update_date = str(datetime.now())
    db_session.add(role)
    await db_session.commit()

    # Invalidate every affected user's session cache so the new rights apply
    # on their very next request, not after a 10-minute cache expiry.
    from src.routers.users import _invalidate_session_cache
    affected_user_ids = (await db_session.execute(
        select(UserOrganization.user_id).where(UserOrganization.role_id == role.id)
    )).scalars().all()
    for uid in affected_user_ids:
        _invalidate_session_cache(uid)

    return BbbscSyncRoleRightsResponse(detail="Role rights synced", role_id=role.id)
