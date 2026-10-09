"""
Once HLS transcoding is "ready" for a video, the raw progressive MP4 is a
single unprotected file (no per-session TTL, no AES-128 encryption) — serving
it would defeat the point of encrypted HLS. `_mp4_locked` / the raw MP4 GET and
HEAD endpoints in src/routers/stream.py must refuse ordinary viewers once a
protected rendition exists, while staff who manage the course (re-upload,
verify, debug) keep direct access.
"""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.db.courses.blocks import Block
from src.routers import stream as stream_mod
from src.routers.stream import router as stream_router
from src.security.auth import get_current_user


def _make_app(db, user):
    app = FastAPI()
    app.include_router(stream_router)
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return app


@pytest.fixture
async def client_factory(db):
    clients = []

    async def _factory(user):
        app = _make_app(db, user)
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(c)
        return c

    yield _factory
    for c in clients:
        await c.aclose()


@pytest.fixture
async def ready_block(db, org, course, activity):
    b = Block(
        block_type="BLOCK_VIDEO",
        content={"filename": "v.mp4", "hls": {"status": "ready"}},
        org_id=org.id,
        course_id=course.id,
        chapter_id=None,
        activity_id=activity.id,
        block_uuid="blk_ready",
        creation_date=str(datetime.now(UTC)),
        update_date=str(datetime.now(UTC)),
    )
    db.add(b)
    await db.commit()
    return b


# ---------------------------------------------------------------------------
# Unit tests for the pure helper
# ---------------------------------------------------------------------------

def test_mp4_locked_false_when_hls_disabled(monkeypatch):
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: False)
    assert stream_mod._mp4_locked({"status": "ready"}, can_manage=False) is False


def test_mp4_locked_false_when_can_manage(monkeypatch):
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: True)
    assert stream_mod._mp4_locked({"status": "ready"}, can_manage=True) is False


def test_mp4_locked_false_when_not_ready(monkeypatch):
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: True)
    for holder in (None, {}, {"status": "processing"}, {"status": "failed"}):
        assert stream_mod._mp4_locked(holder, can_manage=False) is False


def test_mp4_locked_true_when_ready_and_cannot_manage(monkeypatch):
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: True)
    assert stream_mod._mp4_locked({"status": "ready"}, can_manage=False) is True


# ---------------------------------------------------------------------------
# Router: activity (top-level hosted video) MP4 endpoints
# ---------------------------------------------------------------------------

async def test_activity_mp4_blocked_for_regular_user_once_hls_ready(
    client_factory, monkeypatch, db, org, course, chapter, activity, regular_user
):
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "get_file_info", lambda p: (1000, "video/mp4", True))
    activity.extra_metadata = {"hls": {"status": "ready"}}
    db.add(activity)
    await db.commit()

    client = await client_factory(regular_user)
    url = f"/video/{org.org_uuid}/{course.course_uuid}/{activity.activity_uuid}/clip.mp4"
    get_resp = await client.get(url, follow_redirects=False)
    head_resp = await client.head(url, follow_redirects=False)
    assert get_resp.status_code == 403
    assert head_resp.status_code == 403


async def test_activity_mp4_blocked_for_anonymous_on_public_course_once_hls_ready(
    client_factory, monkeypatch, db, org, course, chapter, activity, anonymous_user
):
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "get_file_info", lambda p: (1000, "video/mp4", True))
    activity.extra_metadata = {"hls": {"status": "ready"}}
    db.add(activity)
    await db.commit()

    client = await client_factory(anonymous_user)
    url = f"/video/{org.org_uuid}/{course.course_uuid}/{activity.activity_uuid}/clip.mp4"
    r = await client.get(url, follow_redirects=False)
    assert r.status_code == 403


async def test_activity_mp4_allowed_for_admin_once_hls_ready(
    client_factory, monkeypatch, db, org, course, chapter, activity, admin_user
):
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "get_file_info", lambda p: (1000, "video/mp4", True))
    monkeypatch.setattr(stream_mod, "is_s3_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "generate_presigned_get_url", lambda k: f"https://r2/{k}")
    activity.extra_metadata = {"hls": {"status": "ready"}}
    db.add(activity)
    await db.commit()

    client = await client_factory(admin_user)
    url = f"/video/{org.org_uuid}/{course.course_uuid}/{activity.activity_uuid}/clip.mp4"
    r = await client.get(url, follow_redirects=False)
    assert r.status_code == 302


async def test_activity_mp4_allowed_when_hls_disabled_even_if_marked_ready(
    client_factory, monkeypatch, db, org, course, chapter, activity, regular_user
):
    # Stale "ready" metadata from a prior deployment where HLS was on must not
    # lock viewers out once the operator has turned HLS back off.
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: False)
    monkeypatch.setattr(stream_mod, "get_file_info", lambda p: (1000, "video/mp4", True))
    monkeypatch.setattr(stream_mod, "is_s3_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "generate_presigned_get_url", lambda k: f"https://r2/{k}")
    activity.extra_metadata = {"hls": {"status": "ready"}}
    db.add(activity)
    await db.commit()

    client = await client_factory(regular_user)
    url = f"/video/{org.org_uuid}/{course.course_uuid}/{activity.activity_uuid}/clip.mp4"
    r = await client.get(url, follow_redirects=False)
    assert r.status_code == 302


async def test_activity_mp4_allowed_while_hls_still_processing(
    client_factory, monkeypatch, db, org, course, chapter, activity, regular_user
):
    # Mid-transcode: no protected rendition exists yet, so the MP4 fallback
    # must stay reachable or playback would break for everyone.
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "get_file_info", lambda p: (1000, "video/mp4", True))
    monkeypatch.setattr(stream_mod, "is_s3_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "generate_presigned_get_url", lambda k: f"https://r2/{k}")
    activity.extra_metadata = {"hls": {"status": "processing"}}
    db.add(activity)
    await db.commit()

    client = await client_factory(regular_user)
    url = f"/video/{org.org_uuid}/{course.course_uuid}/{activity.activity_uuid}/clip.mp4"
    r = await client.get(url, follow_redirects=False)
    assert r.status_code == 302


# ---------------------------------------------------------------------------
# Router: video-block MP4 endpoints
# ---------------------------------------------------------------------------

async def test_block_mp4_blocked_for_regular_user_once_hls_ready(
    client_factory, monkeypatch, org, course, chapter, activity, ready_block, regular_user
):
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "get_file_info", lambda p: (1000, "video/mp4", True))

    client = await client_factory(regular_user)
    url = f"/block/{org.org_uuid}/{course.course_uuid}/{activity.activity_uuid}/{ready_block.block_uuid}/v.mp4"
    get_resp = await client.get(url, follow_redirects=False)
    head_resp = await client.head(url, follow_redirects=False)
    assert get_resp.status_code == 403
    assert head_resp.status_code == 403


async def test_block_mp4_allowed_for_admin_once_hls_ready(
    client_factory, monkeypatch, org, course, chapter, activity, ready_block, admin_user
):
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "get_file_info", lambda p: (1000, "video/mp4", True))
    monkeypatch.setattr(stream_mod, "is_s3_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "generate_presigned_get_url", lambda k: f"https://r2/{k}")

    client = await client_factory(admin_user)
    url = f"/block/{org.org_uuid}/{course.course_uuid}/{activity.activity_uuid}/{ready_block.block_uuid}/v.mp4"
    r = await client.get(url, follow_redirects=False)
    assert r.status_code == 302


async def test_block_mp4_allowed_for_unrelated_block_uuid(
    client_factory, monkeypatch, org, course, chapter, activity, regular_user
):
    # No Block row matches this block_uuid (e.g. legacy content predating the
    # Block table) — must not crash and must not lock out by default.
    monkeypatch.setattr(stream_mod, "hls_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "get_file_info", lambda p: (1000, "video/mp4", True))
    monkeypatch.setattr(stream_mod, "is_s3_enabled", lambda: True)
    monkeypatch.setattr(stream_mod, "generate_presigned_get_url", lambda k: f"https://r2/{k}")

    client = await client_factory(regular_user)
    url = f"/block/{org.org_uuid}/{course.course_uuid}/{activity.activity_uuid}/blk_missing/v.mp4"
    r = await client.get(url, follow_redirects=False)
    assert r.status_code == 302
