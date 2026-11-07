"""scripts/check_command_metadata.py: declared SDK metadata vs. what's reached.

The script is a report (static analysis can't follow every indirection), so
this only checks its machinery on commands whose calls are known.
"""

import pytest

from tests.test_manifest.conftest import load_script


@pytest.fixture(scope="module")
def reports():
    script = load_script("pltr_check_command_metadata", "check_command_metadata.py")
    return {report.path: report for report in script.check()}


def test_reports_cover_curated_commands_with_metadata(reports):
    assert "pltr folder get" in reports
    assert not any(path.startswith("pltr api ") for path in reports)
    assert "pltr commands list" in reports  # local: declares and reaches nothing
    assert reports["pltr commands list"].reached == []


def test_follows_services_into_the_sdk(reports):
    assert reports["pltr folder get"].reached == ["filesystem.Folder.get"]
    assert reports["pltr folder get"].ok
    # Through a lambda handed to collect_pages.
    assert reports["pltr folder list"].reached == ["filesystem.Folder.children"]
    # A service method that calls two SDK methods (read, then replace).
    assert reports["pltr space update"].reached == [
        "filesystem.Space.get",
        "filesystem.Space.replace",
    ]


def test_follows_composed_services(reports):
    """`pltr cp` -> CopyService -> self.dataset_service / self.folder_service."""
    report = reports["pltr cp"]
    assert "CopyService.copy_resource" in report.services
    assert {
        "datasets.Dataset.create",
        "filesystem.Folder.create",
        "filesystem.Resource.get",
    } <= set(report.reached)


def test_streamed_calls_count_as_the_method(reports):
    """`File.with_streaming_response.content` is the `File.content` endpoint."""
    report = reports["pltr dataset files get"]
    assert "datasets.Dataset.File.content" in report.reached
    assert not any("with_streaming_response" in path for path in report.reached)


SERVICES = """
class ThingService:
    def __init__(self):
        self.other = OtherService()

    def get(self):
        return self._fetch()

    def _fetch(self):
        return None

    def via_other(self):
        return self.other.run()


class OtherService:
    def run(self):
        return None

    def unused(self):
        return None
"""

COMMANDS = """
from ..services.thing import ThingService


def command():
    service = ThingService()
    _helper(service, 1)
    ThingService().via_other()


def _helper(svc, number):
    svc.get()


def unrelated(svc):
    svc.get()
"""


def test_walks_helpers_self_calls_and_composed_services(tmp_path):
    script = load_script("pltr_check_command_metadata", "check_command_metadata.py")
    (tmp_path / "services").mkdir()
    (tmp_path / "commands").mkdir()
    (tmp_path / "services" / "thing.py").write_text(SERVICES)
    (tmp_path / "commands" / "thing.py").write_text(COMMANDS)
    source = script.Source(tmp_path)

    reached = script.reached_functions(source, ("commands/thing.py", None, "command"))

    assert reached == {
        ("commands/thing.py", None, "command"),
        ("commands/thing.py", None, "_helper"),  # the service went in a parameter
        ("services/thing.py", "ThingService", "get"),
        ("services/thing.py", "ThingService", "_fetch"),  # self.method()
        ("services/thing.py", "ThingService", "via_other"),
        ("services/thing.py", "OtherService", "run"),  # self.other = OtherService()
    }
