from __future__ import annotations

import io
import json
import logging
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import AuthenticationError, SubjectVerifier, SupabaseJwksVerifier
from .config import Settings
from .core_repository import CoreFoodRepository
from .gemini import GeminiClient, GeminiError
from .models import (
    CoachRequest,
    CoachResponse,
    CoachVoiceResponse,
    DeleteFeedbackResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    ResolutionResponse,
    ResolveTextRequest,
)
from .pipeline import ResolverPipeline
from .supabase_store import SupabasePrivateStore, SupabaseStoreError


SERVICE_VERSION = "0.4.2"
MAX_AUDIO_BYTES = 1024 * 1024
MAX_AUDIO_SECONDS = 30.0
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def validate_wav(payload: bytes) -> float:
    if not payload:
        raise HTTPException(status_code=422, detail="Audio file is empty")
    if len(payload) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio must not exceed 1 MB")
    try:
        with wave.open(io.BytesIO(payload), "rb") as audio:
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
            sample_rate = audio.getframerate()
            frames = audio.getnframes()
    except (wave.Error, EOFError) as exc:
        raise HTTPException(status_code=422, detail="Audio must be a valid PCM WAV") from exc
    if (channels, sample_width, sample_rate) != (1, 2, 16_000):
        raise HTTPException(
            status_code=422,
            detail="Audio must be 16 kHz, mono, 16-bit PCM WAV",
        )
    duration = frames / sample_rate
    if duration <= 0:
        raise HTTPException(status_code=422, detail="Audio contains no samples")
    if duration > MAX_AUDIO_SECONDS:
        raise HTTPException(status_code=413, detail="Audio must not exceed 30 seconds")
    return duration


def create_app(
    *,
    settings: Settings | None = None,
    core: CoreFoodRepository | None = None,
    store: SupabasePrivateStore | None = None,
    gemini: GeminiClient | None = None,
    verifier: SubjectVerifier | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_environment()
    resolved_core = core or CoreFoodRepository(resolved_settings.core_database_path)
    resolved_store = store or SupabasePrivateStore(resolved_settings)
    resolved_gemini = gemini or GeminiClient(resolved_settings)
    resolved_verifier = verifier or SupabaseJwksVerifier(
        jwks_url=resolved_settings.jwks_url,
        issuer=resolved_settings.jwt_issuer,
        audience=resolved_settings.supabase_jwt_audience,
    )
    pipeline = ResolverPipeline(
        settings=resolved_settings,
        core=resolved_core,
        store=resolved_store,
        gemini=resolved_gemini,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        resolved_core.validate()
        core_version = resolved_core.artifact_version()
        if core_version != resolved_settings.core_version:
            raise RuntimeError(
                f"Configured Core version {resolved_settings.core_version} "
                f"does not match database {core_version}"
            )
        application.state.settings = resolved_settings
        application.state.core = resolved_core
        application.state.store = resolved_store
        application.state.gemini = resolved_gemini
        application.state.verifier = resolved_verifier
        application.state.pipeline = pipeline
        yield

    application = FastAPI(
        title="OpenNutri Voice Resolver",
        summary="Bounded authenticated food resolution for voice and submitted text.",
        version=SERVICE_VERSION,
        lifespan=lifespan,
    )

    async def authenticated_subject(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> str:
        if credentials is None or credentials.scheme.casefold() != "bearer":
            raise HTTPException(status_code=401, detail="Bearer access token required")
        try:
            return await request.app.state.verifier.verify(credentials.credentials)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service_version=SERVICE_VERSION,
            core_version=resolved_settings.core_version,
            index_version=resolved_settings.index_version,
            providers_configured=bool(
                resolved_settings.supabase_url
                and resolved_settings.supabase_service_role_key
                and resolved_settings.gemini_api_key
            ),
        )

    @application.post(
        "/v1/voice/resolve",
        response_model=ResolutionResponse,
        tags=["resolution"],
    )
    async def resolve_voice(
        request: Request,
        audio: UploadFile = File(),
        language_hint: str = Form(default="auto", max_length=32),
        local_timestamp: str = Form(max_length=64),
        timezone: str = Form(max_length=64),
        subject: str = Depends(authenticated_subject),
    ) -> ResolutionResponse:
        if audio.content_type not in {
            "audio/wav",
            "audio/x-wav",
            "audio/wave",
            "application/octet-stream",
        }:
            raise HTTPException(status_code=415, detail="Audio must be WAV")
        payload = await audio.read(MAX_AUDIO_BYTES + 1)
        validate_wav(payload)
        request_id = str(uuid4())
        reserved = False
        try:
            quota = await request.app.state.store.reserve_request(
                subject=subject,
                request_id=request_id,
            )
            if not quota.get("allowed"):
                return request.app.state.pipeline.manual_search_response(
                    request_id=request_id,
                    query="",
                    error_code=str(quota.get("reason") or "quota_limited"),
                    audio_model=resolved_settings.audio_model_for_language(
                        language_hint
                    ),
                )
            reserved = True
            return await request.app.state.pipeline.resolve_voice(
                request_id=request_id,
                wav_bytes=payload,
                language_hint=language_hint,
                local_timestamp=local_timestamp,
                timezone_name=timezone,
            )
        except SupabaseStoreError:
            return request.app.state.pipeline.manual_search_response(
                request_id=request_id,
                query="",
                error_code="supabase_unavailable",
                audio_model=resolved_settings.audio_model_for_language(language_hint),
            )
        except GeminiError as exc:
            logger.warning(
                "voice_resolution_failed request_id=%s code=%s retryable=%s "
                "status=%s partial_transcript=%s",
                request_id,
                exc.error_code,
                exc.is_retryable,
                exc.http_status,
                exc.partial_transcript is not None,
            )
            return request.app.state.pipeline.manual_search_response(
                request_id=request_id,
                query=exc.partial_transcript or "",
                error_code=exc.error_code,
                audio_model=resolved_settings.audio_model_for_language(language_hint),
                transcript=exc.partial_transcript,
            )
        finally:
            if reserved:
                try:
                    await request.app.state.store.release_request(
                        subject=subject,
                        request_id=request_id,
                    )
                except SupabaseStoreError:
                    pass

    @application.post(
        "/v1/foods/resolve-text",
        response_model=ResolutionResponse,
        tags=["resolution"],
    )
    async def resolve_text(
        body: ResolveTextRequest,
        request: Request,
        subject: str = Depends(authenticated_subject),
    ) -> ResolutionResponse:
        request_id = str(uuid4())
        reserved = False
        try:
            quota = await request.app.state.store.reserve_request(
                subject=subject,
                request_id=request_id,
            )
            if not quota.get("allowed"):
                return request.app.state.pipeline.manual_search_response(
                    request_id=request_id,
                    query=body.query,
                    error_code=str(quota.get("reason") or "quota_limited"),
                    audio_model=None,
                )
            reserved = True
            return await request.app.state.pipeline.resolve_text(
                request_id=request_id,
                query=body.query,
                local_timestamp=body.local_timestamp,
                timezone_name=body.timezone,
            )
        except SupabaseStoreError:
            return request.app.state.pipeline.manual_search_response(
                request_id=request_id,
                query=body.query,
                error_code="supabase_unavailable",
                audio_model=None,
            )
        except GeminiError as exc:
            logger.warning(
                "text_resolution_failed request_id=%s code=%s retryable=%s "
                "status=%s",
                request_id,
                exc.error_code,
                exc.is_retryable,
                exc.http_status,
            )
            return request.app.state.pipeline.manual_search_response(
                request_id=request_id,
                query=body.query,
                error_code=exc.error_code,
                audio_model=None,
            )
        finally:
            if reserved:
                try:
                    await request.app.state.store.release_request(
                        subject=subject,
                        request_id=request_id,
                    )
                except SupabaseStoreError:
                    pass

    @application.post(
        "/v1/voice/feedback",
        response_model=FeedbackResponse,
        tags=["feedback"],
    )
    async def store_feedback(
        body: FeedbackRequest,
        request: Request,
        subject: str = Depends(authenticated_subject),
    ) -> FeedbackResponse:
        rows = [
            {
                "request_id": body.request_id,
                "source_phrase": item.source_phrase,
                "proposed_food_id": item.proposed_food_id,
                "final_food_id": item.final_food_id,
                "corrected": item.corrected,
                "core_version": body.core_version,
                "index_version": body.index_version,
                "model_version": body.model_version,
            }
            for item in body.items
        ]
        try:
            stored = await request.app.state.store.store_feedback(
                subject=subject,
                rows=rows,
            )
        except SupabaseStoreError as exc:
            raise HTTPException(status_code=503, detail="Feedback storage unavailable") from exc
        return FeedbackResponse(stored=stored)

    @application.post(
        "/v1/coach/respond",
        response_model=CoachResponse,
        tags=["coach"],
    )
    async def coach_respond(
        body: CoachRequest,
        request: Request,
        subject: str = Depends(authenticated_subject),
    ) -> CoachResponse:
        request_id = str(uuid4())
        reserved = False
        try:
            quota = await request.app.state.store.reserve_request(
                subject=subject,
                request_id=request_id,
            )
            if not quota.get("allowed"):
                raise HTTPException(status_code=429, detail="Coach request limit reached")
            reserved = True
            output = await request.app.state.gemini.generate_coach_response(body)
            return CoachResponse(
                **output.model_dump(),
                model=resolved_settings.gemini_coach_model,
            )
        except SupabaseStoreError as exc:
            raise HTTPException(status_code=503, detail="Coach temporarily unavailable") from exc
        except GeminiError as exc:
            logger.warning(
                "coach_request_failed request_id=%s mode=%s code=%s status=%s",
                request_id,
                body.mode,
                exc.error_code,
                exc.http_status,
            )
            raise HTTPException(status_code=503, detail="Coach temporarily unavailable") from exc
        finally:
            if reserved:
                try:
                    await request.app.state.store.release_request(
                        subject=subject,
                        request_id=request_id,
                    )
                except SupabaseStoreError:
                    pass

    @application.post(
        "/v1/coach/voice",
        response_model=CoachVoiceResponse,
        tags=["coach"],
    )
    async def coach_voice(
        request: Request,
        audio: UploadFile = File(),
        context: str = Form(max_length=32_000),
        language_hint: str = Form(default="auto", max_length=32),
        subject: str = Depends(authenticated_subject),
    ) -> CoachVoiceResponse:
        if audio.content_type not in {
            "audio/wav",
            "audio/x-wav",
            "audio/wave",
            "application/octet-stream",
        }:
            raise HTTPException(status_code=415, detail="Audio must be WAV")
        payload = await audio.read(MAX_AUDIO_BYTES + 1)
        validate_wav(payload)
        try:
            body = CoachRequest.model_validate(json.loads(context))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=422, detail="Invalid coach context") from exc
        if body.mode != "chat":
            raise HTTPException(status_code=422, detail="Voice coach requires chat mode")
        request_id = str(uuid4())
        reserved = False
        try:
            quota = await request.app.state.store.reserve_request(
                subject=subject,
                request_id=request_id,
            )
            if not quota.get("allowed"):
                raise HTTPException(status_code=429, detail="Coach request limit reached")
            reserved = True
            output = await request.app.state.gemini.generate_coach_voice_response(
                wav_bytes=payload,
                language_hint=language_hint,
                request=body,
            )
            return CoachVoiceResponse(
                **output.model_dump(),
                model=resolved_settings.gemini_coach_model,
            )
        except SupabaseStoreError as exc:
            raise HTTPException(status_code=503, detail="Coach temporarily unavailable") from exc
        except GeminiError as exc:
            logger.warning(
                "coach_voice_failed request_id=%s code=%s status=%s partial_transcript=%s",
                request_id,
                exc.error_code,
                exc.http_status,
                exc.partial_transcript is not None,
            )
            raise HTTPException(status_code=503, detail="Coach temporarily unavailable") from exc
        finally:
            if reserved:
                try:
                    await request.app.state.store.release_request(
                        subject=subject,
                        request_id=request_id,
                    )
                except SupabaseStoreError:
                    pass

    @application.delete(
        "/v1/voice/feedback",
        response_model=DeleteFeedbackResponse,
        tags=["feedback"],
    )
    async def delete_feedback(
        request: Request,
        subject: str = Depends(authenticated_subject),
    ) -> DeleteFeedbackResponse:
        try:
            await request.app.state.store.delete_feedback(subject=subject)
        except SupabaseStoreError as exc:
            raise HTTPException(status_code=503, detail="Feedback storage unavailable") from exc
        return DeleteFeedbackResponse(deleted=True)

    return application


app = create_app()
