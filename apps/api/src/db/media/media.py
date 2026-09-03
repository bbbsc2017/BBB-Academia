from enum import Enum

from sqlalchemy import BigInteger, Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class MediaTypeEnum(str, Enum):
    """Kind of media asset. Extensible — add new embeddable kinds here."""
    UPLOAD = "UPLOAD"  # A stored, downloadable file (pdf, mp4, etc.)
    EMBED = "EMBED"    # An external embed (YouTube/Vimeo/generic URL)


class MediaBase(SQLModel):
    name: str
    description: str | None = ""
    media_type: MediaTypeEnum = Field(default=MediaTypeEnum.UPLOAD)
    # For EMBED
    url: str | None = ""
    thumbnail_image: str | None = ""
    public: bool = True


class Media(MediaBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("organization.id", ondelete="CASCADE"), index=True
        )
    )
    media_uuid: str = Field(default="", index=True)
    # For UPLOAD — file metadata (mirrors BlockFile shape)
    file_id: str | None = ""
    # Randomized, server-only relative storage key (under content/). New uploads
    # set this; it is NEVER returned to clients, so the storage path cannot be
    # derived from public identifiers. Legacy rows leave it empty (reconstructed).
    storage_key: str | None = ""
    file_format: str | None = ""
    file_size: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    file_mime: str | None = ""
    creation_date: str = ""
    update_date: str = ""


class MediaCreate(MediaBase):
    org_id: int = Field(default=None, foreign_key="organization.id")
    # Optional: place into a folder right away
    folder_uuid: str | None = None


class MediaUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    thumbnail_image: str | None = None
    public: bool | None = None


class MediaRead(MediaBase):
    id: int
    org_id: int
    media_uuid: str
    # NOTE: the storage-locating fields (file_id / storage_key) are intentionally
    # NOT exposed — clients load bytes via GET /media/{media_uuid}/file only, so
    # the storage path is never derivable. file_format/size/mime are safe metadata
    # the UI needs to pick the right preview.
    file_format: str | None = ""
    file_size: int | None = None
    file_mime: str | None = ""
    creation_date: str
    update_date: str
