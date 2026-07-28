from __future__ import annotations

from fastapi.testclient import TestClient

from opennutri_voice.core_repository import CoreFoodRepository
from opennutri_voice.main import create_app
from opennutri_voice.models import (
    AudioExtraction,
    ExtractedConcept,
    ExtractedQuantity,
    SelectorDecision,
    SelectorOutput,
)

from .conftest import make_wav


class StubVerifier:
    async def verify(self, token: str) -> str:
        if token != "valid-token":
            raise RuntimeError("bad token")
        return "00000000-0000-0000-0000-000000000001"


class StubStore:
    def __init__(self):
        self.allowed = True
        self.feedback = []
        self.deleted_subject = None
        self.released = []

    async def reserve_request(self, *, subject, request_id):
        return {"allowed": self.allowed, "reason": "user_daily_limit"}

    async def release_request(self, *, subject, request_id):
        self.released.append((subject, request_id))

    async def semantic_search(self, *, embedding, limit):
        return [{"food_id": "food-apple", "similarity": 0.99}]

    async def store_feedback(self, *, subject, rows):
        self.feedback.extend(rows)
        assert all(
            set(row)
            == {
                "request_id",
                "source_phrase",
                "proposed_food_id",
                "final_food_id",
                "corrected",
                "core_version",
                "index_version",
                "model_version",
            }
            for row in rows
        )
        return len(rows)

    async def delete_feedback(self, *, subject):
        self.deleted_subject = subject


class StubGemini:
    async def transcribe_and_extract(self, *, wav_bytes, language_hint):
        return AudioExtraction(
            transcript="one hundred grams apple",
            detected_language="en",
            concepts=[
                ExtractedConcept(
                    source_phrase="one hundred grams apple",
                    food_name="apple",
                    quantity=ExtractedQuantity(value=100, unit="g"),
                    preparation=["raw"],
                    meal="breakfast",
                )
            ],
        )

    async def embed_concepts(self, concepts):
        return [[0.0] * 768 for _ in concepts]

    async def select_candidates(self, *, concepts, candidate_sets):
        return SelectorOutput(
            decisions=[
                SelectorDecision(
                    concept_index=0,
                    selected_food_id="food-apple",
                    alternative_food_ids=["food-apple-cooked"],
                    confidence=0.95,
                )
            ]
        )


def build_client(settings):
    store = StubStore()
    app = create_app(
        settings=settings,
        core=CoreFoodRepository(settings.core_database_path),
        store=store,
        gemini=StubGemini(),
        verifier=StubVerifier(),
    )
    return TestClient(app), store


def test_auth_audio_validation_and_bounded_voice_response(settings):
    client, store = build_client(settings)
    with client:
        missing_auth = client.post(
            "/v1/voice/resolve",
            files={"audio": ("meal.wav", make_wav(), "audio/wav")},
            data={
                "language_hint": "en",
                "local_timestamp": "2026-07-24T12:00:00",
                "timezone": "Europe/Istanbul",
            },
        )
        invalid_audio = client.post(
            "/v1/voice/resolve",
            headers={"authorization": "Bearer valid-token"},
            files={"audio": ("meal.wav", make_wav(sample_rate=8_000), "audio/wav")},
            data={
                "language_hint": "en",
                "local_timestamp": "2026-07-24T12:00:00",
                "timezone": "Europe/Istanbul",
            },
        )
        response = client.post(
            "/v1/voice/resolve",
            headers={"authorization": "Bearer valid-token"},
            files={"audio": ("meal.wav", make_wav(), "audio/wav")},
            data={
                "language_hint": "en",
                "local_timestamp": "2026-07-24T12:00:00",
                "timezone": "Europe/Istanbul",
            },
        )

    assert missing_auth.status_code == 401
    assert invalid_audio.status_code == 422
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "resolved"
    assert payload["items"][0]["selected_candidate"]["food_id"] == "food-apple"
    assert payload["items"][0]["quantity"]["grams"] == 100
    assert payload["items"][0]["meal_default"] == "breakfast"
    assert len(store.released) == 1


def test_quota_falls_back_to_lexical_manual_search(settings):
    client, store = build_client(settings)
    store.allowed = False
    with client:
        response = client.post(
            "/v1/foods/resolve-text",
            headers={"authorization": "Bearer valid-token"},
            json={
                "query": "apple",
                "local_timestamp": "2026-07-24T12:00:00",
                "timezone": "Europe/Istanbul",
            },
        )
    payload = response.json()
    assert payload["status"] == "manual_search"
    assert payload["error_code"] == "user_daily_limit"
    assert payload["manual_search_candidates"][0]["food_id"] == "food-apple"
    assert store.released == []


def test_feedback_contract_excludes_private_fields_and_deletes_by_subject(settings):
    client, store = build_client(settings)
    headers = {"authorization": "Bearer valid-token"}
    valid = {
        "request_id": "00000000-0000-0000-0000-000000000099",
        "core_version": "0.3.0",
        "index_version": "fixture-index",
        "model_version": "gemini-selector",
        "items": [
            {
                "source_phrase": "apple",
                "proposed_food_id": "food-apple-cooked",
                "final_food_id": "food-apple",
                "corrected": True,
            }
        ],
    }
    with client:
        stored = client.post("/v1/voice/feedback", headers=headers, json=valid)
        invalid = client.post(
            "/v1/voice/feedback",
            headers=headers,
            json={**valid, "transcript": "the complete private transcript"},
        )
        deleted = client.delete("/v1/voice/feedback", headers=headers)

    assert stored.status_code == 200
    assert stored.json() == {"stored": 1}
    assert invalid.status_code == 422
    assert deleted.json() == {"deleted": True}
    assert store.deleted_subject == "00000000-0000-0000-0000-000000000001"
