
from pydantic import BaseModel
from sqlalchemy import JSON, Column, ForeignKey, Index, Integer, String
from sqlmodel import Field, SQLModel

from src.db.roles import Rights


class APITokenBase(SQLModel):
    """Base model for API tokens"""
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    rights: Rights | dict | None = Field(default=None, sa_column=Column(JSON))


class APIToken(APITokenBase, table=True):
    """Database model for API tokens"""
    __tablename__ = "apitoken"
    __table_args__ = (
        Index("ix_apitoken_token_prefix", "token_prefix"),
        Index("ix_apitoken_org_id", "org_id"),
        {"extend_existing": True}
    )

    id: int | None = Field(default=None, primary_key=True)
    token_uuid: str = Field(default="", max_length=100)  # format: apitoken_{uuid4()}
    token_prefix: str = Field(default="", max_length=12)
    token_hash: str = Field(default="", sa_column=Column(String(255)))
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    created_by_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
    update_date: str = ""
    last_used_at: str | None = None
    expires_at: str | None = None  # None = never expires
    is_active: bool = Field(default=True)  # False = revoked


class APITokenCreate(BaseModel):
    """Model for creating a new API token"""
    name: str
    description: str | None = None
    rights: Rights | dict | None = None
    expires_at: str | None = None


class APITokenUpdate(BaseModel):
    """Model for updating an API token"""
    name: str | None = None
    description: str | None = None
    rights: Rights | dict | None = None
    expires_at: str | None = None


class APITokenRead(BaseModel):
    """Model for reading an API token (without sensitive data)"""
    id: int
    token_uuid: str
    name: str
    description: str | None = None
    token_prefix: str
    org_id: int
    rights: Rights | dict | None = None
    created_by_user_id: int
    creation_date: str
    update_date: str
    last_used_at: str | None = None
    expires_at: str | None = None
    is_active: bool


class APITokenCreatedResponse(BaseModel):
    """
    Response model when a new API token is created.
    This is the ONLY time the full token is shown.
    """
    token: str  # The full token (only shown once!)
    token_uuid: str
    name: str
    description: str | None = None
    token_prefix: str
    org_id: int
    rights: Rights | dict | None = None
    created_by_user_id: int
    creation_date: str
    expires_at: str | None = None
