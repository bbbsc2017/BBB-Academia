
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class PodcastEpisodeBase(SQLModel):
    title: str
    description: str | None = None
    audio_file: str | None = Field(default="")
    duration_seconds: int | None = Field(default=0)
    episode_number: int | None = Field(default=1)
    thumbnail_image: str | None = Field(default="")
    published: bool = Field(default=False)
    order: int = Field(default=0)


class PodcastEpisode(PodcastEpisodeBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    podcast_id: int = Field(
        sa_column=Column(Integer, ForeignKey("podcast.id", ondelete="CASCADE"))
    )
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"))
    )
    episode_uuid: str = ""
    creation_date: str = ""
    update_date: str = ""


class PodcastEpisodeCreate(PodcastEpisodeBase):
    podcast_id: int = Field(default=None, foreign_key="podcast.id")
    org_id: int = Field(default=None, foreign_key="organization.id")
    thumbnail_image: str | None = Field(default="")


class PodcastEpisodeUpdate(SQLModel):
    title: str | None = None
    description: str | None = None
    audio_file: str | None = None  # None means don't update, use upload endpoint to change
    duration_seconds: int | None = None
    episode_number: int | None = None
    thumbnail_image: str | None = None  # None means don't update, use upload endpoint to change
    published: bool | None = None
    order: int | None = None


class PodcastEpisodeRead(PodcastEpisodeBase):
    id: int
    podcast_id: int = Field(default=None, foreign_key="podcast.id")
    org_id: int = Field(default=None, foreign_key="organization.id")
    episode_uuid: str
    creation_date: str
    update_date: str
    thumbnail_image: str | None = Field(default="")
