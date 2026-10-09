"""
Tests for importing a bbbsc participant's profile photo into LearnHouse.

bbbsc stores profile images as base64 ``data:`` URIs (not hosted URLs), so
they cannot be assigned straight to ``User.avatar_image`` the way Google
OAuth's picture URL is — LearnHouse only renders a bare filename (resolved
from its own media storage) or a real ``http(s)://`` URL. ``_store_bbbsc_avatar``
decodes and re-uploads the image into LearnHouse's own storage instead, and is
designed to fail open (return ``None``) on any invalid/unavailable input so a
bad or missing photo can never block a participant import.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from src.db.users import User
from src.services.auth.bbbsc import _store_bbbsc_avatar, provision_or_sync_bbbsc_user

# A real, minimal 1x1 PNG — passes both base64 decoding and the magic-byte check.
_VALID_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
)
_VALID_PNG_DATA_URI = f"data:image/png;base64,{_VALID_PNG_B64}"


@pytest.mark.asyncio
async def test_store_avatar_valid_png_uploads_and_returns_filename():
    with patch(
        "src.services.auth.bbbsc.upload_content", new=AsyncMock(return_value=None)
    ) as upload_mock:
        filename = await _store_bbbsc_avatar(_VALID_PNG_DATA_URI, "user_abc123")

    assert filename is not None
    assert filename.endswith(".png")
    upload_mock.assert_awaited_once()
    kwargs = upload_mock.await_args.kwargs
    assert kwargs["directory"] == "avatars"
    assert kwargs["type_of_dir"] == "users"
    assert kwargs["uuid"] == "user_abc123"
    assert kwargs["file_and_format"] == filename
    assert isinstance(kwargs["file_binary"], bytes)


@pytest.mark.asyncio
async def test_store_avatar_none_input_returns_none():
    assert await _store_bbbsc_avatar(None, "user_abc123") is None


@pytest.mark.asyncio
async def test_store_avatar_empty_string_returns_none():
    assert await _store_bbbsc_avatar("", "user_abc123") is None


@pytest.mark.asyncio
async def test_store_avatar_not_a_data_uri_returns_none():
    assert (
        await _store_bbbsc_avatar("https://example.com/photo.png", "user_abc123")
        is None
    )


@pytest.mark.asyncio
async def test_store_avatar_unsupported_mime_type_rejected():
    """SVG data URIs must never reach the filesystem (stored XSS via avatar)."""
    evil = "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="
    assert await _store_bbbsc_avatar(evil, "user_abc123") is None


@pytest.mark.asyncio
async def test_store_avatar_malformed_base64_returns_none():
    bad = "data:image/png;base64,not-valid-base64!!!"
    assert await _store_bbbsc_avatar(bad, "user_abc123") is None


@pytest.mark.asyncio
async def test_store_avatar_content_failing_magic_bytes_check_returns_none():
    """Claiming image/png with non-image bytes must be rejected (spoofed mime)."""
    import base64

    fake = base64.b64encode(b"this is definitely not an image").decode()
    data_uri = f"data:image/png;base64,{fake}"
    assert await _store_bbbsc_avatar(data_uri, "user_abc123") is None


@pytest.mark.asyncio
async def test_store_avatar_upload_failure_fails_open():
    """Storage errors must never bubble up and block the participant import."""
    with patch(
        "src.services.auth.bbbsc.upload_content",
        new=AsyncMock(side_effect=OSError("disk full")),
    ):
        assert await _store_bbbsc_avatar(_VALID_PNG_DATA_URI, "user_abc123") is None


@pytest.mark.asyncio
async def test_store_avatar_oversized_content_returns_none():
    with patch(
        "src.services.auth.bbbsc._MAX_BBBSC_AVATAR_BYTES", 4
    ):
        assert await _store_bbbsc_avatar(_VALID_PNG_DATA_URI, "user_abc123") is None


@pytest.fixture
def mock_request():
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "headers": [],
        "client": ("127.0.0.1", 0),
    }
    return Request(scope)


async def _fake_create_user(request, db_session, acting_user, user_object, org_id, **kwargs):
    """Stand-in for create_user: inserts just enough of a User row to let
    provision_or_sync_bbbsc_user's re-query find it, without the real
    signup side effects (welcome email, etc.) that are out of scope here."""
    from datetime import UTC, datetime

    user = User(
        username=user_object.username,
        first_name=user_object.first_name,
        last_name=user_object.last_name,
        email=user_object.email,
        password="",
        user_uuid=f"user_{user_object.username}",
        email_verified=True,
        creation_date=str(datetime.now(UTC)),
        update_date=str(datetime.now(UTC)),
    )
    db_session.add(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_provision_new_user_with_photo_sets_avatar(db, mock_request, org):
    bbbsc_user = {
        "email": "newparticipant@test.com",
        "firstName": "New",
        "lastName": "Participant",
        "roles": ["STUDENT"],
        "profileImageUrl": _VALID_PNG_DATA_URI,
    }
    with patch(
        "src.services.auth.bbbsc.create_user", new=AsyncMock(side_effect=_fake_create_user)
    ), patch(
        "src.services.auth.bbbsc._store_bbbsc_avatar",
        new=AsyncMock(return_value="fake_avatar.png"),
    ) as avatar_mock:
        user = await provision_or_sync_bbbsc_user(
            mock_request, db, bbbsc_user, sync_role=False
        )

    assert user is not None
    avatar_mock.assert_awaited_once_with(_VALID_PNG_DATA_URI, user.user_uuid)
    refreshed = (
        await db.execute(select(User).where(User.id == user.id))
    ).scalars().first()
    assert refreshed.avatar_image == "fake_avatar.png"


@pytest.mark.asyncio
async def test_provision_new_user_without_photo_leaves_avatar_unset(
    db, mock_request, org
):
    bbbsc_user = {
        "email": "nophoto@test.com",
        "firstName": "No",
        "lastName": "Photo",
        "roles": ["STUDENT"],
    }
    with patch(
        "src.services.auth.bbbsc.create_user", new=AsyncMock(side_effect=_fake_create_user)
    ), patch(
        "src.services.auth.bbbsc._store_bbbsc_avatar", new=AsyncMock(return_value=None)
    ) as avatar_mock:
        user = await provision_or_sync_bbbsc_user(
            mock_request, db, bbbsc_user, sync_role=False
        )

    assert user is not None
    avatar_mock.assert_awaited_once_with(None, user.user_uuid)
    assert not user.avatar_image


@pytest.mark.asyncio
async def test_provision_existing_user_never_overwrites_avatar(
    db, mock_request, org
):
    """Re-syncing an existing user (e.g. re-running the import) must never
    clobber an avatar the user has since changed inside LearnHouse itself."""
    from datetime import UTC, datetime

    from src.db.user_organizations import UserOrganization

    existing = User(
        username="existingparticipant",
        first_name="Existing",
        last_name="Participant",
        email="existing@test.com",
        password="",
        user_uuid="user_existingparticipant",
        email_verified=True,
        avatar_image="custom_avatar_user_chose.png",
        creation_date=str(datetime.now(UTC)),
        update_date=str(datetime.now(UTC)),
    )
    db.add(existing)
    await db.commit()
    await db.refresh(existing)
    db.add(
        UserOrganization(
            user_id=existing.id,
            org_id=org.id,
            role_id=4,
            creation_date=str(datetime.now(UTC)),
            update_date=str(datetime.now(UTC)),
        )
    )
    await db.commit()

    bbbsc_user = {
        "email": "existing@test.com",
        "firstName": "Existing",
        "lastName": "Participant",
        "roles": ["STUDENT"],
        "profileImageUrl": _VALID_PNG_DATA_URI,
    }
    with patch(
        "src.services.auth.bbbsc._store_bbbsc_avatar", new=AsyncMock()
    ) as avatar_mock:
        user = await provision_or_sync_bbbsc_user(
            mock_request, db, bbbsc_user, sync_role=False
        )

    avatar_mock.assert_not_awaited()
    assert user.avatar_image == "custom_avatar_user_chose.png"
