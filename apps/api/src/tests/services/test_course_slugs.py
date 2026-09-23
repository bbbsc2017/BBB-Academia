"""Course slugs: name-derived, stable, unique per org, resolvable by slug or legacy uuid."""

from datetime import UTC, datetime

import pytest
from sqlmodel import select

from src.db.courses.courses import Course
from src.services.courses.slugs import (
    backfill_course_slugs,
    generate_unique_slug,
    resolve_course_identifier,
    slugify,
)

_UUID = "0b1f3c52-7a4e-4c1d-9d3a-1f2e3d4c5b6a"


def _course(org, name, uuid, slug=None, id=None):
    now = str(datetime.now(UTC))
    return Course(
        id=id,
        name=name,
        public=True,
        published=True,
        open_to_contributors=False,
        org_id=org.id,
        course_uuid=uuid,
        slug=slug,
        creation_date=now,
        update_date=now,
    )


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Curso de Programación Básica", "curso-de-programacion-basica"),
        ("  ¡Hola, Mundo! 2026  ", "hola-mundo-2026"),
        ("Ñandú & Café", "nandu-cafe"),
        ("!!!", ""),
        ("", ""),
    ],
)
def test_slugify(name, expected):
    assert slugify(name) == expected


def test_slugify_truncates_without_trailing_hyphen():
    slug = slugify("palabra " * 40)
    assert len(slug) <= 80
    assert not slug.endswith("-")


@pytest.mark.asyncio
async def test_generate_unique_slug_appends_counter_on_collision(db, org):
    db.add(_course(org, "Intro", "course_a", slug="intro"))
    db.add(_course(org, "Intro", "course_b", slug="intro-2"))
    await db.commit()
    assert await generate_unique_slug(db, org.id, "Intro") == "intro-3"


@pytest.mark.asyncio
async def test_generate_unique_slug_falls_back_when_name_has_no_usable_chars(db, org):
    assert await generate_unique_slug(db, org.id, "!!!") == "curso"


@pytest.mark.asyncio
async def test_generate_unique_slug_never_looks_like_a_uuid(db, org):
    slug = await generate_unique_slug(db, org.id, _UUID)
    assert slug == f"curso-{_UUID}"


@pytest.mark.asyncio
async def test_backfill_assigns_slugs_and_keeps_existing(db, org):
    db.add(_course(org, "Mi Curso", "course_1"))
    db.add(_course(org, "Mi Curso", "course_2"))
    db.add(_course(org, "Otro", "course_3", slug="ya-tiene"))
    await db.commit()

    assert await backfill_course_slugs(db) == 2
    slugs = {
        c.course_uuid: c.slug
        for c in (await db.execute(select(Course))).scalars().all()
    }
    assert slugs == {"course_1": "mi-curso", "course_2": "mi-curso-2", "course_3": "ya-tiene"}
    assert await backfill_course_slugs(db) == 0


@pytest.mark.asyncio
async def test_resolve_by_slug_and_by_legacy_uuid(db, org):
    db.add(_course(org, "Mi Curso", f"course_{_UUID}", slug="mi-curso"))
    await db.commit()

    by_slug = await resolve_course_identifier(db, org.slug, "mi-curso")
    by_uuid = await resolve_course_identifier(db, org.slug, _UUID)
    by_prefixed = await resolve_course_identifier(db, org.slug, f"course_{_UUID}")
    assert by_slug is not None and by_uuid is not None and by_prefixed is not None
    assert by_slug.course_uuid == by_uuid.course_uuid == by_prefixed.course_uuid == f"course_{_UUID}"


@pytest.mark.asyncio
async def test_resolve_backfills_missing_slug_on_uuid_lookup(db, org):
    db.add(_course(org, "Sin Slug", f"course_{_UUID}"))
    await db.commit()
    course = await resolve_course_identifier(db, org.slug, _UUID)
    assert course.slug == "sin-slug"


@pytest.mark.asyncio
async def test_resolve_unknown_or_other_org_returns_none(db, org, other_org):
    db.add(_course(org, "Mi Curso", f"course_{_UUID}", slug="mi-curso"))
    await db.commit()
    assert await resolve_course_identifier(db, org.slug, "no-existe") is None
    assert await resolve_course_identifier(db, "org-inexistente", "mi-curso") is None
    assert await resolve_course_identifier(db, other_org.slug, "mi-curso") is None
    assert await resolve_course_identifier(db, other_org.slug, _UUID) is None
