# /// script
# requires-python = ">=3.10"
# ///
"""Re-check the TfL data facts that PLAN.md relies on.

Run before the rehearsal and before recording:

        uv run docs/demos/tfl-station-outages/check_data.py
"""

import csv
import io
import json
import re
import statistics
import urllib.request
from collections import Counter

DISRUPTIONS = "https://api.tfl.gov.uk/StopPoint/Mode/tube/Disruption"
LIFTS = "https://api.tfl.gov.uk/Disruptions/Lifts/v2/"
FOOTFALL = (
    "https://crowding.data.tfl.gov.uk/Network%20Demand/StationFootfall_2025_2026%20.csv"
)


def get(url):
    # TfL's API answers 403 to urllib's default User-Agent.
    request = urllib.request.Request(url, headers={"User-Agent": "pltr-demo-check"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
        print(f"{response.status} {len(body) / 1000:,.0f} KB  {url}")
        return body


def kind(description):
    text = description.lower()
    return "escalator" if "escalator" in text else "lift" if "lift" in text else "other"


def plain(name):
    return name.removesuffix(" Underground Station")


def normalized(name):
    return re.sub(r"['’.]", "", plain(name))


disruptions = json.loads(get(DISRUPTIONS))
lifts = json.loads(get(LIFTS))
footfall = list(csv.DictReader(io.StringIO(get(FOOTFALL).decode("utf-8-sig"))))

print(
    f"\ndisruptions: {len(disruptions)}, {dict(Counter(kind(d['description']) for d in disruptions))}"
)
step_free = sum(
    bool(re.search(r"step.free", d["description"], re.I)) for d in disruptions
)
print(f"disruptions that say step free or step-free: {step_free}")

stations = {row["Station"] for row in footfall}
for label, key in (
    ("remove ' Underground Station'", plain),
    ("also drop ' and .", normalized),
):
    missed = [
        d["commonName"] for d in disruptions if key(d["commonName"]) not in stations
    ]
    print(
        f"name join, {label}: {len(disruptions) - len(missed)}/{len(disruptions)} match, missed {sorted(set(missed))}"
    )

codes = {d["stationAtcoCode"] for d in disruptions}
matched = sum(lift["stationUniqueId"] in codes for lift in lifts)
print(
    f"\nlift outages: {len(lifts)}, {matched} with a stationUniqueId equal to a disruption's stationAtcoCode"
)

print(f"\nfootfall columns: {list(footfall[0])}")
print(
    f"footfall dates: {footfall[0]['TravelDate']} to {max(row['TravelDate'] for row in footfall)}"
)
last = sorted({row["TravelDate"] for row in footfall})[-28:]
weekday = [
    row
    for row in footfall
    if row["TravelDate"] in last and row["DayOfWeek"] not in ("Saturday", "Sunday")
]
traffic = {}
for row in weekday:
    traffic.setdefault(row["Station"], []).append(
        int(row["EntryTapCount"]) + int(row["ExitTapCount"])
    )
busiest = sorted(traffic, key=lambda s: statistics.mean(traffic[s]), reverse=True)[:3]
print(
    f"busiest stations, mean weekday entries plus exits over the last 28 days: {busiest}"
)
