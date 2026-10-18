"""Sri Lanka ADM2 district boundaries for the spatial timeline (read-only
reference data, see `reference/ATTRIBUTION.md`). WGS84 lon/lat."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pyproj
import shapely
from shapely.geometry import Point, shape
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union

_REFERENCE_PATH = Path(__file__).resolve().parent / "reference" / "sri_lanka_districts_adm2.geojson"
_GEOD = pyproj.Geod(ellps="WGS84")


@dataclass(frozen=True)
class District:
    name: str  # bare name, e.g. "Matara"
    shape_name: str  # geoBoundaries name, e.g. "Matara District"
    geometry: shapely.geometry.base.BaseGeometry


def normalize_district_name(raw: str | None) -> str | None:
    """"Matara", "MATARA DISTRICT", "5.95, 80.54 (Matara District)" -> "matara"."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith(")") and "(" in text:
        text = text[text.rindex("(") + 1 : -1]
    text = text.strip().casefold()
    if text.endswith(" district"):
        text = text[: -len(" district")].strip()
    return text or None


@lru_cache(maxsize=1)
def load_districts() -> tuple[District, ...]:
    with open(_REFERENCE_PATH, encoding="utf-8") as fh:
        collection = json.load(fh)
    districts = []
    for feature in collection["features"]:
        shape_name = feature["properties"]["shapeName"]
        geometry = shapely.make_valid(shape(feature["geometry"]))
        bare = shape_name[: -len(" District")] if shape_name.endswith(" District") else shape_name
        districts.append(District(name=bare, shape_name=shape_name, geometry=geometry))
    return tuple(sorted(districts, key=lambda d: d.name))


def find_district(raw_name: str | None) -> District | None:
    key = normalize_district_name(raw_name)
    if key is None:
        return None
    for district in load_districts():
        if district.name.casefold() == key:
            return district
    return None


@lru_cache(maxsize=1)
def sri_lanka_land() -> shapely.geometry.base.BaseGeometry:
    return shapely.make_valid(unary_union([d.geometry for d in load_districts()]))


_SRI_LANKA_METRIC_CRS = "EPSG:32644"  # WGS 84 / UTM 44N: covers all of Sri Lanka (78-84 E), scale error < 0.05%


@lru_cache(maxsize=1)
def _to_metric() -> pyproj.Transformer:
    return pyproj.Transformer.from_crs("EPSG:4326", _SRI_LANKA_METRIC_CRS, always_xy=True)


@lru_cache(maxsize=64)
def _metric_district_geometry(name: str):
    district = find_district(name)
    return shapely_transform(_to_metric().transform, district.geometry) if district is not None else None


def distance_to_district_km(district: District, latitude: float, longitude: float) -> float:
    """Distance (km) from a point to the district polygon; 0 inside it."""
    geometry = _metric_district_geometry(district.name)
    x, y = _to_metric().transform(float(longitude), float(latitude))
    return geometry.distance(Point(x, y)) / 1000.0


def geodesic_area_km2(geometry: shapely.geometry.base.BaseGeometry) -> float:
    if geometry is None or geometry.is_empty:
        return 0.0
    area_m2, _perimeter = _GEOD.geometry_area_perimeter(geometry)
    return abs(area_m2) / 1e6
