"""Contract-test cases for src/pltr/commands/site.py (see __init__.py)."""

from pathlib import Path

from tests import foundry_json as fj
from tests.test_contract.cases import resource_rid

#: A build folder with index.html at its root.
SITE_DIR = str(Path(__file__).parent / "data" / "site")
APPLICATION = resource_rid("third-party-application")
WEBSITE = {"deployedVersion": "1.0.0", "subdomains": ["app.apps.example.com"]}

ARGS = {
    "site deploy": [SITE_DIR, "--application", APPLICATION, "--version", "1.0.0"],
    "site rollback": ["1.0.0", "--application", APPLICATION],
}

SUCCESS = {
    # Version.get answers VersionNotFound (the version is new), then the
    # upload and the deploy.
    "site deploy": [
        {"status_code": 404, "json": fj.error("VersionNotFound")},
        {"json": {"version": "1.0.0"}},
        {"json": WEBSITE},
    ],
    "site rollback": [{"json": WEBSITE}],
    "site versions": [{"json": {"data": [{"version": "1.0.0"}]}}],
}
