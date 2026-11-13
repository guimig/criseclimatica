"""Non-blocking PR diagnostics of public institutional sources; never stores data.

No credentials. HTTPS probes do not bypass authentication, CAPTCHAs or access
restrictions. A green CI check does NOT imply every provider is online.
"""

from __future__ import annotations

import sys
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observatorio.metar import fetch_metars, normalize_metars, MetarSourceError
from observatorio.config import load_locations  # noqa: E402
from observatorio.defesa_civil_sc import collect as collect_defesa  # noqa: E402
from observatorio.inmet_archive import ARCHIVE_ROOT  # noqa: E402
from observatorio.epagri_geo import collect as collect_geo  # noqa: E402
from observatorio.epagri_notices import collect as collect_advisories  # noqa: E402
from observatorio.epagri_bulletins import collect as collect_bulletins  # noqa: E402



def probe_defesa_routes():
    """Public endpoint timings only; no headers, tokens or proxy values."""
    paths=[('www','https://www.defesacivil.sc.gov.br/wp-json/wp/v2/posts?per_page=1&_fields=link'),
           ('apex','https://defesacivil.sc.gov.br/wp-json/wp/v2/posts?per_page=1&_fields=link'),
           ('rest_route','https://www.defesacivil.sc.gov.br/?rest_route=/wp/v2/posts&per_page=1&_fields=link'),
           ('cap_federal','https://idapfile.mdr.gov.br/idap/api/rss/cap')]
    def read(item):
        name,url=item;start=time.monotonic()
        try:
            with urlopen(Request(url,headers={'User-Agent':'criseclimatica-network-diagnostic/1'}),timeout=12) as reply:
                reply.read(1024)
                return {'route':name,'status':reply.status,'elapsed':round(time.monotonic()-start,2)}
        except HTTPError as exc:return {'route':name,'http':exc.code,'elapsed':round(time.monotonic()-start,2)}
        except (OSError,ValueError) as exc:return {'route':name,'error':type(exc).__name__,'elapsed':round(time.monotonic()-start,2)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(read,paths):print('DEFESA_ROUTE',json.dumps(result))
    for family in ('--ipv4','--ipv6'):
        try:
            result=subprocess.run(['curl',family,'--connect-timeout','6','--max-time','12','--silent','--output','/dev/null',
                '--write-out','%{http_code} dns=%{time_namelookup} connect=%{time_connect} tls=%{time_appconnect} first_byte=%{time_starttransfer}',paths[0][1]],capture_output=True,text=True,timeout=14)
            print('DEFESA_CURL',family,'exit='+str(result.returncode),result.stdout.strip()[:180])
        except (OSError,subprocess.TimeoutExpired):print('DEFESA_CURL',family,'failed')


def main() -> int:
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    locations = load_locations(ROOT / "config" / "locations.json")
    probe_defesa_routes()
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
    editorial = collect_bulletins(stamp)
    print(f"Epagri/Ciram editorial forecast RSS: {editorial['status']}; bulletins={len(editorial.get('bulletins', []))}")
    try:
        metars = normalize_metars(fetch_metars(), locations, stamp)
        codes = ",".join(row["icao"] for row in metars["stations"])
        print(f"NOAA/METAR regional: {metars['status']}; stations={len(metars['stations'])}/6; codes={codes or 'none'}")
    except (MetarSourceError, OSError, ValueError) as exc:
        print(f"NOAA/METAR regional: unavailable ({type(exc).__name__})")
    print("Network probes are informational; validate actual datasets after publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

