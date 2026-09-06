"""Create the Peblo TV Mini database foundation.

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sections",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label", name="uq_sections_label"),
    )
    op.create_table(
        "categories",
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("value"),
        sa.UniqueConstraint("label", name="uq_categories_label"),
    )
    op.create_table(
        "languages",
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("label", name="uq_languages_label"),
    )
    op.create_table(
        "shows",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(), nullable=False),
        sa.Column("show_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("section_id", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("default_language", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["category"], ["categories.value"]),
        sa.ForeignKeyConstraint(["default_language"], ["languages.code"]),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("show_id", name="uq_shows_show_id"),
        sa.CheckConstraint("length(trim(show_id)) > 0", name="ck_shows_show_id_nonempty"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_shows_title_nonempty"),
    )
    op.create_index("ix_shows_section_id", "shows", ["section_id"])
    op.create_index("ix_shows_category", "shows", ["category"])
    op.create_index("ix_shows_section_category", "shows", ["section_id", "category"])
    op.create_index("ix_shows_title_lower", "shows", [sa.text("lower(title)")])

    op.create_table(
        "seasons",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(), nullable=False),
        sa.Column("show_id", sa.BigInteger(), nullable=False),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["show_id"], ["shows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("show_id", "season_number", name="uq_seasons_show_number"),
        sa.CheckConstraint("season_number >= 0", name="ck_seasons_number_nonnegative"),
    )
    op.create_index("ix_seasons_show_number", "seasons", ["show_id", "season_number"])

    op.create_table(
        "content_groups",
        sa.Column("content_group", sa.String(length=255), nullable=False),
        sa.Column("season_id", sa.BigInteger(), nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_group"),
        sa.UniqueConstraint("season_id", "episode_number", name="uq_content_groups_season_episode"),
        sa.UniqueConstraint("content_group", "season_id", "episode_number", name="uq_content_groups_composite_ref"),
        sa.CheckConstraint("length(trim(content_group)) > 0", name="ck_content_groups_key_nonempty"),
        sa.CheckConstraint("episode_number > 0", name="ck_content_groups_episode_positive"),
    )
    op.create_index("ix_content_groups_season_episode", "content_groups", ["season_id", "episode_number"])

    op.create_table(
        "episodes",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(), nullable=False),
        sa.Column("episode_id", sa.String(length=255), nullable=False),
        sa.Column("season_id", sa.BigInteger(), nullable=False),
        sa.Column("content_group", sa.String(length=255), nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["language"], ["languages.code"]),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["content_group", "season_id", "episode_number"],
            ["content_groups.content_group", "content_groups.season_id", "content_groups.episode_number"],
            name="fk_episodes_content_group_position",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", name="uq_episodes_episode_id"),
        sa.UniqueConstraint("content_group", "language", name="uq_episodes_content_group_language"),
        sa.CheckConstraint("length(trim(episode_id)) > 0", name="ck_episodes_id_nonempty"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_episodes_title_nonempty"),
        sa.CheckConstraint("episode_number > 0", name="ck_episodes_number_positive"),
        sa.CheckConstraint("duration_seconds > 0", name="ck_episodes_duration_positive"),
    )
    op.create_index("ix_episodes_season_episode", "episodes", ["season_id", "episode_number"])
    op.create_index("ix_episodes_content_group", "episodes", ["content_group"])
    op.create_index("ix_episodes_language", "episodes", ["language"])
    op.create_index("ix_episodes_season_language", "episodes", ["season_id", "language"])
    op.create_index("ix_episodes_title_lower", "episodes", [sa.text("lower(title)")])

    op.create_table(
        "artworks",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(), nullable=False),
        sa.Column("show_id", sa.BigInteger(), nullable=True),
        sa.Column("episode_id", sa.BigInteger(), nullable=True),
        sa.Column("surface", sa.String(length=30), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("validation_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["show_id"], ["shows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_artworks_storage_key"),
        sa.CheckConstraint("(show_id IS NOT NULL AND episode_id IS NULL) OR (show_id IS NULL AND episode_id IS NOT NULL)", name="ck_artworks_exactly_one_owner"),
        sa.CheckConstraint("surface IN ('poster', 'banner', 'thumbnail')", name="ck_artworks_surface"),
        sa.CheckConstraint("length(trim(storage_key)) > 0", name="ck_artworks_storage_key_nonempty"),
        sa.CheckConstraint("length(trim(content_type)) > 0", name="ck_artworks_content_type_nonempty"),
        sa.CheckConstraint("width > 0", name="ck_artworks_width_positive"),
        sa.CheckConstraint("height > 0", name="ck_artworks_height_positive"),
        sa.CheckConstraint("file_size_bytes >= 0", name="ck_artworks_size_nonnegative"),
        sa.CheckConstraint("validation_status IN ('pending', 'valid', 'invalid', 'failed')", name="ck_artworks_validation_status"),
    )
    op.create_index("uq_artworks_show_surface", "artworks", ["show_id", "surface"], unique=True, postgresql_where=sa.text("show_id IS NOT NULL"))
    op.create_index("uq_artworks_episode_surface", "artworks", ["episode_id", "surface"], unique=True, postgresql_where=sa.text("episode_id IS NOT NULL"))
    op.create_index("ix_artworks_show_id", "artworks", ["show_id"], postgresql_where=sa.text("show_id IS NOT NULL"))
    op.create_index("ix_artworks_episode_id", "artworks", ["episode_id"], postgresql_where=sa.text("episode_id IS NOT NULL"))

    op.create_table(
        "publish_runs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_version", sa.String(length=255), nullable=True),
        sa.Column("source_identifier", sa.String(length=255), nullable=True),
        sa.Column("catalogue_object_key", sa.Text(), nullable=True),
        sa.Column("catalogue_object_version", sa.String(length=255), nullable=True),
        sa.Column("catalogue_checksum", sa.String(length=255), nullable=True),
        sa.Column("catalogue_etag", sa.String(length=255), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("error_details", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="ck_publish_runs_status"),
        sa.CheckConstraint("(status = 'running' AND completed_at IS NULL) OR (status IN ('succeeded', 'failed') AND completed_at IS NOT NULL)", name="ck_publish_runs_completion"),
        sa.CheckConstraint("status <> 'succeeded' OR catalogue_object_key IS NOT NULL", name="ck_publish_runs_success_object_key"),
    )
    op.create_index("ix_publish_runs_status", "publish_runs", ["status"])
    op.create_index("ix_publish_runs_started_at", "publish_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_publish_runs_started_at", table_name="publish_runs")
    op.drop_index("ix_publish_runs_status", table_name="publish_runs")
    op.drop_table("publish_runs")
    op.drop_index("ix_artworks_episode_id", table_name="artworks")
    op.drop_index("ix_artworks_show_id", table_name="artworks")
    op.drop_index("uq_artworks_episode_surface", table_name="artworks")
    op.drop_index("uq_artworks_show_surface", table_name="artworks")
    op.drop_table("artworks")
    op.drop_index("ix_episodes_title_lower", table_name="episodes")
    op.drop_index("ix_episodes_season_language", table_name="episodes")
    op.drop_index("ix_episodes_language", table_name="episodes")
    op.drop_index("ix_episodes_content_group", table_name="episodes")
    op.drop_index("ix_episodes_season_episode", table_name="episodes")
    op.drop_table("episodes")
    op.drop_index("ix_content_groups_season_episode", table_name="content_groups")
    op.drop_table("content_groups")
    op.drop_index("ix_seasons_show_number", table_name="seasons")
    op.drop_table("seasons")
    op.drop_index("ix_shows_title_lower", table_name="shows")
    op.drop_index("ix_shows_section_category", table_name="shows")
    op.drop_index("ix_shows_category", table_name="shows")
    op.drop_index("ix_shows_section_id", table_name="shows")
    op.drop_table("shows")
    op.drop_table("languages")
    op.drop_table("categories")
    op.drop_table("sections")
