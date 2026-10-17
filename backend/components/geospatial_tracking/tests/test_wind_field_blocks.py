"""Sub-daily wind: 3-hour blocks and their use by the spread path (offline)."""

from datetime import date, timedelta

import pyproj
from shapely.prepared import prep

from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.spatial_timeline.districts import sri_lanka_land
from components.geospatial_tracking.services.spatial_timeline.engine import trace_source_path
from components.geospatial_tracking.services.spatial_timeline.wind_field import _with_blocks

TODAY = date(2026, 10, 13)


def test_hours_are_reduced_to_daily_and_3_hour_vectors():
    # 06-09 h wind FROM the west (toward east), 12-15 h FROM the south (toward north).
    hours = [("2026-10-13", h, 5.0, 270.0) for h in (6, 7, 8)] + [("2026-10-13", h, 5.0, 180.0) for h in (12, 13, 14)]
    day = _with_blocks(hours)["2026-10-13"]
    assert round(day["blocks"][2]["toward_deg"]) == 90 and round(day["blocks"][4]["toward_deg"]) == 0
    assert day["blocks"][0] is None and len(day["blocks"]) == 8
    assert 0 < day["toward_deg"] < 90  # daily mean between the two


def test_spread_path_follows_the_net_daily_wind_not_the_3_hour_swings():
    """Morning wind east, afternoon wind north (net north-east): the path follows
    the day's NET wind smoothly -- it does not zigzag with the sea/land breeze."""
    land = prep(sri_lanka_land().buffer(0.01))
    origin = (7.29, 80.63)  # inland (Kandy): no coast effects
    pts = [EligibleSourcePoint(source_id="O", latitude=origin[0], longitude=origin[1])]
    east = {"toward_deg": 90.0, "steadiness": 1.0, "kind": "TEST"}
    north = {"toward_deg": 0.0, "steadiness": 1.0, "kind": "TEST"}
    wind = {(TODAY + timedelta(days=d)).isoformat(): {"toward_deg": 45.0, "steadiness": 0.9, "kind": "TEST", "blocks": [east] * 4 + [north] * 4} for d in range(3)}
    trace = trace_source_path(origin[0], origin[1], pts, 3, land.contains, as_of=TODAY, wind_by_date=wind)
    geod = pyproj.Geod(ellps="WGS84")
    coords = trace["coords"]
    heads = [geod.inv(*coords[i], *coords[i + 1])[0] % 360 for i in range(len(coords) - 1)]
    assert max(abs(((heads[i + 1] - heads[i]) + 180) % 360 - 180) for i in range(len(heads) - 1)) < 15  # no zigzag
    overall = geod.inv(*coords[0], *coords[-1])[0] % 360
    assert abs(((overall - 45.0) + 180) % 360 - 180) < 45  # net north-east
