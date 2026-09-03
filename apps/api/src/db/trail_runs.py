from enum import Enum

from pydantic import BaseModel
from sqlalchemy import JSON, Column, ForeignKey, Integer, UniqueConstraint
from sqlmodel import Field, SQLModel

from src.db.trail_steps import TrailStep


class TrailRunEnum(str, Enum):
    RUN_TYPE_COURSE = "RUN_TYPE_COURSE"


class StatusEnum(str, Enum):
    STATUS_IN_PROGRESS = "STATUS_IN_PROGRESS"
    STATUS_COMPLETED = "STATUS_COMPLETED"
    STATUS_PAUSED = "STATUS_PAUSED"
    STATUS_CANCELLED = "STATUS_CANCELLED"


class TrailRun(SQLModel, table=True):
    # A user can have at most one run per course inside a trail. The service
    # does a check-then-insert (select existing, else create), which races
    # under concurrent requests (e.g. double-clicking "enroll"), producing
    # duplicate runs that corrupt progress display and make .first() lookups
    # nondeterministic. The DB constraint closes that window. (Requires a
    # matching migration to apply to the live DB.)
    __table_args__ = (
        UniqueConstraint(
            "trail_id", "course_id", "user_id", name="uq_trailrun_trail_course_user"
        ),
        {"extend_existing": True},
    )
    id: int | None = Field(default=None, primary_key=True)
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: StatusEnum = StatusEnum.STATUS_IN_PROGRESS
    # foreign keys
    trail_id: int = Field(
        sa_column=Column(Integer, ForeignKey("trail.id", ondelete="CASCADE"), index=True)
    )
    course_id: int = Field(
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), index=True)
    )
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"))
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), index=True)
    )
    # timestamps
    creation_date: str
    update_date: str


class TrailRunCreate(SQLModel):
    data: dict = Field(default_factory=dict)
    status: StatusEnum = StatusEnum.STATUS_IN_PROGRESS
    trail_id: int
    course_id: int
    org_id: int
    user_id: int
    creation_date: str
    update_date: str


# trick because Lists are not supported in SQLModel (runs: list[TrailStep] )
class TrailRunRead(BaseModel):
    id: int | None = None
    data: dict = Field(default_factory=dict)
    status: StatusEnum = StatusEnum.STATUS_IN_PROGRESS
    # foreign keys
    trail_id: int | None = None
    course_id: int | None = None
    org_id: int | None = None
    user_id: int | None = None
    # course object
    course: dict | None = None
    # timestamps
    creation_date: str | None = None
    update_date: str | None = None
    # number of activities in course
    course_total_steps: int = 0
    steps: list[TrailStep] = Field(default_factory=list)
