from __future__ import annotations

import io
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.database import SessionLocal, engine
from backend.models import Artwork, Base, ContentGroup, Episode, Language, PublishRun, Season, Show
from backend.seed_reference import load_reference_tables
from backend.storage import LocalStorage

app = FastAPI(title="Peblo TV Mini API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:5177",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177",
    ],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"] ,
)
storage = LocalStorage()
app.mount("/media", StaticFiles(directory=storage.root), name="media")


@app.middleware("http")
async def allow_cross_origin_media(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/media/"):
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    return response
MAX_ARTWORK_BYTES = 200 * 1024
ARTWORK_SIZE = (1600, 900)


class ShowIn(BaseModel):
    show_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    section_id: str
    category: str
    description: str
    default_language: str


class SeasonIn(BaseModel):
    season_number: int = Field(ge=0)


class EpisodeIn(BaseModel):
    episode_id: str = Field(min_length=1)
    content_group: str = Field(min_length=1)
    episode_number: int = Field(gt=0)
    title: str = Field(min_length=1)
    language: str
    duration_seconds: int = Field(gt=0)


class ShowOut(ShowIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SeasonOut(SeasonIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    show_id: int


class EpisodeOut(EpisodeIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    season_id: int


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(db_session)]


def role_required(*allowed: str):
    def dependency(authorization: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
        token = authorization[7:].strip()
        if token == os.getenv("DEMO_ADMIN_TOKEN", "demo-admin-token"):
            role = "admin"
        elif token == os.getenv("DEMO_EDITOR_TOKEN", "demo-editor-token"):
            role = "editor"
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid demo token")
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return role
    return dependency


Editor = Depends(role_required("editor", "admin"))
Admin = Depends(role_required("admin"))


@app.on_event("startup")
def startup() -> None:
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            load_reference_tables(db)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/shows", response_model=list[ShowOut])
def list_shows(db: DB, _: str = Editor) -> list[Show]:
    return list(db.scalars(select(Show).order_by(Show.title)).all())


@app.post("/shows", response_model=ShowOut, status_code=201)
def create_show(payload: ShowIn, db: DB, _: str = Editor) -> Show:
    show = Show(**payload.model_dump())
    db.add(show)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, detail=str(exc)) from exc
    db.refresh(show)
    return show


@app.patch("/shows/{show_id}", response_model=ShowOut)
def update_show(show_id: int, payload: ShowIn, db: DB, _: str = Editor) -> Show:
    show = db.get(Show, show_id)
    if not show:
        raise HTTPException(404, "Show not found")
    for key, value in payload.model_dump().items():
        setattr(show, key, value)
    db.commit()
    return show


@app.delete("/shows/{show_id}", status_code=204)
def delete_show(show_id: int, db: DB, _: str = Editor) -> None:
    show = db.get(Show, show_id)
    if not show:
        raise HTTPException(404, "Show not found")
    db.delete(show)
    db.commit()


@app.get("/shows/{show_id}/seasons", response_model=list[SeasonOut])
def list_seasons(show_id: int, db: DB, _: str = Editor) -> list[Season]:
    return list(db.scalars(select(Season).where(Season.show_id == show_id).order_by(Season.season_number)).all())


@app.post("/shows/{show_id}/seasons", response_model=SeasonOut, status_code=201)
def create_season(show_id: int, payload: SeasonIn, db: DB, _: str = Editor) -> Season:
    if not db.get(Show, show_id):
        raise HTTPException(404, "Show not found")
    season = Season(show_id=show_id, **payload.model_dump())
    db.add(season)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, detail=str(exc)) from exc
    db.refresh(season)
    return season


@app.patch("/seasons/{season_id}", response_model=SeasonOut)
def update_season(season_id: int, payload: SeasonIn, db: DB, _: str = Editor) -> Season:
    season = db.get(Season, season_id)
    if not season:
        raise HTTPException(404, "Season not found")
    season.season_number = payload.season_number
    db.commit()
    return season


@app.delete("/seasons/{season_id}", status_code=204)
def delete_season(season_id: int, db: DB, _: str = Editor) -> None:
    season = db.get(Season, season_id)
    if not season:
        raise HTTPException(404, "Season not found")
    db.delete(season)
    db.commit()


@app.get("/seasons/{season_id}/episodes", response_model=list[EpisodeOut])
def list_episodes(season_id: int, db: DB, _: str = Editor) -> list[Episode]:
    return list(db.scalars(select(Episode).where(Episode.season_id == season_id).order_by(Episode.episode_number, Episode.language)).all())


@app.post("/seasons/{season_id}/episodes", response_model=EpisodeOut, status_code=201)
def create_episode(season_id: int, payload: EpisodeIn, db: DB, _: str = Editor) -> Episode:
    season = db.get(Season, season_id)
    if not season:
        raise HTTPException(404, "Season not found")
    group = db.get(ContentGroup, payload.content_group)
    if group is None:
        db.add(ContentGroup(content_group=payload.content_group, season_id=season_id, episode_number=payload.episode_number))
    elif (group.season_id, group.episode_number) != (season_id, payload.episode_number):
        raise HTTPException(400, "content_group position does not match season")
    episode = Episode(season_id=season_id, **payload.model_dump())
    db.add(episode)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, detail=str(exc)) from exc
    db.refresh(episode)
    return episode


@app.patch("/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(episode_id: int, payload: EpisodeIn, db: DB, _: str = Editor) -> Episode:
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    for key, value in payload.model_dump().items():
        setattr(episode, key, value)
    db.commit()
    return episode


@app.delete("/episodes/{episode_id}", status_code=204)
def delete_episode(episode_id: int, db: DB, _: str = Editor) -> None:
    episode = db.get(Episode, episode_id)
    if not episode:
        raise HTTPException(404, "Episode not found")
    db.delete(episode)
    db.commit()


def validate_upload(content: bytes, content_type: str | None) -> tuple[int, int]:
    if len(content) > MAX_ARTWORK_BYTES:
        raise HTTPException(422, "Artwork exceeds 200 KB")
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(422, "Artwork must be JPEG, PNG, or WebP")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(422, "Uploaded file is not a valid image") from exc
    if (width, height) != ARTWORK_SIZE or width * 9 != height * 16:
        raise HTTPException(422, "Artwork must be exactly 1600x900 with a 16:9 aspect ratio")
    return width, height


@app.post("/artworks/upload")
async def upload_artwork(
    db: DB,
    role: str = Depends(role_required("editor", "admin")),
    owner_type: Annotated[str, Query(pattern="^(show|episode)$")] = "show",
    owner_id: int = 0,
    surface: Annotated[str, Query(pattern="^(poster|banner|thumbnail)$")] = "poster",
    file: UploadFile = File(...),
) -> dict[str, Any]:
    content = await file.read()
    width, height = validate_upload(content, file.content_type)
    owner = db.get(Show if owner_type == "show" else Episode, owner_id)
    if owner is None:
        raise HTTPException(404, "Artwork owner not found")
    extension = (file.filename or "image.jpg").split(".")[-1]
    storage_key = f"artworks/{owner_type}/{owner_id}/{surface}-{uuid.uuid4().hex}.{extension}"
    stored = storage.put_bytes(storage_key, content)
    filters = {"show_id" if owner_type == "show" else "episode_id": owner_id, "surface": surface}
    artwork = db.scalar(select(Artwork).filter_by(**filters))
    values = {"storage_key": storage_key, "content_type": file.content_type or "image/jpeg", "width": width, "height": height, "file_size_bytes": len(content), "validation_status": "valid", "validation_error": None, "validated_at": datetime.now(timezone.utc)}
    if artwork is None:
        artwork = Artwork(**filters, **values)
        db.add(artwork)
    else:
        for key, value in values.items():
            setattr(artwork, key, value)
    db.commit()
    return {"id": artwork.id, "surface": surface, "storage": stored, "validation_status": "valid"}


def validation_report(db: Session) -> dict[str, Any]:
    invalid_artwork = list(db.scalars(select(Artwork).where(Artwork.validation_status != "valid")).all())
    issues = [{"type": "artwork", "id": item.id, "owner_type": "show" if item.show_id else "episode", "owner_id": item.show_id or item.episode_id, "surface": item.surface, "message": item.validation_error or "Artwork is not valid", "storage_key": item.storage_key} for item in invalid_artwork]
    for show in db.scalars(select(Show)).all():
        if not any(a.show_id == show.id and a.surface == "banner" and a.validation_status == "valid" for a in show.artworks):
            issues.append({"type": "catalogue", "show_id": show.show_id, "message": "Show needs valid banner artwork"})
        for season in show.seasons:
            if season.show_id != show.id:
                issues.append({"type": "catalogue", "show_id": show.show_id, "message": "Season relationship is invalid"})
            for episode in season.episodes:
                if not any(a.surface == "thumbnail" and a.validation_status == "valid" for a in episode.artworks):
                    issues.append({"type": "catalogue", "episode_id": episode.episode_id, "message": "Episode needs valid thumbnail artwork"})
                if not episode.language or db.get(Language, episode.language) is None:
                    issues.append({"type": "catalogue", "episode_id": episode.episode_id, "message": "Episode language is missing or invalid"})
                if episode.duration_seconds <= 0:
                    issues.append({"type": "catalogue", "episode_id": episode.episode_id, "message": "Episode duration must be positive"})
                group = episode.content_group_ref
                if group is None or group.season_id != season.id or group.episode_number != episode.episode_number:
                    issues.append({"type": "catalogue", "episode_id": episode.episode_id, "message": "Episode content-group relationship is invalid"})
    return {"valid": not issues, "issues": issues}


@app.get("/validation/report")
def report(db: DB, _: str = Editor) -> dict[str, Any]:
    return validation_report(db)


def build_catalogue(db: Session) -> dict[str, Any]:
    shows = list(db.scalars(select(Show).options(joinedload(Show.seasons).joinedload(Season.episodes), joinedload(Show.artworks))).unique())
    result: list[dict[str, Any]] = []
    for show in shows:
        show_art = {a.surface: a.storage_key for a in show.artworks if a.validation_status == "valid"}
        seasons = []
        for season in sorted(show.seasons, key=lambda row: row.season_number):
            if season.season_number == 0:
                continue
            groups: dict[str, dict[str, Any]] = {}
            for episode in sorted(season.episodes, key=lambda row: (row.episode_number, row.language)):
                item = groups.setdefault(episode.content_group, {"episode_number": episode.episode_number, "title": episode.title, "duration_seconds": episode.duration_seconds, "languages": [], "artwork": {}})
                item["languages"].append(episode.language)
                item["artwork"].update({a.surface: a.storage_key for a in episode.artworks if a.validation_status == "valid"})
            seasons.append({"season_number": season.season_number, "episodes": list(groups.values())})
        result.append({"show_id": show.show_id, "title": show.title, "section": show.section_id, "category": show.category, "description": show.description, "default_language": show.default_language, "artwork": show_art, "seasons": seasons})
    return {"schema_version": "1.0", "published_at": datetime.now(timezone.utc).isoformat(), "shows": result}


def filter_catalogue(catalogue: dict[str, Any], query: str | None, section: str | None, category: str | None, language: str | None, show: str | None, season: int | None) -> dict[str, Any]:
    filtered = []
    for item in catalogue.get("shows", []):
        if query and query.lower() not in f"{item['title']} {item['description']}".lower():
            continue
        if (section and item["section"] != section) or (category and item["category"] != category) or (show and item["show_id"] != show):
            continue
        seasons = [s for s in item["seasons"] if season is None or s["season_number"] == season]
        if season is not None and not seasons:
            continue
        if language:
            seasons = [{**s, "episodes": [e for e in s["episodes"] if language in e["languages"]]} for s in seasons]
            if not any(s["episodes"] for s in seasons):
                continue
        filtered.append({**item, "seasons": seasons})
    return {**catalogue, "shows": filtered}


def published_catalogue() -> dict[str, Any]:
    catalogue = storage.get_json("catalogue/catalogue.json")
    if catalogue is None:
        raise HTTPException(404, "No published catalogue")
    return catalogue


@app.post("/publish")
def publish(db: DB, _: str = Admin) -> dict[str, Any]:
    run = PublishRun(status="running", started_at=datetime.now(timezone.utc), source_identifier="database")
    db.add(run)
    db.commit()
    report_data = validation_report(db)
    if not report_data["valid"]:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_summary = "Catalogue validation failed"
        run.error_details = report_data
        db.commit()
        raise HTTPException(422, detail=report_data)
    payload = build_catalogue(db)
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    try:
        stored = storage.put_json_versioned(payload, version)
        live = storage.promote(stored["key"])
    except Exception as exc:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_summary = str(exc)
        db.commit()
        raise HTTPException(500, "Publish storage failed") from exc
    run.status = "succeeded"
    run.completed_at = datetime.now(timezone.utc)
    run.catalogue_object_key = stored["key"]
    run.catalogue_object_version = stored["version"]
    run.catalogue_checksum = stored["etag"]
    run.catalogue_etag = live["version"]
    db.commit()
    return {"status": "succeeded", "version": stored["version"], "key": stored["key"]}


@app.get("/publish/runs")
def publish_runs(db: DB, _: str = Admin) -> list[dict[str, Any]]:
    return [{"id": r.id, "status": r.status, "started_at": r.started_at, "completed_at": r.completed_at, "version": r.catalogue_object_version, "error": r.error_summary} for r in db.scalars(select(PublishRun).order_by(PublishRun.started_at.desc())).all()]


@app.get("/catalog")
def catalog() -> dict[str, Any]:
    return published_catalogue()


@app.get("/catalog/search")
def catalog_search(query: str | None = None, section: str | None = None, category: str | None = None, language: str | None = None, show: str | None = None, season: int | None = None) -> dict[str, Any]:
    return filter_catalogue(published_catalogue(), query, section, category, language, show, season)