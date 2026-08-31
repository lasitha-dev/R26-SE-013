"""Checkpoint 6A Part 11: local, gitignored weather-response cache.

`FileWeatherCache` is duck-typed on purpose — `services/geospatial/weather/era5.py`'s
`build_pre_t0_weather_summary` accepts an optional `cache=` object and only
ever calls `.get(key)`/`.set(key, payload)` on it, so the lower-level
geospatial/weather package never imports this higher-level `features`
package (dependency injection, not import — keeps the layering in
`FEATURE_ASSEMBLY_PROTOCOL.md`'s diagram one-directional).

The cache key is a hash of the EXACT request parameters Open-Meteo
receives (`era5._hourly_request_params`'s own dict — model, lat/lon,
start_date/end_date, requested `hourly` variables, `timezone`) — Part 11's
required key material falls out of that dict directly rather than being
reconstructed separately, so the key can never silently drift from what
was actually requested. A cache entry is only ever read back for an
IDENTICAL request; nothing here ever fabricates a fallback value for a
key that doesn't match.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def cache_key_for_request(params: dict) -> str:
    """Pure: deterministic key from the exact request parameter dict."""
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FileWeatherCache:
    """One JSON file per cache key under `cache_dir` (default
    `local_data/cache/weather/`, covered by the repo-root `.gitignore`'s
    `/local_data/` rule — never committed)."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> dict | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, payload: dict) -> None:
        path = self._path_for(key)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        tmp.replace(path)
