from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Path as PathParameter, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .models import (
    CurrentReleaseResponse,
    FoodDetailResponse,
    FoodSearchResponse,
    HealthResponse,
)
from .repository import API_VERSION, CoreRepository, InvalidSearchQuery


def create_app(
    database_path: Path | None = None,
    *,
    cors_origins: tuple[str, ...] | None = None,
) -> FastAPI:
    environment = Settings.from_environment()
    settings = Settings(
        database_path=(database_path or environment.database_path).resolve(),
        cors_origins=environment.cors_origins if cors_origins is None else cors_origins,
    )
    repository = CoreRepository(settings.database_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        repository.validate()
        application.state.repository = repository
        yield

    application = FastAPI(
        title="OpenNutri Core API",
        summary="Read-only access to versioned, source-traceable food composition data.",
        version=API_VERSION,
        lifespan=lifespan,
    )
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["*"],
        )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health(request: Request) -> dict:
        return _repository(request).health()

    @application.get(
        "/v1/releases/current",
        response_model=CurrentReleaseResponse,
        tags=["releases"],
    )
    def current_release(request: Request) -> dict:
        return _repository(request).current_release()

    @application.get(
        "/v1/foods/search",
        response_model=FoodSearchResponse,
        tags=["foods"],
    )
    def search_foods(
        request: Request,
        q: str = Query(min_length=1, max_length=100, description="Food name or terms"),
        limit: int = Query(default=20, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10_000),
    ) -> dict:
        try:
            return _repository(request).search_foods(q, limit=limit, offset=offset)
        except InvalidSearchQuery as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.get(
        "/v1/foods/{food_id}",
        response_model=FoodDetailResponse,
        tags=["foods"],
        responses={404: {"description": "Food not found"}},
    )
    def food_detail(
        request: Request,
        food_id: str = PathParameter(min_length=1, max_length=100),
    ) -> dict:
        food = _repository(request).food_detail(food_id)
        if food is None:
            raise HTTPException(status_code=404, detail="Food not found")
        return food

    return application


def _repository(request: Request) -> CoreRepository:
    return request.app.state.repository


app = create_app()
