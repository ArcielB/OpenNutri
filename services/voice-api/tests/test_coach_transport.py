import base64
import json
from dataclasses import replace
from unittest.mock import AsyncMock

import httpx
import pytest

from opennutri_voice.gemini import GeminiClient, GeminiError
from opennutri_voice.models import CoachRequest


@pytest.mark.asyncio
async def test_voice_endpoint_retry_keeps_audio_schema_and_stateless_boundary(settings, monkeypatch):
    monkeypatch.setattr('opennutri_voice.gemini.asyncio.sleep', AsyncMock())
    requests = []
    output = {'headline': 'Fixture', 'message': 'Fixture reply', 'transcript': 'Fixture speech'}

    async def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={'status': 'completed', 'steps': [
            {'type': 'thought', 'content': [{'type': 'text', 'text': 'not final JSON'}]},
            {'type': 'user_input', 'content': [{'type': 'text', 'text': 'not final JSON'}]},
            {'type': 'model_output', 'content': [{'type': 'text', 'text': json.dumps(output)}]},
        ]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = GeminiClient(settings, client=transport)
        result = await client.generate_coach_voice_response(
            wav_bytes=b'fixture', language_hint='en-US',
            request=CoachRequest(mode='chat', local_date='2026-09-05'),
        )
    assert result.transcript == 'Fixture speech'
    assert len(requests) == 2
    original, retry = [json.loads(request.content) for request in requests]
    assert requests[1].url.path == '/v1beta/interactions'
    assert retry['store'] is False
    assert retry['model'] == settings.gemini_coach_model
    assert 'previous_interaction_id' not in retry
    assert retry['input'][1] == {'type': 'audio', 'mime_type': 'audio/wav',
                                 'data': base64.b64encode(b'fixture').decode()}
    assert retry['response_format']['schema'] == original['generationConfig']['responseJsonSchema']


@pytest.mark.asyncio
@pytest.mark.parametrize('response', [
    {'status': 'in_progress', 'steps': []},
    {'status': 'failed', 'steps': []},
    {'status': 'completed', 'steps': []},
    {'status': 'completed', 'steps': [{'type': 'thought', 'content': []}]},
    {'status': 'completed', 'steps': [{'type': 'model_output', 'content': [{'type': 'text', 'text': 12}]}]},
])
async def test_incomplete_or_nonfinal_interaction_cannot_become_advice(settings, monkeypatch, response):
    monkeypatch.setattr('opennutri_voice.gemini.asyncio.sleep', AsyncMock())
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        with pytest.raises(GeminiError) as error:
            await GeminiClient(settings, client=transport).generate_coach_response(
                CoachRequest(mode='oracle', local_date='2026-09-05'))
    assert error.value.error_code == 'gemini_invalid_output'
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [429, 503])
async def test_long_retry_hint_never_triggers_early_retry(settings, monkeypatch, status):
    sleep = AsyncMock()
    monkeypatch.setattr('opennutri_voice.gemini.asyncio.sleep', sleep)
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={'Retry-After': '30'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        with pytest.raises(GeminiError):
            await GeminiClient(settings, client=transport).generate_coach_response(
                CoachRequest(mode='oracle', local_date='2026-09-05'))
    assert len(calls) == 1
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_quota_retry_does_not_switch_endpoints(settings, monkeypatch):
    monkeypatch.setattr('opennutri_voice.gemini.asyncio.sleep', AsyncMock())
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={'Retry-After': '1'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        with pytest.raises(GeminiError) as error:
            await GeminiClient(settings, client=transport).generate_coach_response(
                CoachRequest(mode='oracle', local_date='2026-09-05'))
    assert error.value.is_rate_limited
    assert len(calls) == 2
    assert all(request.url.path.endswith(':generateContent') for request in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [429, 503])
@pytest.mark.parametrize('voice', [False, True])
async def test_configured_fallback_keeps_context_and_reports_actual_model(settings, monkeypatch, status, voice):
    monkeypatch.setattr('opennutri_voice.gemini.asyncio.sleep', AsyncMock())
    settings = replace(settings, gemini_coach_fallback_model='gemini-3.5-flash-lite')
    calls = []

    async def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(status)
        output = {'headline': 'Fixture', 'message': 'Fixture guidance', 'actions': []}
        if voice:
            output['transcript'] = 'Fixture speech'
        return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(output)}]}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = GeminiClient(settings, client=transport)
        request = CoachRequest(mode='chat' if voice else 'oracle', local_date='2026-09-05')
        if voice:
            output = await client.generate_coach_voice_response(wav_bytes=b'fixture', language_hint='en-US', request=request)
        else:
            output = await client.generate_coach_response(request)
    assert len(calls) == 2
    assert calls[1].url.path.endswith('/gemini-3.5-flash-lite:generateContent')
    assert output.resolved_model == 'gemini-3.5-flash-lite'
    assert 'resolved_model' not in output.model_dump()
    assert '_resolved_model' not in output.model_json_schema()['properties']
    primary, fallback = [json.loads(call.content) for call in calls]
    assert primary['contents'] == fallback['contents']
    assert primary['systemInstruction'] == fallback['systemInstruction']
    assert primary['generationConfig']['responseJsonSchema'] == fallback['generationConfig']['responseJsonSchema']
    assert fallback['generationConfig']['thinkingConfig']['thinkingLevel'] == 'minimal'


@pytest.mark.asyncio
async def test_failed_fallback_does_not_start_a_third_call(settings, monkeypatch):
    monkeypatch.setattr('opennutri_voice.gemini.asyncio.sleep', AsyncMock())
    settings = replace(settings, gemini_coach_fallback_model='gemini-3.5-flash-lite')
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        with pytest.raises(GeminiError):
            await GeminiClient(settings, client=transport).generate_coach_response(
                CoachRequest(mode='oracle', local_date='2026-09-05'))
    assert len(calls) == 2
