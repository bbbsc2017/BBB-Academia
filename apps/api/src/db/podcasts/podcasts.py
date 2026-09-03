
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from src.db.resource_authors import ResourceAuthorshipEnum, ResourceAuthorshipStatusEnum
from src.db.users import UserRead


class PodcastSEO(BaseModel):
    """SEO configuration for a podcast stored as JSON"""
    # Basic SEO
    title: str | None = None
    description: str | None = None
    keywords: str | None = None
    canonical_url: str | None = None
    # Open Graph
    og_title: str | None = None
    og_description: str | None = None
    og_image: str | None = None
    # Twitter Card
    twitter_card: str | None = None  # 'summary' | 'summary_large_image'
    twitter_title: str | None = None
    twitter_description: str | None = None
    # Robots & Structured Data
    robots_noindex: bool = False
    robots_nofollow: bool = False
    enable_jsonld: bool = True


class AuthorWithRole(SQLModel):
    user: UserRead
    authorship: ResourceAuthorshipEnum
    authorship_status: ResourceAuthorshipStatusEnum
    creation_date: str
    update_date: str


class PodcastBase(SQLModel):
    name: str
    description: str | None = None
    about: str | None = None
    tags: str | None = None
    thumbnail_image: str | None = Field(default="")
    public: bool
    published: bool = Field(default=False)


class Podcast(PodcastBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"))
    )
    podcast_uuid: str = ""
    creation_date: str = ""
    update_date: str = ""
    seo: dict | None = Field(default=None, sa_column=Column(JSONB))


class PodcastCreate(PodcastBase):
    org_id: int = Field(default=None, foreign_key="organization.id")
    thumbnail_image: str | None = Field(default="")


class PodcastUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    about: str | None = None
    tags: str | None = None
    thumbnail_image: str | None = Field(default="")
    public: bool | None = None
    published: bool | None = None
    seo: dict | None = None


class PodcastRead(PodcastBase):
    id: int
    org_id: int = Field(default=None, foreign_key="organization.id")
    authors: list[AuthorWithRole]
    podcast_uuid: str
    creation_date: str
    update_date: str
    thumbnail_image: str | None = Field(default="")
    seo: dict | None = None


class PodcastReadWithEpisodeCount(PodcastRead):
    episode_count: int = 0
