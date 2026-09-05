"""Bounded live contract probes using synthetic data; prints no tokens or text."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opennutri_voice.models import CoachResponse, CoachVoiceResponse  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Explicitly spend up to four AI requests')
    parser.add_argument('--wav', type=Path, help='Optional committed synthetic WAV fixture for voice chat')
    parser.add_argument('--modes', nargs='+', choices=('daily', 'chat', 'oracle'),
                        default=['daily', 'chat', 'oracle'], help='Run only the selected checks')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required; these probes consume the shared beta quota')
    token = os.environ.get('OPENNUTRI_APP_ACCESS_TOKEN')
    public_key = os.environ.get('OPENNUTRI_APP_SUPABASE_PUBLISHABLE_KEY')
    if not token and not public_key:
        parser.error('Set OPENNUTRI_APP_ACCESS_TOKEN or OPENNUTRI_APP_SUPABASE_PUBLISHABLE_KEY')
    base = os.environ.get('OPENNUTRI_VOICE_API_BASE_URL', 'https://opennutri-voice-beta.vercel.app').rstrip('/')
    app_url = os.environ.get('OPENNUTRI_APP_SUPABASE_URL', 'https://xktsqscshecpnfvlqtoy.supabase.co').rstrip('/')
    with httpx.Client(timeout=40) as client:
        health = client.get(f'{base}/health')
        health.raise_for_status()
        print(json.dumps({'stage': 'health', 'service_version': health.json()['service_version']}), flush=True)
        if not token:
            auth = client.post(f'{app_url}/auth/v1/signup', headers={'apikey': public_key}, json={})
            auth.raise_for_status()
            token = auth.json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        context = {
            'locale': 'en-US', 'local_date': time.strftime('%Y-%m-%d'),
            'goal': 'Eat well', 'diet': 'Plant powered',
            'diet_notes': 'Simple, affordable meals', 'memories': ['Prefers lentils'],
            'daily_totals': [
                {'name': 'Protein', 'amount': 40, 'unit': 'g', 'target': 100},
                {'name': 'Vitamin D', 'amount': None, 'unit': 'mcg', 'target': 20,
                 'logged_foods_with_value': 0, 'logged_food_count': 2},
            ],
            'recent_foods': [],
        }
        for mode in dict.fromkeys(args.modes):
            body = {**context, 'mode': mode}
            if mode == 'chat':
                body.update(user_message='What is another quick option?', conversation=[
                    {'role': 'assistant', 'text': 'A lentil bowl is one simple option.'},
                ])
            started = time.monotonic()
            response = client.post(f'{base}/v1/coach/respond', headers=headers, json=body)
            response.raise_for_status()
            result = CoachResponse.model_validate(response.json())
            if mode != 'chat' and result.memory_updates:
                raise ValueError('Non-chat response returned memory updates')
            if mode == 'oracle' and (not result.actions or not all(action.search_query for action in result.actions)):
                raise ValueError('Oracle action missing Core search query')
            print(json.dumps({'stage': mode, 'seconds': round(time.monotonic() - started, 2),
                              'model': result.model, 'actions': len(result.actions),
                              'memory_updates': len(result.memory_updates)}), flush=True)
        if args.wav:
            started = time.monotonic()
            with args.wav.open('rb') as audio:
                response = client.post(f'{base}/v1/coach/voice', headers=headers,
                    files={'audio': ('fixture.wav', audio, 'audio/wav')},
                    data={'context': json.dumps({**context, 'mode': 'chat'}), 'language_hint': 'en-US'})
            response.raise_for_status()
            result = CoachVoiceResponse.model_validate(response.json())
            print(json.dumps({'stage': 'voice_chat', 'seconds': round(time.monotonic() - started, 2),
                              'model': result.model, 'transcript_present': bool(result.transcript)}), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        # Do not print request/response bodies or access tokens on errors.
        print(json.dumps({'stage': 'failed', 'error_type': type(exc).__name__,
                          'status': exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None}))
        raise SystemExit(1)
