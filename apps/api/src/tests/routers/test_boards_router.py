"""Router tests for src/routers/boards/*.py."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.db.boards import Board, BoardMemberRead, BoardRead
from src.routers.boards.boards import internal_router
from src.routers.boards.boards import router as boards_router
from src.security.auth import get_authenticated_user, get_current_user
from src.security.features_utils.dependencies import require_boards_feature


@pytest.fixture
def app(db, admin_user):
    app = FastAPI()
    app.include_router(boards_router, prefix="/api/v1/boards")
    app.include_router(internal_router, prefix="/api/v1/internal/boards")
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_authenticated_user] = lambda: admin_user
    app.dependency_overrides[require_boards_feature] = lambda: True
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _mock_board(**overrides) -> BoardRead:
    data = {
        "id": 1,
        "org_id": 1,
        "name": "Board",
        "description": "Desc",
        "thumbnail_image": "",
        "public": True,
        "board_uuid": "board_test",
        "created_by": 1,
        "creation_date": "2024-01-01",
        "update_date": "2024-01-01",
        "member_count": 1,
    }
    data.update(overrides)
    return BoardRead(**data)


def _mock_member(**overrides) -> BoardMemberRead:
    data = {
        "id": 1,
        "board_id": 1,
        "user_id": 1,
        "role": "editor",
        "creation_date": "2024-01-01",
        "username": "user",
    }
    data.update(overrides)
    return BoardMemberRead(**data)


class TestBoardsRouter:
    async def test_board_crud_and_membership_endpoints(self, client):
        with patch(
            "src.routers.boards.boards.create_board",
            new_callable=AsyncMock,
            return_value=_mock_board(),
        ):
            response = await client.post("/api/v1/boards/?org_id=1", json={"name": "Board"})
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.get_boards_by_org",
            new_callable=AsyncMock,
            return_value=[_mock_board()],
        ):
            response = await client.get("/api/v1/boards/org/1")
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.get_board",
            new_callable=AsyncMock,
            return_value=_mock_board(),
        ):
            response = await client.get("/api/v1/boards/board_test")
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.update_board",
            new_callable=AsyncMock,
            return_value=_mock_board(name="Updated"),
        ):
            response = await client.put("/api/v1/boards/board_test", json={"name": "Updated"})
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.duplicate_board",
            new_callable=AsyncMock,
            return_value=_mock_board(board_uuid="board_copy"),
        ):
            response = await client.post("/api/v1/boards/board_test/duplicate")
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.delete_board",
            new_callable=AsyncMock,
            return_value={"deleted": True},
        ):
            response = await client.delete("/api/v1/boards/board_test")
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.get_board_members",
            new_callable=AsyncMock,
            return_value=[_mock_member()],
        ):
            response = await client.get("/api/v1/boards/board_test/members")
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.update_board_thumbnail",
            new_callable=AsyncMock,
            return_value=_mock_board(thumbnail_image="thumb.png"),
        ):
            response = await client.post(
                "/api/v1/boards/board_test/thumbnail",
                files={"thumbnail": ("t.png", b"img", "image/png")},
            )
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.add_board_member",
            new_callable=AsyncMock,
            return_value=_mock_member(user_id=2),
        ):
            response = await client.post(
                "/api/v1/boards/board_test/members",
                json={"user_id": 2, "role": "editor"},
            )
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.add_board_members_batch",
            new_callable=AsyncMock,
            return_value=[_mock_member(user_id=2)],
        ):
            response = await client.post(
                "/api/v1/boards/board_test/members/batch",
                json={"members": [{"user_id": 2, "role": "editor"}]},
            )
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.remove_board_member",
            new_callable=AsyncMock,
            return_value={"removed": True},
        ):
            response = await client.delete("/api/v1/boards/board_test/members/2")
        assert response.status_code == 200

        with patch(
            "src.routers.boards.boards.check_board_membership",
            new_callable=AsyncMock,
            return_value=_mock_member(),
        ):
            response = await client.get("/api/v1/boards/board_test/membership")
        assert response.status_code == 200

    async def test_internal_ydoc_endpoints(self, client):
        old = os.environ.get("COLLAB_INTERNAL_KEY")
        os.environ["COLLAB_INTERNAL_KEY"] = "collab-secret"
        try:
            with patch(
                "src.routers.boards.boards.get_ydoc_state",
                new_callable=AsyncMock,
                return_value=b"state",
            ):
                response = await client.get(
                    "/api/v1/internal/boards/board_test/ydoc",
                    headers={"x-internal-key": "collab-secret"},
                )
            assert response.status_code == 200
            assert response.content == b"state"

            with patch(
                "src.routers.boards.boards.get_ydoc_state",
                new_callable=AsyncMock,
                return_value=None,
            ):
                response = await client.get(
                    "/api/v1/internal/boards/board_test/ydoc",
                    headers={"x-internal-key": "collab-secret"},
                )
            assert response.status_code == 200
            assert response.content == b""

            with patch(
                "src.routers.boards.boards.store_ydoc_state",
                new_callable=AsyncMock,
                return_value={"stored": True},
            ):
                response = await client.put(
                    "/api/v1/internal/boards/board_test/ydoc",
                    headers={"x-internal-key": "collab-secret"},
                    content=b"state",
                )
            assert response.status_code == 200
        finally:
            if old is None:
                os.environ.pop("COLLAB_INTERNAL_KEY", None)
            else:
                os.environ["COLLAB_INTERNAL_KEY"] = old

    async def test_internal_ydoc_rejects_invalid_key(self, client):
        old = os.environ.get("COLLAB_INTERNAL_KEY")
        os.environ["COLLAB_INTERNAL_KEY"] = "collab-secret"
        try:
            response = await client.get(
                "/api/v1/internal/boards/board_test/ydoc",
                headers={"x-internal-key": "wrong-key"},
            )
        finally:
            if old is None:
                os.environ.pop("COLLAB_INTERNAL_KEY", None)
            else:
                os.environ["COLLAB_INTERNAL_KEY"] = old

        assert response.status_code == 403

