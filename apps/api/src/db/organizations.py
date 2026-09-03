from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from src.db.organization_config import OrganizationConfig
from src.db.roles import RoleRead
from src.db.usergroups import UserGroupRead

if TYPE_CHECKING:
    from src.db.users import UserRead


class OrganizationBase(SQLModel):
    name: str
    description: str | None = None
    about: str | None = None
    socials: dict | None = Field(default_factory=dict, sa_column=Column(JSON))
    links: dict | None = Field(default_factory=dict, sa_column=Column(JSON))
    scripts: dict | None = Field(default_factory=dict, sa_column=Column(JSON))
    logo_image: str | None = None
    thumbnail_image: str | None = None
    previews: dict | None = Field(default_factory=dict, sa_column=Column(JSON))
    explore: bool | None = Field(default=False)
    label: str | None = None
    slug: str
    email: str


class Organization(OrganizationBase, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    org_uuid: str = Field(default="", unique=True)
    slug: str = Field(unique=True, index=True)  # Override to add unique constraint
    explore: bool | None = Field(default=False, index=True)  # Override to add index
    creation_date: str = ""
    update_date: str = ""

class OrganizationWithConfig(BaseModel):
    org: Organization
    config: OrganizationConfig


class OrganizationUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    about: str | None = None
    socials: dict | None = None
    links: dict | None = None
    scripts: dict | None = None
    logo_image: str | None = None
    thumbnail_image: str | None = None
    previews: dict | None = None
    label: str | None = None
    slug: str | None = None
    email: str | None = None

class OrganizationCreate(OrganizationBase):
    pass


class OrganizationRead(OrganizationBase):
    id: int
    org_uuid: str
    config: OrganizationConfig | dict | None = None
    creation_date: str
    update_date: str


class OrganizationUser(BaseModel):
    user: UserRead
    role: RoleRead
    usergroups: list[UserGroupRead] = []
    joined_at: str | None = None


# Rebuild models to resolve forward references after all classes are defined
def rebuild_models():
    from src.db.users import UserRead  # noqa: F401
    OrganizationUser.model_rebuild()

rebuild_models()
