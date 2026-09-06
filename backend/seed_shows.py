from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import delete

from backend.database import SessionLocal, engine
from backend.models import Artwork, Base, ContentGroup, Episode, Season, Show
from backend.seed_reference import load_reference_tables
from backend.storage import LocalStorage

FIXTURE = Path(__file__).resolve().parents[1] / "data" / "seed_shows.json"
DEMO_ASSET = Path(__file__).resolve().parents[1] / "assets" / "demo" / "valid-1600x900.jpg"


def seed(path: Path = FIXTURE, reset: bool = False) -> None:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    storage = LocalStorage()
    demo_bytes = DEMO_ASSET.read_bytes() if DEMO_ASSET.exists() else None
    with SessionLocal() as db:
        load_reference_tables(db)
        if reset:
            db.execute(delete(Artwork))
            db.execute(delete(Episode))
            db.execute(delete(ContentGroup))
            db.execute(delete(Season))
            db.execute(delete(Show))
            db.commit()
        shows = {row.show_id: row for row in db.query(Show).all()}
        for item in fixture["shows"]:
            show = shows.get(item["show_id"])
            if show is None:
                show = Show(**{key: item[key] for key in ("show_id", "title", "section_id", "category", "description", "default_language")})
                db.add(show)
                db.flush()
            if not any(art.surface == "banner" for art in show.artworks):
                art = item["artwork"]
                db.add(Artwork(show_id=show.id, surface="banner", storage_key=art["path"], content_type="image/jpeg", width=art["width"], height=art["height"], file_size_bytes=art["bytes"], validation_status="valid"))
                if demo_bytes is not None:
                    storage.put_bytes(art["path"], demo_bytes)
        db.flush()
        shows = {row.show_id: row for row in db.query(Show).all()}
        for item in fixture["episodes"]:
            if db.query(Episode).filter_by(episode_id=item["episode_id"]).first():
                continue
            show = shows[item["show_id"]]
            season = db.query(Season).filter_by(show_id=show.id, season_number=item["season"]).first()
            if season is None:
                season = Season(show_id=show.id, season_number=item["season"])
                db.add(season)
                db.flush()
            group = db.get(ContentGroup, item["content_group"])
            if group is None:
                group = ContentGroup(content_group=item["content_group"], season_id=season.id, episode_number=item["episode"])
                db.add(group)
                db.flush()
            episode = Episode(episode_id=item["episode_id"], season_id=season.id, content_group=item["content_group"], episode_number=item["episode"], title=item["title"], language=item["language"], duration_seconds=item["duration_seconds"])
            db.add(episode)
            db.flush()
            art = item["artwork"]
            valid = art["validation"] == "valid"
            db.add(Artwork(episode_id=episode.id, surface="thumbnail", storage_key=art["path"], content_type="image/jpeg", width=art["width"], height=art["height"], file_size_bytes=art["bytes"], validation_status="valid" if valid else "invalid", validation_error=None if valid else art["validation"],))
            if valid and demo_bytes is not None:
                storage.put_bytes(art["path"], demo_bytes)
        db.commit()
        print(f"Seeded {len(shows)} shows from deterministic replacement fixture {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    args = parser.parse_args()
    seed(args.fixture, args.reset)