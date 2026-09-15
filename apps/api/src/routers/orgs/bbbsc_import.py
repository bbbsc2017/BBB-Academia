"""
bbbsc Participant Import Router

Lets LearnHouse dashboard staff pull "Participante" (bbbsc role=STUDENT) users
from bbbsc's own admin system and create matching LearnHouse accounts for
them, so students already registered in bbbsc don't need a second signup.
This is the reverse direction of apps/api/src/routers/integrations/bbbsc.py
(which lets bbbsc_admin push a single course assignment into LearnHouse) —
here it's LearnHouse dashboard staff, already authenticated with normal
session/RBAC, pulling a list on demand.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.users import AnonymousUser, PublicUser
from src.security.auth import get_current_user
from src.services.orgs.bbbsc_import import (
    import_bbbsc_participants,
    list_bbbsc_participants,
)

router = APIRouter()


@router.get(
    "/{org_id}/bbbsc/participants",
    summary="List bbbsc participants available to import",
    description="Fetch a paginated page of bbbsc 'Participante' (STUDENT role) "
    "users, flagging which already have a matching LearnHouse account by email.",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Caller is not an org admin/maintainer"},
        404: {"description": "Organization not found"},
        502: {"description": "bbbsc is unreachable or not configured"},
    },
)
async def api_list_bbbsc_participants(
    request: Request,
    org_id: int,
    page: int = 1,
    limit: int = 50,
    search: str = "",
    current_user: PublicUser | AnonymousUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    return await list_bbbsc_participants(
        request, org_id, db_session, current_user, page, limit, search
    )


class BbbscImportRequest(BaseModel):
    # Full participant dicts as returned by the list endpoint above (email,
    # firstName, lastName, ...), not just emails — avoids a second bbbsc
    # round-trip per import.
    participants: list[dict]


@router.post(
    "/{org_id}/bbbsc/import",
    summary="Import selected bbbsc participants into LearnHouse",
    description="Create (or reuse, if already present) a LearnHouse account for "
    "each selected bbbsc participant, defaulting them to the Learner role.",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Caller is not an org admin/maintainer"},
        404: {"description": "Organization not found"},
    },
)
async def api_import_bbbsc_participants(
    request: Request,
    org_id: int,
    body: BbbscImportRequest,
    current_user: PublicUser | AnonymousUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    return await import_bbbsc_participants(
        request, org_id, body.participants, db_session, current_user
    )
