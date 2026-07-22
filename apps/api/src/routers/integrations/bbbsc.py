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

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.courses.courses import Course
from src.db.usergroup_user import UserGroupUser
from src.db.usergroups import UserGroup, UserGroupCreate
from src.db.users import APITokenUser
from src.security.auth import get_current_user
from src.services.auth.bbbsc import provision_or_sync_bbbsc_user
from src.services.courses.lock_usergroups import _attach_usergroup
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

    # Reuses the same JIT-provisioning path as first login via bbbsc — a bare
    # roles=[] maps to the default learner role (see _role_id_for_bbbsc_roles).
    user = await provision_or_sync_bbbsc_user(
        request,
        db_session,
        {
            "email": payload.student_email,
            "firstName": payload.first_name,
            "lastName": payload.last_name,
            "roles": [],
        },
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
        from datetime import datetime
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
