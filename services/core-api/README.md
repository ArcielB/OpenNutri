# OpenNutri Core API

This service exposes a versioned, read-only HTTP contract over an OpenNutri Core
SQLite release. The API never mutates the dataset and does not expose the SQLite
table layout directly, so future source adapters can preserve the HTTP contract.

## Run locally

Build the FNDDS release first if it is not already present:

```bash
python3 services/data-pipeline/scripts/build_core_dataset.py
```

Install and run the API:

```bash
cd services/core-api
python3 -m pip install -r requirements-dev.txt
python3 -m uvicorn opennutri_api.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive OpenAPI documentation
is at `http://127.0.0.1:8000/docs`.

The default database is the local FNDDS `v0.0.1` artifact. Override it with an
absolute or relative path:

```bash
OPENNUTRI_CORE_DB_PATH=/data/opennutri.sqlite \
  python3 -m uvicorn opennutri_api.main:app --host 0.0.0.0 --port 8000
```

Browser origins default to `http://localhost:5173` and
`http://127.0.0.1:5173`. Set a comma-separated production allowlist with
`OPENNUTRI_API_CORS_ORIGINS`. An explicitly empty value disables CORS.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /health` | Database availability, API version, and served artifact version |
| `GET /v1/releases/current` | Source release, coverage, checksum, and license metadata |
| `GET /v1/foods/search?q=apple&limit=20&offset=0` | Ranked and paginated food search |
| `GET /v1/foods/{food_id}` | Food provenance, quality, per-100 g nutrients, and portions |

Search input is converted to literal Unicode prefix tokens. Callers cannot inject
FTS operators. Search returns only `is_searchable` records; known excluded records
remain retrievable by ID for audit and provenance.

The API returns USDA nutrient observations unchanged on their stored
`per_100g_edible_portion` basis. Clients can calculate a portion value with:

```text
portion_value = per_100g_value * gram_weight / 100
```

## Validate

```bash
cd services/core-api
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Fixture tests cover validation, read-only access, safe search, pagination, ranking,
details, provenance, error behavior, and OpenAPI. When the local full release is
present, the suite also runs a real FNDDS search/detail smoke test. Set
`OPENNUTRI_SKIP_REAL_RELEASE_TEST=1` only when that local integration test must be
suppressed.

## Current boundary

This is the first local product API, not a deployed public service. It has no write
routes, authentication, diaries, user data, AI features, or rate limiting. Search
ranking must pass the reviewed common-query benchmark before it is treated as a
stable public ranking contract.
