from __future__ import annotations

import json

import httpx
import pytest

from scripts import smoke_coach


def test_smoke_runs_remaining_modes_after_failure(monkeypatch, capsys):
    modes = []

    def handler(request):
        if request.url.path == '/health':
            return httpx.Response(200, json={'service_version': 'fixture'})
        mode = json.loads(request.content)['mode']
        modes.append(mode)
        if mode == 'chat':
            return httpx.Response(503, json={'private': 'never print this'})
        return httpx.Response(200, json={
            'headline': 'Fixture', 'message': 'Fixture advice', 'model': 'fixture',
            'actions': [{'title': 'Lentils', 'detail': 'Try a bowl', 'search_query': 'lentils'}],
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(smoke_coach.httpx, 'Client', lambda **kwargs: client)
    monkeypatch.setenv('OPENNUTRI_APP_ACCESS_TOKEN', 'private-test-token')
    monkeypatch.setattr('sys.argv', ['smoke_coach.py', '--live'])
    assert smoke_coach.main() == 1
    assert modes == ['daily', 'chat', 'oracle']
    output = capsys.readouterr().out
    assert 'private-test-token' not in output
    assert 'never print this' not in output
    rows = [json.loads(line) for line in output.splitlines()]
    assert [row['stage'] for row in rows] == ['health', 'daily', 'chat', 'oracle']
    assert rows[2]['status'] == 503
    assert rows[2]['result'] == 'failed'


def test_smoke_voice_only(monkeypatch, tmp_path, capsys):
    fixture = tmp_path / 'fixture.wav'
    fixture.write_bytes(b'fixture-not-real-audio')
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path == '/health':
            return httpx.Response(200, json={'service_version': 'fixture'})
        return httpx.Response(200, json={
            'headline': 'Fixture', 'message': 'Fixture advice',
            'model': 'fixture', 'transcript': 'private fixture transcript',
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(smoke_coach.httpx, 'Client', lambda **kwargs: client)
    monkeypatch.setenv('OPENNUTRI_APP_ACCESS_TOKEN', 'private-test-token')
    monkeypatch.setattr('sys.argv', ['smoke_coach.py', '--live', '--modes', '--wav', str(fixture)])
    assert smoke_coach.main() == 0
    assert paths == ['/health', '/v1/coach/voice']
    assert 'private fixture transcript' not in capsys.readouterr().out


def test_smoke_rejects_empty_selection_before_network(monkeypatch):
    monkeypatch.setattr('sys.argv', ['smoke_coach.py', '--live', '--modes'])
    with pytest.raises(SystemExit) as exc:
        smoke_coach.main()
    assert exc.value.code == 2
