from enum import Enum

from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlmodel import Field, SQLModel


class PlaygroundAccessType(str, Enum):
    PUBLIC = "public"               # Anonymous users can view
    AUTHENTICATED = "authenticated"  # Must be logged in
    RESTRICTED = "restricted"        # User groups only


class PlaygroundBase(SQLModel):
    name: str
    description: str | None = None
    thumbnail_image: str | None = None
    access_type: PlaygroundAccessType = PlaygroundAccessType.AUTHENTICATED
    published: bool = False
    course_uuid: str | None = None  # Optional course link (for RAG)
    html_content: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )


class Playground(PlaygroundBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    )
    playground_uuid: str = Field(default="", index=True)
    course_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="SET NULL"), nullable=True),
    )
    created_by: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    creation_date: str = ""
    update_date: str = ""


class PlaygroundRead(PlaygroundBase):
    id: int
    org_id: int
    org_uuid: str | None = None
    org_slug: str | None = None
    playground_uuid: str
    course_id: int | None = None
    created_by: int | None = None
    author_username: str | None = None
    author_first_name: str | None = None
    author_last_name: str | None = None
    author_user_uuid: str | None = None
    author_avatar_image: str | None = None
    creation_date: str
    update_date: str


class PlaygroundCreate(SQLModel):
    name: str
    description: str | None = None
    thumbnail_image: str | None = None
    access_type: PlaygroundAccessType = PlaygroundAccessType.AUTHENTICATED
    course_uuid: str | None = None
    html_content: str | None = None


class PlaygroundUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    thumbnail_image: str | None = None
    access_type: PlaygroundAccessType | None = None
    published: bool | None = None
    course_uuid: str | None = None
    html_content: str | None = None
