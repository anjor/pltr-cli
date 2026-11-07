"""Arrow timestamps with a time zone decode without a system time zone database.

Windows (and minimal Linux containers) have no system tz database, so zoneinfo
falls back to the tzdata package, which pltr declares as a dependency.
"""

import zoneinfo
from datetime import datetime, timezone

import pyarrow as pa
import pytest

from pltr.contract import table_rows


@pytest.fixture
def no_system_tz_database():
    zoneinfo.reset_tzpath(to=[])
    zoneinfo.ZoneInfo.clear_cache()
    try:
        yield
    finally:
        zoneinfo.reset_tzpath()
        zoneinfo.ZoneInfo.clear_cache()


@pytest.mark.parametrize("tz", ["UTC", "Europe/London"])
def test_timezone_aware_timestamps_decode_without_system_tz_data(
    no_system_tz_database, tz
):
    moment = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    table = pa.table({"at": pa.array([moment], type=pa.timestamp("us", tz=tz))})

    columns, rows = table_rows(table)

    assert list(columns) == ["at"]
    assert len(rows) == 1
    assert rows[0]["at"]
