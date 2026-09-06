from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


DatabaseId = BigInteger().with_variant(Integer, "sqlite")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"), nullable=False
    )


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    shows: Mapped[List[Show]] = relationship(back_populates="section")


class Category(Base):
    __tablename__ = "categories"

    value: Mapped[str] = mapped_column(String(255), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    shows: Mapped[List[Show]] = relationship(back_populates="category_ref")


class Language(Base):
    __tablename__ = "languages"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    shows: Mapped[List[Show]] = relationship(back_populates="default_language_ref")
    episodes: Mapped[List[Episode]] = relationship(back_populates="language_ref")


class Show(TimestampMixin, Base):
    __tablename__ = "shows"
    __table_args__ = (
        CheckConstraint("length(trim(show_id)) > 0", name="ck_shows_show_id_nonempty"),
        CheckConstraint("length(trim(title)) > 0", name="ck_shows_title_nonempty"),
        Index("ix_shows_section_id", "section_id"),
        Index("ix_shows_category", "category"),
        Index("ix_shows_section_category", "section_id", "category"),
        Index("ix_shows_title_lower", text("lower(title)")),
    )

    id: Mapped[int] = mapped_column(DatabaseId, primary_key=True)
    show_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    section_id: Mapped[str] = mapped_column(ForeignKey("sections.id"), nullable=False)
    category: Mapped[str] = mapped_column(ForeignKey("categories.value"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    default_language: Mapped[str] = mapped_column(ForeignKey("languages.code"), nullable=False)

    section: Mapped[Section] = relationship(back_populates="shows")
    category_ref: Mapped[Category] = relationship(back_populates="shows")
    default_language_ref: Mapped[Language] = relationship(back_populates="shows")
    seasons: Mapped[List[Season]] = relationship(back_populates="show", cascade="all, delete-orphan")
    artworks: Mapped[List[Artwork]] = relationship(back_populates="show")


class Season(TimestampMixin, Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("show_id", "season_number", name="uq_seasons_show_number"),
        CheckConstraint("season_number >= 0", name="ck_seasons_number_nonnegative"),
        Index("ix_seasons_show_number", "show_id", "season_number"),
    )

    id: Mapped[int] = mapped_column(DatabaseId, primary_key=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id", ondelete="CASCADE"), nullable=False)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)

    show: Mapped[Show] = relationship(back_populates="seasons")
    content_groups: Mapped[List[ContentGroup]] = relationship(back_populates="season", cascade="all, delete-orphan")
    episodes: Mapped[List[Episode]] = relationship(back_populates="season", overlaps="content_group_ref,episodes")


class ContentGroup(TimestampMixin, Base):
    __tablename__ = "content_groups"
    __table_args__ = (
        UniqueConstraint("season_id", "episode_number", name="uq_content_groups_season_episode"),
        UniqueConstraint("content_group", "season_id", "episode_number", name="uq_content_groups_composite_ref"),
        CheckConstraint("length(trim(content_group)) > 0", name="ck_content_groups_key_nonempty"),
        CheckConstraint("episode_number > 0", name="ck_content_groups_episode_positive"),
        Index("ix_content_groups_season_episode", "season_id", "episode_number"),
    )

    content_group: Mapped[str] = mapped_column(String(255), primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)

    season: Mapped[Season] = relationship(back_populates="content_groups")
    episodes: Mapped[List[Episode]] = relationship(back_populates="content_group_ref", overlaps="season,episodes")


class Episode(TimestampMixin, Base):
    __tablename__ = "episodes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["content_group", "season_id", "episode_number"],
            ["content_groups.content_group", "content_groups.season_id", "content_groups.episode_number"],
            ondelete="CASCADE",
            name="fk_episodes_content_group_position",
        ),
        UniqueConstraint("content_group", "language", name="uq_episodes_content_group_language"),
        CheckConstraint("length(trim(episode_id)) > 0", name="ck_episodes_id_nonempty"),
        CheckConstraint("length(trim(title)) > 0", name="ck_episodes_title_nonempty"),
        CheckConstraint("episode_number > 0", name="ck_episodes_number_positive"),
        CheckConstraint("duration_seconds > 0", name="ck_episodes_duration_positive"),
        Index("ix_episodes_season_episode", "season_id", "episode_number"),
        Index("ix_episodes_content_group", "content_group"),
        Index("ix_episodes_language", "language"),
        Index("ix_episodes_season_language", "season_id", "language"),
        Index("ix_episodes_title_lower", text("lower(title)")),
    )

    id: Mapped[int] = mapped_column(DatabaseId, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    content_group: Mapped[str] = mapped_column(String(255), nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(ForeignKey("languages.code"), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    season: Mapped[Season] = relationship(back_populates="episodes", overlaps="content_group_ref,episodes")
    content_group_ref: Mapped[ContentGroup] = relationship(back_populates="episodes", overlaps="season,episodes")
    language_ref: Mapped[Language] = relationship(back_populates="episodes")
    artworks: Mapped[List[Artwork]] = relationship(back_populates="episode")


class Artwork(TimestampMixin, Base):
    __tablename__ = "artworks"
    __table_args__ = (
        CheckConstraint(
            "(show_id IS NOT NULL AND episode_id IS NULL) OR (show_id IS NULL AND episode_id IS NOT NULL)",
            name="ck_artworks_exactly_one_owner",
        ),
        CheckConstraint("surface IN ('poster', 'banner', 'thumbnail')", name="ck_artworks_surface"),
        CheckConstraint("length(trim(storage_key)) > 0", name="ck_artworks_storage_key_nonempty"),
        CheckConstraint("length(trim(content_type)) > 0", name="ck_artworks_content_type_nonempty"),
        CheckConstraint("width > 0", name="ck_artworks_width_positive"),
        CheckConstraint("height > 0", name="ck_artworks_height_positive"),
        CheckConstraint("file_size_bytes >= 0", name="ck_artworks_size_nonnegative"),
        CheckConstraint(
            "validation_status IN ('pending', 'valid', 'invalid', 'failed')",
            name="ck_artworks_validation_status",
        ),
        Index("uq_artworks_show_surface", "show_id", "surface", unique=True, postgresql_where=text("show_id IS NOT NULL")),
        Index("uq_artworks_episode_surface", "episode_id", "surface", unique=True, postgresql_where=text("episode_id IS NOT NULL")),
        Index("ix_artworks_show_id", "show_id", postgresql_where=text("show_id IS NOT NULL")),
        Index("ix_artworks_episode_id", "episode_id", postgresql_where=text("episode_id IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(DatabaseId, primary_key=True)
    show_id: Mapped[int | None] = mapped_column(ForeignKey("shows.id", ondelete="CASCADE"))
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"))
    surface: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    validation_error: Mapped[str | None] = mapped_column(Text)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    show: Mapped[Show | None] = relationship(back_populates="artworks")
    episode: Mapped[Episode | None] = relationship(back_populates="artworks")


class PublishRun(Base):
    __tablename__ = "publish_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="ck_publish_runs_status"),
        CheckConstraint(
            "(status = 'running' AND completed_at IS NULL) OR (status IN ('succeeded', 'failed') AND completed_at IS NOT NULL)",
            name="ck_publish_runs_completion",
        ),
        CheckConstraint(
            "status <> 'succeeded' OR catalogue_object_key IS NOT NULL",
            name="ck_publish_runs_success_object_key",
        ),
        Index("ix_publish_runs_status", "status"),
        Index("ix_publish_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(DatabaseId, primary_key=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_version: Mapped[str | None] = mapped_column(String(255))
    source_identifier: Mapped[str | None] = mapped_column(String(255))
    catalogue_object_key: Mapped[str | None] = mapped_column(Text)
    catalogue_object_version: Mapped[str | None] = mapped_column(String(255))
    catalogue_checksum: Mapped[str | None] = mapped_column(String(255))
    catalogue_etag: Mapped[str | None] = mapped_column(String(255))
    error_summary: Mapped[str | None] = mapped_column(Text)
    error_details: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
