# OpenNutri Core API

This service exposes a versioned, read-only HTTP contract over an OpenNutri Core
SQLite release. The API never mutates the dataset and does not expose the SQLite
table layout directly, so future source adapters can preserve the HTTP contract.

## Run locally

Build the combined USDA release first if it is not already present:

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

The default database is the local USDA Core `v0.1.0` artifact. Override it with an
absolute or relative path:

```bash
OPENNUTRI_CORE_DB_PATH=/data/opennutri.sqlite \
  python3 -m uvicorn opennutri_api.main:app --host 0.0.0.0 --port 8000
```

Browser origins default to `http://localhost:5173` and
`http://127.0.0.1:5173`. Set a comma-separated production allowlist with
`OPENNUTRI_API_CORS_ORIGINS`. An explicitly empty value disables CORS.

## Deploy on Vercel

Create a Vercel project from this repository with `services/core-api` as its
root directory. No environment variables are required for the API-only deploy.
The repository's `vercel.json` runs `scripts/fetch_core_release.py` during the
build and bundles the resulting read-only SQLite database with the FastAPI
function.

The build downloads the fixed `core-usda-v0.1.0` asset from the
[GitHub release](https://github.com/ArcielB/OpenNutri/releases/tag/core-usda-v0.1.0).
It verifies the compressed and expanded file sizes and SHA-256 checksums before
installation. A changed, partial, or unavailable artifact fails the deployment
instead of serving unverified data.

When a browser frontend is deployed, set `OPENNUTRI_API_CORS_ORIGINS` in Vercel
to its exact origin, such as `https://app.example.com`. Multiple origins are
comma-separated.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /health` | Database availability, API version, and served artifact version |
| `GET /v1/releases/current` | Source release, coverage, checksum, and license metadata |
| `GET /v1/foods/search?q=apple&limit=20&offset=0` | Ranked and paginated food search |
| `GET /v1/foods/{food_id}` | Food provenance, quality, per-100 g nutrients, and portions |

Search input is converted to literal Unicode prefix tokens. Callers cannot inject
FTS operators. If every term has no common match, search returns the largest, most
selective matching subset and identifies it with `match_mode=partial_terms` and
`matched_terms`. Search returns only `is_searchable` records; known excluded records
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
present, the suite also runs combined-release search/detail smoke tests. Set
`OPENNUTRI_SKIP_REAL_RELEASE_TEST=1` only when that local integration test must be
suppressed.

## Current boundary

This is a public read-only data API. It has no write routes, authentication, user
data, or rate limiting. Search ranking must pass the reviewed common-query benchmark
before it is treated as a stable public ranking contract.
