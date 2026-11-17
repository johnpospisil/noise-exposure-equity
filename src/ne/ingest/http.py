"""Small HTTP helpers: cached, resumable downloads and retrying JSON GETs."""

from __future__ import annotations

from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

USER_AGENT = "noise-exposure-equity research pipeline (python-requests)"
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=2, max=60), reraise=True)
def download(url: str, dest: Path, chunk: int = 1 << 20) -> Path:
    """Download ``url`` to ``dest`` unless it is already complete; resumes partial files."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = int(_session.head(url, timeout=60, allow_redirects=True).headers["Content-Length"])
    if dest.exists() and dest.stat().st_size == total:
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with _session.get(url, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()
        mode = "ab" if have and r.status_code == 206 else "wb"
        with open(part, mode) as f:
            for b in r.iter_content(chunk):
                f.write(b)
    if part.stat().st_size != total:
        raise OSError(f"incomplete download {url}: {part.stat().st_size} of {total} bytes")
    part.rename(dest)
    return dest


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=2, max=60), reraise=True)
def get_json(url: str, params: dict | None = None):
    r = _session.get(url, params=params, timeout=300)
    r.raise_for_status()
    return r.json()
