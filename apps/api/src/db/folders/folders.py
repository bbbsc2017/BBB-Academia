
from pydantic import BaseModel
from sqlalchemy import BigInteger, Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class FolderBase(SQLModel):
    name: str
    public: bool = True
    description: str | None = ""
    thumbnail_image: str | None = ""
    color: str | None = "violet"


class Folder(FolderBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("organization.id", ondelete="CASCADE"), index=True
        )
    )
    folder_uuid: str = Field(default="", index=True)
    # Self-referential parent for nesting. NULL = root folder.
    parent_folder_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("folder.id", ondelete="CASCADE"), nullable=True, index=True
        ),
    )
    # Manual (admin drag) ordering position among siblings. Only consulted when
    # the org's folders.sort_mode == "manual"; the other modes sort by name/date.
    order: int = Field(default=0)
    creation_date: str = ""
    update_date: str = ""


class FolderCreate(FolderBase):
    org_id: int = Field(default=None, foreign_key="organization.id")
    parent_folder_uuid: str | None = None


class FolderUpdate(SQLModel):
    name: str | None = None
    public: bool | None = None
    description: str | None = None
    thumbnail_image: str | None = None
    color: str | None = None
    # When provided, re-parents the folder (use "" or "root" to move to root).
    parent_folder_uuid: str | None = None


class FolderBreadcrumb(SQLModel):
    folder_uuid: str
    name: str


class FolderContentItem(SQLModel):
    """A resolved leaf item inside a folder (any resource type)."""
    resource_uuid: str
    resource_type: str  # courses | podcasts | communities | boards | playgrounds | media
    position: int = 0
    resource: dict


class FolderRead(FolderBase):
    id: int
    org_id: int
    folder_uuid: str
    parent_folder_id: int | None = None
    order: int = 0
    creation_date: str
    update_date: str
    # Total number of children (sub-folders + leaf items), always populated.
    total_items: int = 0
    # Direct children
    subfolders: list[FolderRead] = []
    items: list[FolderContentItem] = []
    breadcrumbs: list[FolderBreadcrumb] = []


class FolderOrder(BaseModel):
    folder_id: int


class FolderUpdateOrder(BaseModel):
    folder_order_by_ids: list[FolderOrder]


class FolderContentUpdateOrder(BaseModel):
    # Content resource_uuids in the desired display order; position = array index.
    resource_uuids: list[str]
