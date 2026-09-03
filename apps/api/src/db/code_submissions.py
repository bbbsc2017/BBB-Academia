from datetime import UTC, datetime

from sqlmodel import JSON, Column, Field, SQLModel


class CodeSubmission(SQLModel, table=True):
    __tablename__ = "code_submission"

    id: int | None = Field(default=None, primary_key=True)
    submission_uuid: str = Field(index=True)
    user_id: int = Field(index=True)
    activity_uuid: str = Field(index=True)
    block_id: str = Field(index=True)
    language_id: int
    source_code: str
    results: dict = Field(default={}, sa_column=Column(JSON))
    passed: bool = False
    total_tests: int = 0
    passed_tests: int = 0
    execution_time_ms: int | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None).isoformat())


class CodeSubmissionRead(SQLModel):
    id: int
    submission_uuid: str
    language_id: int
    source_code: str
    results: dict
    passed: bool
    total_tests: int
    passed_tests: int
    execution_time_ms: int | None
    created_at: str
