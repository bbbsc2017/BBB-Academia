
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Index, Integer, String
from sqlmodel import Field, SQLModel


class SuperadminAPITokenBase(SQLModel):
    """Base model for superadmin API tokens (cross-org)."""
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)


class SuperadminAPIToken(SuperadminAPITokenBase, table=True):
    """Database model for superadmin API tokens.

    Distinct from the org-scoped APIToken: no org_id (cross-org by design),
    no rights (all-or-nothing scope). Token secret prefix is ``lh_sa_`` to
    distinguish from org tokens (``lh_``).
    """
    __tablename__ = "superadmin_apitoken"
    __table_args__ = (
        Index("ix_superadmin_apitoken_token_prefix", "token_prefix"),
        Index("ix_superadmin_apitoken_created_by", "created_by_user_id"),
        {"extend_existing": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    token_uuid: str = Field(default="", max_length=100)  # satoken_{uuid4()}
    token_prefix: str = Field(default="", max_length=15)
    token_hash: str = Field(default="", sa_column=Column(String(255)))
    created_by_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
    update_date: str = ""
    last_used_at: str | None = None
    expires_at: str | None = None  # None = never expires
    is_active: bool = Field(default=True)  # False = revoked


class SuperadminAPITokenCreate(BaseModel):
    name: str
    description: str | None = None
    expires_at: str | None = None


class SuperadminAPITokenUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    expires_at: str | None = None


class SuperadminAPITokenRead(BaseModel):
    id: int
    token_uuid: str
    name: str
    description: str | None = None
    token_prefix: str
    created_by_user_id: int
    creation_date: str
    update_date: str
    last_used_at: str | None = None
    expires_at: str | None = None
    is_active: bool


class SuperadminAPITokenCreatedResponse(BaseModel):
    """Returned only on creation — the only response that includes the plaintext token."""
    token: str
    token_uuid: str
    name: str
    description: str | None = None
    token_prefix: str
    created_by_user_id: int
    creation_date: str
    expires_at: str | None = None
