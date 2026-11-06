"""Non-blocking PR diagnostics of public institutional sources; never stores data.

No credentials. HTTPS probes do not bypass authentication, CAPTCHAs or access
restrictions. A green CI check does NOT imply every provider is online.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observatorio.config import load_locations  # noqa: E402
from observatorio.defesa_civil_sc import collect as collect_defesa  # noqa: E402
from observatorio.inmet_archive import ARCHIVE_ROOT  # noqa: E402
from observatorio.epagri_geo import collect as collect_geo  # noqa: E402
from observatorio.epagri_notices import collect as collect_advisories  # noqa: E402


def main() -> int:
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    locations = load_locations(ROOT / "config" / "locations.json")
    result = collect_defesa(locations, stamp)
    print(f"Defesa Civil SC: {result['status']}; method={result.get('retrieval_method', 'none')}; published={len(result.get('publications', []))}")
    print("Defesa Civil SC sanitized diagnostics:", result.get("source_diagnostics", [])[:5])
    address = f"{ARCHIVE_ROOT}{now.year}.zip"
    request = Request(address, method="HEAD", headers={"User-Agent": "criseclimatica/0.7 (public read-only status check)"})
    try:
        with urlopen(request, timeout=15) as response:
            size = response.headers.get("Content-Length", "unknown")
            print(f"INMET annual ZIP HEAD: HTTP {response.status}; Content-Length={size} bytes (if provided)")
    except HTTPError as exc:
        print(f"INMET annual ZIP HEAD: HTTP {exc.code}; HEAD may be unsupported; no download attempted")
    except (URLError, TimeoutError, OSError) as exc:
        print(f"INMET annual ZIP HEAD: unavailable ({type(exc).__name__}); no download attempted")
    geo = collect_geo(locations, stamp)
    registry_count = sum(len(item.get("stations", [])) for item in geo.get("locations", []))
    print(f"Epagri ArcGIS registry: {geo['status']}; nearby listings={registry_count}; source is metadata only")
    advisories = collect_advisories(stamp)
    print(f"Epagri/Ciram RSS advisories: {advisories['status']}; publications={len(advisories.get('notices', []))}")
    print("Network probes are informational; validate actual datasets after publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
