from opennutri_voice.config import Settings


def test_default_audio_models_prioritize_voice_latency(monkeypatch):
    monkeypatch.delenv("OPENNUTRI_GEMINI_AUDIO_MODEL", raising=False)
    monkeypatch.delenv("OPENNUTRI_GEMINI_AUDIO_FALLBACK_MODEL", raising=False)

    settings = Settings.from_environment()

    assert settings.gemini_audio_model == "gemini-3.1-flash-lite"
    assert settings.gemini_audio_fallback_model == "gemini-3.5-flash-lite"
    assert settings.gemini_request_timeout_seconds == 12
