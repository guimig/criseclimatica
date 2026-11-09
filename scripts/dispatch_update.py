"""External scheduler entrypoint; server-side token, never browser code."""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = 'https://api.github.com/repos/guimig/criseclimatica/actions/workflows/pages.yml/dispatches'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def dispatch(token: str | None) -> None:
    if not isinstance(token, str) or not token or any(c.isspace() for c in token):
        raise RuntimeError('Configure GITHUB_UPDATE_TOKEN privately on the external scheduler')
    request = Request(ENDPOINT, data=json.dumps({'ref': 'main'}).encode(), method='POST', headers={
        'Accept': 'application/vnd.github+json', 'Authorization': 'Bearer '+token,
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'criseclimatica-external-scheduler',
        'Content-Type': 'application/json'})
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            if response.status != 204:
                raise RuntimeError('Unexpected response when dispatching update')
    except HTTPError as exc:
        raise RuntimeError(f'Update dispatch rejected: HTTP {exc.code}') from None
    except (URLError, OSError):
        raise RuntimeError('Update dispatch unavailable; keep the external retry policy active') from None


def main() -> int:
    try:
        dispatch(os.environ.get('GITHUB_UPDATE_TOKEN'))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print('Update dispatch accepted; collection and publication still depend on workflow completion.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
