"""Tests for src/services/courses/activities/video.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from src.services.courses.activities.video import (
    ExternalVideo,
    create_external_video_activity,
    create_video_activity,
    update_video_activity,
)


def _mock_video_file(content_type: str = "video/mp4", filename: str = "test.mp4") -> MagicMock:
    uf = MagicMock(spec=UploadFile)
    uf.content_type = content_type
    uf.filename = filename
    return uf


class TestCreateVideoActivity:
    @pytest.mark.asyncio
    async def test_raises_404_when_chapter_not_found(
        self, mock_request, db, org, admin_user
    ):
        with pytest.raises(HTTPException) as exc:
            await create_video_activity(
                mock_request,
                name="Test Video",
                chapter_id=9999,
                current_user=admin_user,
                db_session=db,
                video_file=None,
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_409_when_no_video_file(
        self, mock_request, db, org, course, chapter, admin_user
    ):
        with patch(
            "src.services.courses.activities.video.check_resource_access",
            new_callable=AsyncMock,
        ), pytest.raises(HTTPException) as exc:
            await create_video_activity(
                mock_request,
                name="Test Video",
                chapter_id=chapter.id,
                current_user=admin_user,
                db_session=db,
                video_file=None,
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_raises_409_for_invalid_video_content_type(
        self, mock_request, db, org, course, chapter, admin_user
    ):
        with patch(
            "src.services.courses.activities.video.check_resource_access",
            new_callable=AsyncMock,
        ), pytest.raises(HTTPException) as exc:
            await create_video_activity(
                mock_request,
                name="Test Video",
                chapter_id=chapter.id,
                current_user=admin_user,
                db_session=db,
                video_file=_mock_video_file(content_type="text/plain"),
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_creates_video_activity_successfully(
        self, mock_request, db, org, course, chapter, admin_user
    ):
        with patch(
            "src.services.courses.activities.video.check_resource_access",
            new_callable=AsyncMock,
        ), patch(
            "src.services.courses.activities.video.upload_video",
            new_callable=AsyncMock,
            return_value="video_test.mp4",
        ):
            result = await create_video_activity(
                mock_request,
                name="Test Video",
                chapter_id=chapter.id,
                current_user=admin_user,
                db_session=db,
                video_file=_mock_video_file(),
            )

        assert result.name == "Test Video"


class TestUpdateVideoActivity:
    @pytest.mark.asyncio
    async def test_reupload_clears_stale_hls_status_and_reenqueues(
        self, mock_request, db, org, course, chapter, activity, admin_user
    ):
        # SECURITY: a stale "ready" status from the video being replaced would
        # (a) keep pointing players at the old rendition and (b) keep the raw
        # MP4 download lock in stream.py engaged for content that no longer
        # has a matching protected rendition. Both must be cleared immediately.
        activity.extra_metadata = {"hls": {"status": "ready", "master": "old/master.m3u8"}}
        db.add(activity)
        await db.commit()

        with patch(
            "src.services.courses.activities.video.check_resource_access",
            new_callable=AsyncMock,
        ), patch(
            "src.services.courses.activities.video.upload_video",
            new_callable=AsyncMock,
            return_value="new_video.mp4",
        ), patch(
            "src.services.utils.hls_jobs.enqueue"
        ) as enqueue_mock:
            result = await update_video_activity(
                mock_request,
                activity_uuid=activity.activity_uuid,
                current_user=admin_user,
                db_session=db,
                video_file=_mock_video_file(filename="new_video.mp4"),
            )

        assert result.content["filename"] == "new_video.mp4"
        assert "hls" not in (result.extra_metadata or {})
        enqueue_mock.assert_called_once_with(activity.activity_uuid)

    @pytest.mark.asyncio
    async def test_name_only_update_leaves_hls_status_and_enqueue_untouched(
        self, mock_request, db, org, course, chapter, activity, admin_user
    ):
        activity.extra_metadata = {"hls": {"status": "ready", "master": "old/master.m3u8"}}
        db.add(activity)
        await db.commit()

        with patch(
            "src.services.courses.activities.video.check_resource_access",
            new_callable=AsyncMock,
        ), patch(
            "src.services.utils.hls_jobs.enqueue"
        ) as enqueue_mock:
            result = await update_video_activity(
                mock_request,
                activity_uuid=activity.activity_uuid,
                current_user=admin_user,
                db_session=db,
                name="Renamed",
            )

        assert result.name == "Renamed"
        assert result.extra_metadata["hls"]["status"] == "ready"
        enqueue_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_409_for_invalid_video_content_type(
        self, mock_request, db, org, course, chapter, activity, admin_user
    ):
        with patch(
            "src.services.courses.activities.video.check_resource_access",
            new_callable=AsyncMock,
        ), pytest.raises(HTTPException) as exc:
            await update_video_activity(
                mock_request,
                activity_uuid=activity.activity_uuid,
                current_user=admin_user,
                db_session=db,
                video_file=_mock_video_file(content_type="text/plain"),
            )
        assert exc.value.status_code == 409


class TestCreateExternalVideoActivity:
    @pytest.mark.asyncio
    async def test_raises_404_when_chapter_not_found(
        self, mock_request, db, org, admin_user
    ):
        data = ExternalVideo(
            name="YT Video", uri="https://youtube.com/watch?v=abc", type="youtube", chapter_id=9999
        )
        with pytest.raises(HTTPException) as exc:
            await create_external_video_activity(mock_request, admin_user, data, db)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_creates_external_video_activity(
        self, mock_request, db, org, course, chapter, admin_user
    ):
        data = ExternalVideo(
            name="YT Video",
            uri="https://youtube.com/watch?v=abc123",
            type="youtube",
            chapter_id=chapter.id,
        )
        with patch(
            "src.services.courses.activities.video.check_resource_access",
            new_callable=AsyncMock,
        ):
            result = await create_external_video_activity(
                mock_request, admin_user, data, db
            )
        assert result.name == "YT Video"
