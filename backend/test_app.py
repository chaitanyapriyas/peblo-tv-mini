from __future__ import annotations

import io
import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_peblo.db"
os.environ["STORAGE_ROOT"] = "./test_storage"

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.app as app_module
from backend.app import build_catalogue, filter_catalogue, publish, role_required, validate_upload
from backend.models import Base, ContentGroup, Episode, Language, PublishRun, Section, Category, Season, Show
from backend.storage import LocalStorage


def test_artwork_validation_rejects_bad_dimensions() -> None:
    image = Image.new("RGB", (1280, 720), "red")
    stream = io.BytesIO()
    image.save(stream, format="JPEG")
    try:
        validate_upload(stream.getvalue(), "image/jpeg")
    except Exception as exc:
        assert "1600x900" in str(exc)
    else:
        raise AssertionError("invalid dimensions were accepted")


def test_catalogue_collapses_languages_and_excludes_season_zero() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Section(id="drama", label="Drama"), Category(value="Drama", label="Drama"), Language(code="en", label="English"), Language(code="es", label="Spanish")])
        db.flush()
        show = Show(show_id="s", title="Show", section_id="drama", category="Drama", description="D", default_language="en")
        db.add(show)
        db.flush()
        trailer = Season(show_id=show.id, season_number=0)
        season = Season(show_id=show.id, season_number=1)
        db.add_all([trailer, season])
        db.flush()
        group = ContentGroup(content_group="g", season_id=season.id, episode_number=1)
        db.add(group)
        db.flush()
        db.add_all([Episode(episode_id="e-en", season_id=season.id, content_group="g", episode_number=1, title="Hello", language="en", duration_seconds=60), Episode(episode_id="e-es", season_id=season.id, content_group="g", episode_number=1, title="Hola", language="es", duration_seconds=60)])
        db.commit()
        catalogue = build_catalogue(db)
    assert [s["season_number"] for s in catalogue["shows"][0]["seasons"]] == [1]
    assert catalogue["shows"][0]["seasons"][0]["episodes"][0]["languages"] == ["en", "es"]


def test_composed_catalogue_filters() -> None:
    catalogue = {"shows": [{"show_id": "s", "title": "Harbor Lights", "description": "coast", "section": "drama", "category": "Drama", "seasons": [{"season_number": 1, "episodes": [{"languages": ["es"], "title": "Faro"}]}]}]}
    result = filter_catalogue(catalogue, "harbor", "drama", "Drama", "es", "s", 1)
    assert len(result["shows"]) == 1


def test_public_role_is_rejected_for_editor_dependency() -> None:
    dependency = role_required("editor")
    try:
        dependency(None)
    except Exception as exc:
        assert isinstance(exc, HTTPException)
        assert exc.status_code == 401
    else:
        raise AssertionError("missing auth was accepted")


def test_validation_report_endpoint_returns_authenticated_contract() -> None:
    with TestClient(app_module.app) as client:
        response = client.get(
            "/validation/report",
            headers={"Authorization": "Bearer demo-editor-token"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["valid"], bool)
    assert isinstance(payload["issues"], list)


def test_editor_cannot_publish() -> None:
    dependency = role_required("admin")
    try:
        dependency("Bearer demo-editor-token")
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("editor was accepted as admin")


def test_artwork_upload_rejects_aspect_ratio_and_size() -> None:
    image = Image.new("RGB", (1600, 800), "red")
    stream = io.BytesIO()
    image.save(stream, format="JPEG")
    try:
        validate_upload(stream.getvalue(), "image/jpeg")
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("wrong aspect ratio was accepted")
    try:
        validate_upload(b"x" * (200 * 1024 + 1), "image/jpeg")
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "200 KB" in str(exc.detail)
    else:
        raise AssertionError("oversized artwork was accepted")


def test_admin_publish_creates_versioned_live_catalogue_and_run(tmp_path: Path, monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    storage = LocalStorage(str(tmp_path))
    monkeypatch.setattr(app_module, "storage", storage)
    with Session(engine) as db:
        result = publish(db, "admin")
        assert result["status"] == "succeeded"
        assert (tmp_path / result["key"]).exists()
        assert (tmp_path / "catalogue/catalogue.json").exists()
        run = db.query(PublishRun).one()
        assert run.status == "succeeded"
