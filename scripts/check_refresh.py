"""Cheap schedule check; a missed trigger must not defer the next collection.

Only a valid, fresh, real publication may skip collection. Network failures,
invalid dates and malformed data request collection instead of hiding an outage.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

KIND = 'araquari_weather_dashboard_not_official_decision'


def refresh_needed(data: dict, now: datetime, *, min_age_minutes: int = 35) -> bool:
    if not isinstance(data, dict) or data.get('kind') != KIND or data.get('fixture_mode') or data.get('schema_version') != 1:
        return True
    try:
        generated = datetime.fromisoformat(data['generated_at'].replace('Z', '+00:00'))
        expiry = datetime.fromisoformat(data['valid_until'].replace('Z', '+00:00'))
        if generated.tzinfo is None or expiry.tzinfo is None:
            return True
        age = (now-generated).total_seconds()
        return age < -600 or age >= min_age_minutes*60 or expiry <= now
    except (KeyError, ValueError, TypeError, AttributeError):
        return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', choices=('true', 'false'), default='false')
    parser.add_argument('--github-output', type=Path, required=True)
    args = parser.parse_args()
    refresh = True
    reason = 'forced collection'
    if args.force != 'true':
        try:
            request = Request('https://guimig.github.io/criseclimatica/data/dashboard.json',
                              headers={'Cache-Control': 'no-cache', 'User-Agent': 'criseclimatica-refresh-check'})
            with urlopen(request, timeout=15) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Oversized dashboard')
            refresh = refresh_needed(json.loads(raw), datetime.now(timezone.utc))
            reason = 'publication requires collection' if refresh else 'publication is less than 35 minutes old'
        except (OSError, ValueError, TypeError):
            reason = 'publication could not be verified; collect rather than skip'
    with args.github_output.open('a', encoding='utf-8') as output:
        output.write(f'refresh={str(refresh).lower()}\n')
    print(f'Refresh check: {str(refresh).lower()} ({reason})')


if __name__ == '__main__':
    main()
