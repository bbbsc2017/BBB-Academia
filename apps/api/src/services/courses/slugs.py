"""
Human-readable course slugs (``/course/mi-curso`` instead of ``/course/<uuid>``).

Slugs are derived from the course name once, then stay stable when the course
is renamed so links already printed (QR codes, flyers) never break. The old
uuid-based URLs keep working: the frontend proxy redirects them to the slug.
"""

import re
import unicodedata
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.courses import Course
from src.db.organizations import Organization

MAX_SLUG_LENGTH = 80


def slugify(name: str) -> str:
    """Lowercase, accent-stripped, hyphen-separated ASCII slug ('' if nothing usable)."""
    text = unicodedata.normalize("NFKD", name or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = text[:MAX_SLUG_LENGTH].strip("-")
    return text


def looks_like_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def clean_course_uuid(value: str) -> str:
    return value.removeprefix("course_")


async def generate_unique_slug(
    db_session: AsyncSession,
    org_id: int,
    name: str,
    exclude_course_id: int | None = None,
) -> str:
    base = slugify(name) or "curso"
    # A uuid-shaped slug would be indistinguishable from a legacy uuid URL.
    if looks_like_uuid(base):
        base = f"curso-{base}"

    query = select(Course.slug).where(Course.org_id == org_id)
    if exclude_course_id is not None:
        query = query.where(Course.id != exclude_course_id)
    taken = {s for s in (await db_session.execute(query)).scalars().all() if s}

    candidate = base
    counter = 2
    while candidate in taken:
        suffix = f"-{counter}"
        candidate = f"{base[: MAX_SLUG_LENGTH - len(suffix)]}{suffix}"
        counter += 1
    return candidate


async def assign_course_slug(db_session: AsyncSession, course: Course) -> None:
    """Set ``course.slug`` from its name if it has none (caller adds/commits)."""
    if course.slug:
        return
    course.slug = await generate_unique_slug(
        db_session, course.org_id, course.name, exclude_course_id=course.id
    )


async def backfill_course_slugs(db_session: AsyncSession) -> int:
    """Give every course that has no slug one. Idempotent; returns how many."""
    courses = (
        await db_session.execute(
            select(Course).where(Course.slug.is_(None)).order_by(Course.id)  # type: ignore[union-attr]
        )
    ).scalars().all()
    for course in courses:
        await assign_course_slug(db_session, course)
        db_session.add(course)
        # Flush per course so the next one sees this slug as taken.
        await db_session.flush()
    await db_session.commit()
    return len(courses)


async def resolve_course_identifier(
    db_session: AsyncSession, org_slug: str, identifier: str
) -> Course | None:
    """Find a course in an org by slug, by uuid, or by ``course_<uuid>``."""
    org = (
        await db_session.execute(select(Organization).where(Organization.slug == org_slug))
    ).scalars().first()
    if not org:
        return None

    # Slugs never contain "_", so a "course_" prefix or a bare uuid is a legacy id.
    if identifier.startswith("course_") or looks_like_uuid(identifier):
        course = (
            await db_session.execute(
                select(Course).where(
                    Course.org_id == org.id,
                    Course.course_uuid == f"course_{clean_course_uuid(identifier)}",
                )
            )
        ).scalars().first()
    else:
        course = (
            await db_session.execute(
                select(Course).where(Course.org_id == org.id, Course.slug == identifier)
            )
        ).scalars().first()

    if course and not course.slug:
        await assign_course_slug(db_session, course)
        db_session.add(course)
        await db_session.commit()
        await db_session.refresh(course)
    return course
