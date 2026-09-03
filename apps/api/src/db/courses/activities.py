from enum import Enum

from sqlalchemy import JSON, Column, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class ActivityTypeEnum(str, Enum):
    TYPE_VIDEO = "TYPE_VIDEO"
    TYPE_DOCUMENT = "TYPE_DOCUMENT"
    TYPE_DYNAMIC = "TYPE_DYNAMIC"
    TYPE_ASSIGNMENT = "TYPE_ASSIGNMENT"
    TYPE_CUSTOM = "TYPE_CUSTOM"
    TYPE_SCORM = "TYPE_SCORM"


class ActivitySubTypeEnum(str, Enum):
    # Dynamic
    SUBTYPE_DYNAMIC_PAGE = "SUBTYPE_DYNAMIC_PAGE"
    SUBTYPE_DYNAMIC_MARKDOWN = "SUBTYPE_DYNAMIC_MARKDOWN"
    SUBTYPE_DYNAMIC_EMBED = "SUBTYPE_DYNAMIC_EMBED"
    SUBTYPE_DYNAMIC_RESOURCE = "SUBTYPE_DYNAMIC_RESOURCE"
    # Video
    SUBTYPE_VIDEO_YOUTUBE = "SUBTYPE_VIDEO_YOUTUBE"
    SUBTYPE_VIDEO_HOSTED = "SUBTYPE_VIDEO_HOSTED"
    # Document
    SUBTYPE_DOCUMENT_PDF = "SUBTYPE_DOCUMENT_PDF"
    SUBTYPE_DOCUMENT_DOC = "SUBTYPE_DOCUMENT_DOC"
    # Assignment
    SUBTYPE_ASSIGNMENT_ANY = "SUBTYPE_ASSIGNMENT_ANY"
    # Custom
    SUBTYPE_CUSTOM = "SUBTYPE_CUSTOM"
    # SCORM
    SUBTYPE_SCORM_12 = "SUBTYPE_SCORM_12"
    SUBTYPE_SCORM_2004 = "SUBTYPE_SCORM_2004"


class ActivityLockType(str, Enum):
    PUBLIC = "public"                # anyone, including anonymous, can view
    AUTHENTICATED = "authenticated"  # must be signed in
    RESTRICTED = "restricted"        # only members of assigned usergroups


class ActivityBase(SQLModel):
    name: str
    activity_type: ActivityTypeEnum
    activity_sub_type: ActivitySubTypeEnum
    content: dict = Field(default_factory=dict, sa_column=Column(JSON))
    details: dict | None = Field(default=None, sa_column=Column(JSON))
    published: bool = False
    lock_type: ActivityLockType = ActivityLockType.PUBLIC


class Activity(ActivityBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    )
    course_id: int = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), index=True),
    )
    activity_uuid: str = Field(default="", index=True)
    creation_date: str = ""
    update_date: str = ""
    extra_metadata: dict | None = Field(default=None, sa_column=Column(JSONB))
    # Versioning fields
    current_version: int = Field(default=1)
    last_modified_by_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="SET NULL"))
    )


class ActivityCreate(ActivityBase):
    chapter_id: int
    activity_type: ActivityTypeEnum = ActivityTypeEnum.TYPE_CUSTOM
    activity_sub_type: ActivitySubTypeEnum = ActivitySubTypeEnum.SUBTYPE_CUSTOM
    details: dict = Field(default_factory=dict, sa_column=Column(JSON))
    extra_metadata: dict | None = None


class ActivityUpdate(SQLModel):
    name: str | None = None
    content: dict | None = None
    activity_type: ActivityTypeEnum | None = None
    activity_sub_type: ActivitySubTypeEnum | None = None
    details: dict | None = None
    published: bool | None = None
    lock_type: ActivityLockType | None = None
    extra_metadata: dict | None = None


class ActivityRead(ActivityBase):
    id: int
    org_id: int
    course_id: int
    activity_uuid: str
    creation_date: str
    update_date: str
    details: dict | None = Field(default=None, sa_column=Column(JSON))
    extra_metadata: dict | None = None
    # Versioning fields
    current_version: int = 1
    last_modified_by_id: int | None = None
    last_modified_by_username: str | None = None
    # Computed per-request: true if current user cannot access this activity.
    is_locked: bool = False
    # Computed per-request: set when is_locked is True and the block is a paid
    # PaymentsOffer's usergroup (as opposed to a plain, non-payment restricted
    # usergroup) — lets the client render a PaymentWall instead of a generic
    # "no access" screen.
    offer: dict | None = None
