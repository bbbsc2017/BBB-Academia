from enum import Enum

from sqlalchemy import JSON, Column, ForeignKey
from sqlmodel import Field, SQLModel


class BlockTypeEnum(str, Enum):
    BLOCK_QUIZ = "BLOCK_QUIZ"
    BLOCK_VIDEO = "BLOCK_VIDEO"
    BLOCK_DOCUMENT_PDF = "BLOCK_DOCUMENT_PDF"
    BLOCK_IMAGE = "BLOCK_IMAGE"
    BLOCK_AUDIO = "BLOCK_AUDIO"
    BLOCK_CUSTOM = "BLOCK_CUSTOM"


class BlockBase(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    block_type: BlockTypeEnum = BlockTypeEnum.BLOCK_CUSTOM
    content: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Block(BlockBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content: dict = Field(default_factory=dict, sa_column=Column(JSON))
    org_id: int = Field(sa_column= Column("org_id", ForeignKey("organization.id", ondelete="CASCADE")))
    course_id: int = Field(sa_column= Column("course_id", ForeignKey("course.id", ondelete="CASCADE")))
    chapter_id: int | None = Field(default=None, sa_column= Column("chapter_id", ForeignKey("chapter.id", ondelete="CASCADE")))
    activity_id: int = Field(sa_column= Column("activity_id", ForeignKey("activity.id", ondelete="CASCADE")))
    block_uuid: str
    creation_date: str
    update_date: str


class BlockCreate(BlockBase):
    pass


class BlockRead(BlockBase):
    id: int = Field(default=None, primary_key=True)
    org_id: int = Field(default=None, foreign_key="organization.id")
    course_id: int = Field(default=None, foreign_key="course.id")
    chapter_id: int | None = Field(default=None, foreign_key="chapter.id")
    activity_id: int = Field(default=None, foreign_key="activity.id")
    block_uuid: str
    creation_date: str
    update_date: str
