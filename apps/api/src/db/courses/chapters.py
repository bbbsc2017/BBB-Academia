from enum import Enum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from src.db.courses.activities import ActivityRead


class LockType(str, Enum):
    PUBLIC = "public"                # anyone, including anonymous, can view
    AUTHENTICATED = "authenticated"  # must be signed in
    RESTRICTED = "restricted"        # only members of assigned usergroups (via UserGroupResource)


class ChapterBase(SQLModel):
    name: str
    description: str | None = ""
    thumbnail_image: str | None = ""
    lock_type: LockType = LockType.PUBLIC
    org_id: int = Field(
        sa_column=Column("org_id", Integer, ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    )
    course_id: int = Field(
        sa_column=Column("course_id", Integer, ForeignKey("course.id", ondelete="CASCADE"), index=True)
    )


class Chapter(ChapterBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    chapter_uuid: str = Field(default="", index=True)
    creation_date: str = ""
    update_date: str = ""
    extra_metadata: dict | None = Field(default=None, sa_column=Column(JSONB))


class ChapterCreate(ChapterBase):
    # referenced order here will be ignored and just used for validation
    # used order will be the next available.
    extra_metadata: dict | None = None


class ChapterUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    thumbnail_image: str | None = None
    lock_type: LockType | None = None
    extra_metadata: dict | None = None


class ChapterRead(ChapterBase):
    id: int
    activities: list[ActivityRead]
    chapter_uuid: str
    creation_date: str
    update_date: str
    extra_metadata: dict | None = None
    # Computed per-request: whether current user is denied access to this chapter's
    # content (and, by cascade, its activities). Metadata (name, thumbnail) is still
    # returned so TOC navigation still renders a lock placeholder.
    is_locked: bool = False
    # Computed per-request: set when is_locked is True and the block is a paid
    # PaymentsOffer's usergroup — lets the client render a PaymentWall instead
    # of a generic "no access" screen.
    offer: dict | None = None


class ActivityOrder(BaseModel):
    activity_id: int


class ChapterOrder(BaseModel):
    chapter_id: int
    activities_order_by_ids: list[ActivityOrder]


class ChapterUpdateOrder(BaseModel):
    chapter_order_by_ids: list[ChapterOrder]


class DepreceatedChaptersRead(BaseModel):
    chapterOrder: Any
    chapters: Any
    activities: Any
