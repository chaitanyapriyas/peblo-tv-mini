# Peblo TV Mini

Peblo TV Mini is a small catalogue CMS and read-only TV viewer. Editors manage shows, seasons, language variants, episodes, and artwork in the CMS. An admin validates and publishes a catalogue; the Viewer reads the resulting public catalogue.

## Architecture and publishing

The flow is **CMS React -> FastAPI -> PostgreSQL (or SQLite for the demo) -> publish -> versioned catalogue object -> live catalogue pointer -> Viewer**. The database stores editable source data and publish-run history. Publishing validates that source data, writes an immutable versioned JSON catalogue, then the storage abstraction promotes that version to the live `catalogue/catalogue.json` pointer. This is atomic at the catalogue-pointer boundary: readers see either the previous complete object or the new complete object. A database transaction alone cannot make object-storage promotion atomic because the database and object store are separate systems.

`backend/storage.py` is the storage boundary. The local implementation writes files, versions JSON, and promotes the live pointer; a Cloudflare R2 implementation could replace those methods with S3-compatible object operations without changing application-level publishing logic.

The current search filters catalogue records in application code for the published read path. CMS show listing uses the database-backed API and indexed PostgreSQL fields/B-tree indexes. At larger scale, PostgreSQL `pg_trgm` and full-text indexes, or a dedicated search service, can provide ranked and fuzzy search without changing the catalogue contract.

The Viewer reads only the pre-published catalogue rather than live relational tables. This gives fast, stable, cacheable reads and prevents partial edits from reaching viewers, at the cost of publication freshness: edits are invisible until a successful publish.

## Data rules and limitations

Artwork must be JPEG, PNG, or WebP, exactly 1600x900 (16:9), and no larger than 200 KB. Season 0 is reserved for trailers and is excluded from the published catalogue. Episodes use a `content_group` to identify one logical episode across language variants; each language row shares the group and episode position.

Authentication intentionally uses demo Bearer tokens for this take-home: the editor token can CRUD and validate, while only the admin token can publish or view publish history. This is not production authentication. The deterministic fixtures include invalid artwork so validation failures can be demonstrated. PostgreSQL, Docker, and GitHub Actions were not fully live-verified locally; SQLite is the supported local demo path.

AI/agent assistance was used for implementation and debugging. The resulting code was reviewed and tested locally.

## Local run

From PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
$env:DATABASE_URL = "sqlite:///./peblo_tv_mini.db"
$env:STORAGE_ROOT = ".\storage"
$env:DEMO_EDITOR_TOKEN = "demo-editor-token"
$env:DEMO_ADMIN_TOKEN = "demo-admin-token"
python -m backend.seed_shows --reset
uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

In separate terminals:

```powershell
cd cms; npm install; npm run dev -- --host 127.0.0.1 --port 5175
cd viewer; npm install; npm run dev -- --host 127.0.0.1 --port 5177
```

The API is at `http://127.0.0.1:8000`, CMS at `http://localhost:5175`, and Viewer at `http://localhost:5177`. Public catalogue reads use `/catalog`. For the demo recovery path, use the CMS Validation report and upload `assets/demo/valid-1600x900.jpg` for each artwork issue.