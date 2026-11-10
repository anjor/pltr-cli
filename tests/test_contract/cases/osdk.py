"""Contract-test cases for src/pltr/commands/osdk.py (see __init__.py)."""

from tests import foundry_json_ontology as oj
from tests.osdk_fakes import FakeNode


def _fake_node(monkeypatch, tmp_path) -> None:
    """Node.js and npm are faked; the package goes to the test's directory."""
    monkeypatch.chdir(tmp_path)
    FakeNode().apply(monkeypatch)


SETUP = {"osdk generate": _fake_node}
ARGS = {
    "osdk generate": [
        "--ontology",
        "contract-test",
        "--object-type",
        "Employee",
        "--out",
        "osdk",
    ]
}
SUCCESS = {"osdk generate": [{"json": oj.ontology()}]}
