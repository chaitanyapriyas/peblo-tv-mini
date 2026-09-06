from __future__ import annotations

import sys
from datetime import datetime, timezone

from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from backend.database import SessionLocal
from backend.models import Artwork, Base, Category, ContentGroup, Episode, Language, PublishRun, Season, Section, Show


def expect_rejection(label: str, action) -> None:
    try:
        action()
    except IntegrityError:
        print(f"PASS {label}")
    else:
        raise AssertionError(f"Expected IntegrityError: {label}")


def main() -> None:
    with SessionLocal() as db:
        if db.bind.dialect.name == "sqlite":
            db.connection().exec_driver_sql("PRAGMA foreign_keys = ON")
        show = db.scalar(select(Show).where(Show.show_id == "constraint-test-show"))
        if show is None:
            db.add_all([
                Section(id="constraint-test", label="Constraint Test"),
                Category(value="Constraint Test", label="Constraint Test"),
                Language(code="zz", label="Test Language"),
                Language(code="zy", label="Second Test Language"),
            ])
            db.flush()
            show = Show(
                show_id="constraint-test-show",
                title="Constraint Test Show",
                section_id="constraint-test",
                category="Constraint Test",
                description="Constraint verification data",
                default_language="zz",
            )
            db.add(show)
            db.flush()
            season = Season(show_id=show.id, season_number=1)
            db.add(season)
            db.flush()
            group = ContentGroup(content_group="constraint-test-group", season_id=season.id, episode_number=1)
            db.add(group)
            db.flush()
            db.add(Episode(
                episode_id="constraint-test-episode-zz",
                season_id=season.id,
                content_group="constraint-test-group",
                episode_number=1,
                title="Constraint Episode",
                language="zz",
                duration_seconds=60,
            ))
            db.add(Episode(
                episode_id="constraint-test-episode-zy",
                season_id=season.id,
                content_group="constraint-test-group",
                episode_number=1,
                title="Constraint Episode",
                language="zy",
                duration_seconds=60,
            ))
            db.commit()
            show_id, season_id, group_id = show.id, season.id, group.content_group
        else:
            season = db.scalar(select(Season).where(Season.show_id == show.id, Season.season_number == 1))
            group = db.scalar(select(ContentGroup).where(ContentGroup.content_group == "constraint-test-group"))
            show_id, season_id, group_id = show.id, season.id, group.content_group

        def duplicate_season() -> None:
            db.add(Season(show_id=show_id, season_number=1))
            db.flush()

        expect_rejection("duplicate season number", duplicate_season)
        db.rollback()

        season_zero = Season(show_id=show_id, season_number=0)
        db.add(season_zero)
        db.commit()
        print("PASS Season 0 is allowed")

        languages = db.scalars(
            select(Episode.language).where(Episode.content_group == group_id)
        ).all()
        assert len(set(languages)) >= 2
        print("PASS content_group supports multiple languages")

        def duplicate_content_group_position() -> None:
            db.add(ContentGroup(content_group="constraint-test-second-group", season_id=season_id, episode_number=1))
            db.flush()

        expect_rejection("duplicate season episode position across content groups", duplicate_content_group_position)
        db.rollback()

        def duplicate_variant() -> None:
            db.add(Episode(
                episode_id="constraint-test-duplicate-language",
                season_id=season_id,
                content_group=group_id,
                episode_number=1,
                title="Duplicate Language",
                language="zz",
                duration_seconds=60,
            ))
            db.flush()

        expect_rejection("duplicate content_group + language", duplicate_variant)
        db.rollback()

        def disagreeing_group_position() -> None:
            db.add(Episode(
                episode_id="constraint-test-disagreeing-position",
                season_id=season_id,
                content_group=group_id,
                episode_number=2,
                title="Disagreeing Position",
                language="zz",
                duration_seconds=60,
            ))
            db.flush()

        expect_rejection("content_group position disagreement", disagreeing_group_position)
        db.rollback()

        def both_owners() -> None:
            db.add(Artwork(
                show_id=show_id,
                episode_id=db.scalar(select(Episode.id).where(Episode.episode_id == "constraint-test-episode-zz")),
                surface="poster",
                storage_key="constraint/both.jpg",
                content_type="image/jpeg",
                width=1,
                height=1,
                file_size_bytes=1,
                validation_status="pending",
            ))
            db.flush()

        expect_rejection("artwork with both owners", both_owners)
        db.rollback()

        def no_owner() -> None:
            db.add(Artwork(
                surface="poster",
                storage_key="constraint/neither.jpg",
                content_type="image/jpeg",
                width=1,
                height=1,
                file_size_bytes=1,
                validation_status="pending",
            ))
            db.flush()

        expect_rejection("artwork with no owner", no_owner)
        db.rollback()

        db.add(Artwork(
            show_id=show_id,
            surface="poster",
            storage_key="constraint/first-poster.jpg",
            content_type="image/jpeg",
            width=1,
            height=1,
            file_size_bytes=1,
            validation_status="pending",
        ))
        db.commit()

        def duplicate_surface() -> None:
            db.add(Artwork(
                show_id=show_id,
                surface="poster",
                storage_key="constraint/second-poster.jpg",
                content_type="image/jpeg",
                width=1,
                height=1,
                file_size_bytes=1,
                validation_status="pending",
            ))
            db.flush()

        expect_rejection("duplicate artwork surface", duplicate_surface)
        db.rollback()

        invalid = Artwork(
            show_id=show_id,
            surface="banner",
            storage_key="constraint/invalid.jpg",
            content_type="application/octet-stream",
            width=17,
            height=11,
            file_size_bytes=999999,
            validation_status="invalid",
        )
        db.add(invalid)
        db.commit()
        print("PASS invalid artwork metadata is representable")

        publish_columns = {column["name"] for column in inspect(db.bind).get_columns("publish_runs")}
        assert "is_current" not in publish_columns
        print("PASS publish_runs has no is_current column")

        db.query(Artwork).filter(Artwork.storage_key.like("constraint/%")).delete(synchronize_session=False)
        db.query(Episode).filter(Episode.episode_id.like("constraint-test-%")).delete(synchronize_session=False)
        db.query(ContentGroup).filter(ContentGroup.content_group == group_id).delete(synchronize_session=False)
        db.query(Season).filter(Season.id == season_id).delete(synchronize_session=False)
        db.query(Season).filter(Season.id == season_zero.id).delete(synchronize_session=False)
        db.query(Show).filter(Show.id == show_id).delete(synchronize_session=False)
        db.query(Language).filter(Language.code == "zy").delete(synchronize_session=False)
        db.query(Language).filter(Language.code == "zz").delete(synchronize_session=False)
        db.query(Category).filter(Category.value == "Constraint Test").delete(synchronize_session=False)
        db.query(Section).filter(Section.id == "constraint-test").delete(synchronize_session=False)
        db.commit()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise
