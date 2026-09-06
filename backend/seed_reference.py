from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Category, Language, Section

REFERENCE_PATH = Path(__file__).resolve().parents[1] / "data" / "reference.json"


def load_reference_tables(session: Session, reference_path: Path = REFERENCE_PATH) -> None:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))

    for item in reference["sections"]:
        row = session.get(Section, item["id"])
        if row is None:
            session.add(Section(id=item["id"], label=item["label"]))
        else:
            row.label = item["label"]

    for item in reference["categories"]:
        row = session.get(Category, item["value"])
        if row is None:
            session.add(Category(value=item["value"], label=item["label"]))
        else:
            row.label = item["label"]

    for item in reference["languages"]:
        row = session.get(Language, item["code"])
        if row is None:
            session.add(Language(code=item["code"], label=item["label"]))
        else:
            row.label = item["label"]

    session.commit()


if __name__ == "__main__":
    from backend.database import SessionLocal

    with SessionLocal() as db:
        load_reference_tables(db)
