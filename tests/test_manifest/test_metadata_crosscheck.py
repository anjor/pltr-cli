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
