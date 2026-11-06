"""Unit tests for the SDK call checker itself (scripts/sdk_calls.py, issue #185).

Most tests analyze small synthetic service modules against a fake SDK client whose
signatures are fixed here, so they don't change when the real SDK does. A few use the
real FoundryClient to show resolution works without network access.
"""

import textwrap
from types import SimpleNamespace
from typing import Dict, List, Optional

from scripts.sdk_calls import (
    LABELED_HTTP_EXCEPTIONS,
    PLTR_SRC,
    SdkCall,
    analyze_sources,
    compare_with_allowlist,
    find_violations,
    load_allowlist,
    render_allowlist,
    unused_labeled_exceptions,
)


# A fake SDK: namespaces/resources are SimpleNamespaces, methods plain functions.
def _folder_get(folder_rid, *, request_timeout=None, _sdk_internal={}): ...


def _folder_children(folder_rid, *, page_size=None, page_token=None): ...


def _folder_create(*, display_name, parent_folder_rid, request_timeout=None): ...


def _dataset_transactions(dataset_rid, *, page_size=None, preview=None): ...


def _connection_get(connection_rid): ...


FAKE_CLIENT = SimpleNamespace(
    filesystem=SimpleNamespace(
        Folder=SimpleNamespace(
            get=_folder_get, children=_folder_children, create=_folder_create
        )
    ),
    datasets=SimpleNamespace(
        Dataset=SimpleNamespace(transactions=_dataset_transactions)
    ),
    connectivity=SimpleNamespace(Connection=SimpleNamespace(get=_connection_get)),
)

HEADER = """\
import requests
from httpx import post as http_post

from .base import BaseService


class DemoService(BaseService):
    def _get_service(self):
        return self.client.filesystem

"""


def analyze(
    body: str,
    *,
    extra: Optional[Dict[str, str]] = None,
    labeled: Optional[Dict[str, str]] = None,
    client=FAKE_CLIENT,
) -> List[SdkCall]:
    """Analyze DemoService with ``body`` as extra methods (plus optional modules)."""
    source = HEADER + textwrap.indent(textwrap.dedent(body), "    ")
    sources = {"services/demo.py": source, **(extra or {})}
    return analyze_sources(sources, client=client, labeled_http=labeled or {})


def rules(calls: List[SdkCall]) -> List[str]:
    return sorted(v.rule_id for call in calls for v in call.violations)


def only(calls: List[SdkCall]) -> SdkCall:
    assert len(calls) == 1, calls
    return calls[0]


# ------------------------------------------------------------------ resolution


def test_resolves_get_service_chain_and_fills_the_record():
    call = only(
        analyze(
            """
            def get_folder(self, rid):
                return self.service.Folder.get(rid)
            """
        )
    )
    assert call.file == "services/demo.py"
    assert call.class_name == "DemoService"
    assert call.method == "get_folder"
    assert call.function == "DemoService.get_folder"
    assert call.sdk_path == "filesystem.Folder.get"
    assert call.kind == "sdk"
    assert call.resolved is True
    assert call.beta is False
    assert call.line == 13
    assert call.location == "src/pltr/services/demo.py:13"
    assert call.signature == "(folder_rid)"  # request_timeout/_sdk_internal left out
    assert call.violations == []


def test_client_root_and_beta_flag():
    call = only(
        analyze(
            """
            def transactions(self, rid):
                return self.client.datasets.Dataset.transactions(rid, preview=True)
            """
        )
    )
    assert call.sdk_path == "datasets.Dataset.transactions"
    assert call.beta is True
    assert call.violations == []


def test_missing_method_names_the_closest_match():
    call = only(
        analyze("def f(self, rid):\n    return self.service.Folder.gett(rid)\n")
    )
    assert call.resolved is False
    assert call.beta is None
    assert rules([call]) == ["missing-method"]
    assert "has no attribute 'gett'" in call.violations[0].message
    assert "closest: get" in call.violations[0].message


def test_missing_namespace():
    call = only(
        analyze(
            "def f(self):\n    return self.client.file_imports.FileImport.get('x')\n"
        )
    )
    assert call.sdk_path == "file_imports.FileImport.get"
    assert rules([call]) == ["missing-method"]
    assert "FoundryClient has no attribute 'file_imports'" in call.violations[0].message


def test_calling_a_resource_instead_of_a_method_is_missing_method():
    call = only(analyze("def f(self):\n    return self.service.Folder()\n"))
    assert rules([call]) == ["missing-method"]
    assert "is not a method" in call.violations[0].message


# ------------------------------------------------------------- argument binding


def test_unknown_keyword():
    calls = analyze(
        "def f(self, rid):\n    return self.service.Folder.get(rid, query='x')\n"
    )
    assert rules(calls) == ["unknown-keyword(query)"]


def test_missing_required_argument():
    calls = analyze(
        "def f(self):\n    return self.service.Folder.create(display_name='x')\n"
    )
    assert rules(calls) == ["missing-required(parent_folder_rid)"]


def test_keyword_only_argument_passed_positionally():
    calls = analyze("def f(self):\n    return self.service.Folder.create('x', 'y')\n")
    assert rules(calls) == [
        "missing-required(display_name)",
        "missing-required(parent_folder_rid)",
        "too-many-positional",
    ]


def test_argument_passed_positionally_and_by_keyword():
    calls = analyze(
        "def f(self, rid):\n    return self.service.Folder.get(rid, folder_rid=rid)\n"
    )
    assert rules(calls) == ["duplicate-argument(folder_rid)"]


def test_valid_call_has_no_violations():
    calls = analyze(
        """
        def f(self, rid):
            return self.service.Folder.children(rid, page_size=10, page_token=None)
        """
    )
    assert rules(calls) == []


# ------------------------------------------------------------------- preview


def test_preview_on_ga_method():
    # Not also an unknown keyword: the SDK drops preview= on GA methods (with a warning).
    calls = analyze(
        "def f(self, rid):\n    return self.service.Folder.get(rid, preview=True)\n"
    )
    assert rules(calls) == ["preview-on-ga"]


def test_beta_method_without_preview():
    calls = analyze(
        "def f(self, rid):\n    return self.client.datasets.Dataset.transactions(rid)\n"
    )
    assert rules(calls) == ["beta-without-preview"]


def test_beta_method_with_preview_variable_or_false():
    calls = analyze(
        """
        def f(self, rid, preview=False):
            self.client.datasets.Dataset.transactions(rid, preview=preview)
            self.client.datasets.Dataset.transactions(rid, preview=False)
        """
    )
    assert rules(calls) == ["beta-preview-not-literal", "beta-preview-not-literal"]
    assert "not preview=preview" in calls[0].violations[0].message


# -------------------------------------------------------------- kwargs / *args


def test_kwargs_dict_is_unchecked():
    calls = analyze(
        """
        def f(self, rid):
            params = {"page_size": 5}
            return self.service.Folder.children(rid, **params)
        """
    )
    # Required arguments can't be checked when a dict may supply them.
    assert rules(calls) == ["unchecked-kwargs"]
    assert "**params" in calls[0].violations[0].message


def test_kwargs_dict_still_checks_explicit_arguments():
    calls = analyze(
        """
        def f(self, rid):
            params = {"page_size": 5}
            return self.service.Folder.children(rid, preview=True, bogus=1, **params)
        """
    )
    assert rules(calls) == [
        "preview-on-ga",
        "unchecked-kwargs",
        "unknown-keyword(bogus)",
    ]


def test_beta_method_with_kwargs_isnt_also_reported_without_preview():
    calls = analyze(
        """
        def f(self, rid, extra):
            return self.client.datasets.Dataset.transactions(rid, **extra)
        """
    )
    assert rules(calls) == ["unchecked-kwargs"]


def test_star_args_are_unchecked():
    calls = analyze("def f(self, args):\n    return self.service.Folder.get(*args)\n")
    assert rules(calls) == ["unchecked-kwargs"]


# --------------------------------------------------------------- direct HTTP


def test_direct_http_calls_are_reported():
    calls = analyze(
        """
        def f(self, url):
            requests.get(url, timeout=5)
            http_post(url)
            self._make_request("GET", "/api/x")
        """
    )
    assert [c.sdk_path for c in calls] == [
        "requests.get",
        "httpx.post",
        "BaseService._make_request",
    ]
    assert all(c.kind == "http" for c in calls)
    assert rules(calls) == ["direct-http"] * 3


def test_labeled_http_exception_is_recorded_without_violation():
    calls = analyze(
        "def apply(self):\n    return self._make_request('POST', '/x')\n",
        labeled={"services/demo.py::DemoService.apply": "demo apply"},
    )
    call = only(calls)
    assert call.http_label == "demo apply"
    assert call.violations == []
    assert (
        unused_labeled_exceptions(calls, {"services/demo.py::DemoService.apply": "x"})
        == []
    )
    assert unused_labeled_exceptions(
        [], {"services/demo.py::DemoService.apply": "x"}
    ) == ["services/demo.py::DemoService.apply"]


def test_http_exception_classes_and_non_sdk_helpers_are_not_calls():
    calls = analyze(
        """
        def f(self, rid, config):
            try:
                return self._paginate_iterator(self.service.Folder.children(rid), config)
            except requests.HTTPError as e:
                raise requests.RequestException(str(e))
        """
    )
    assert [c.sdk_path for c in calls] == ["filesystem.Folder.children"]


def test_direct_http_in_command_module_function():
    command = "import requests\n\n\ndef verify(url):\n    return requests.post(url)\n"
    calls = analyze("", extra={"commands/verify.py": command})
    call = only(calls)
    assert (call.file, call.class_name, call.method) == (
        "commands/verify.py",
        None,
        "verify",
    )
    assert rules(calls) == ["direct-http"]


# ------------------------------------------------------------ alias following


def test_follows_local_aliases_of_service_and_methods():
    calls = analyze(
        """
        def f(self, rid):
            svc = self.service
            folders = svc.Folder
            folders.get(rid)
            create = self.service.Folder.create
            create(display_name="x", parent_folder_rid=rid, preview=True)
        """
    )
    assert [c.sdk_path for c in calls] == [
        "filesystem.Folder.get",
        "filesystem.Folder.create",
    ]
    assert rules(calls) == ["preview-on-ga"]


def test_follows_properties_accessors_and_literal_getattr():
    calls = analyze(
        """
        @property
        def folders(self):
            return self.client.filesystem.Folder

        def _connections(self):
            return getattr(self.client, "connectivity").Connection

        def f(self, rid):
            self.folders.get(rid)
            self._connections().get(rid)
        """
    )
    assert [c.sdk_path for c in calls] == [
        "filesystem.Folder.get",
        "connectivity.Connection.get",
    ]
    assert rules(calls) == []


def test_optional_getattr_candidate_that_doesnt_exist_is_dropped():
    # Feature detection: the code handles the legacy namespace being absent.
    calls = analyze(
        """
        @property
        def connections(self):
            legacy = getattr(self.client, "connections", None)
            if legacy is not None:
                return legacy
            return getattr(self.client, "connectivity", None)

        def f(self, rid):
            return self.connections.Connection.get(rid)
        """
    )
    assert [c.sdk_path for c in calls] == ["connectivity.Connection.get"]
    assert rules(calls) == []


def test_guarded_call_to_missing_method_is_still_reported():
    calls = analyze(
        """
        def f(self, rid):
            fn = getattr(self.service.Folder, "list_all", None)
            if fn is not None:
                return fn(rid)
        """
    )
    assert [c.sdk_path for c in calls] == ["filesystem.Folder.list_all"]
    assert rules(calls) == ["missing-method"]


def test_composed_service_and_pltr_methods():
    composer = textwrap.dedent(
        """
        from .demo import DemoService


        class CopyThing:
            def __init__(self, profile=None):
                self.demo = DemoService(profile=profile)

            def run(self, rid):
                self.demo.get_folder(rid)
                return self.demo.service.Folder.get(rid, preview=True)
        """
    )
    calls = analyze(
        "def get_folder(self, rid):\n    return self.service.Folder.get(rid)\n",
        extra={"services/copy_thing.py": composer},
    )
    composed = [c for c in calls if c.class_name == "CopyThing"]
    assert [(c.function, c.sdk_path) for c in composed] == [
        ("CopyThing.run", "filesystem.Folder.get")
    ]
    assert rules(composed) == ["preview-on-ga"]


# ---------------------------------------------------------------- uncheckable


def test_dynamic_attribute_name_is_uncheckable():
    call = only(
        analyze(
            "def f(self, name, rid):\n    return getattr(self.service.Folder, name)(rid)\n"
        )
    )
    assert call.sdk_path == "filesystem.Folder.<dynamic>"
    assert rules([call]) == ["uncheckable"]


def test_unresolvable_get_service_is_uncheckable():
    other = textwrap.dedent(
        """
        from .base import BaseService


        class OtherService(BaseService):
            def _get_service(self):
                return self._namespace

            def f(self):
                return self.service.Folder.get("x")
        """
    )
    calls = [
        c
        for c in analyze("", extra={"services/other.py": other})
        if c.class_name == "OtherService"
    ]
    assert [c.sdk_path for c in calls] == ["<service>.Folder.get"]
    assert rules(calls) == ["uncheckable"]


def test_sdk_method_passed_elsewhere_is_uncheckable_but_probes_are_fine():
    calls = analyze(
        """
        def f(self, config):
            if hasattr(self.service.Folder, "get") and callable(self.service.Folder.get):
                return self._paginate(self.service.Folder.children, config)
        """
    )
    call = only(calls)
    assert call.sdk_path == "filesystem.Folder.children"
    assert rules([call]) == ["uncheckable"]
    assert "is passed to self._paginate()" in call.violations[0].message


# ------------------------------------------------------------ real FoundryClient


def test_resolves_against_the_real_client_without_network():
    calls = analyze(
        """
        def f(self, rid):
            self.service.Folder.get(rid)
            self.service.Folder.does_not_exist(rid)
        """,
        client=None,  # the default: a real FoundryClient with a dummy token
    )
    assert [(c.sdk_path, c.resolved, c.beta) for c in calls] == [
        ("filesystem.Folder.get", True, False),
        ("filesystem.Folder.does_not_exist", False, None),
    ]
    assert rules(calls) == ["missing-method"]


# --------------------------------------------------------- keys and allowlist


def test_keys_are_stable_and_repeats_are_numbered():
    calls = analyze(
        """
        def f(self, rid):
            self.service.Folder.get(rid, preview=True)
            self.service.Folder.get(rid, preview=True)
        """
    )
    keys = [finding.key for finding in find_violations(calls)]
    base = "services/demo.py::DemoService.f::filesystem.Folder.get::preview-on-ga"
    assert keys == [base, f"{base}[2]"]


def test_allowlist_round_trip_and_ratchet(tmp_path):
    calls = analyze(
        """
        def f(self, rid):
            self.service.Folder.get(rid, preview=True)
            self.service.Folder.nope(rid)
        """
    )
    findings = find_violations(calls)
    path = tmp_path / "allowlist.txt"
    get_key = findings[0].key
    path.write_text(render_allowlist(findings, {get_key: "known, see #184"}))

    allowlist = load_allowlist(path)
    assert allowlist[get_key] == "known, see #184"
    nope_key = findings[1].key
    assert allowlist[nope_key].startswith("filesystem.Folder has no attribute 'nope'")
    assert compare_with_allowlist(findings, allowlist) == ([], [])

    # A fixed violation leaves a stale entry; a new one isn't allowlisted.
    new, stale = compare_with_allowlist(findings[1:], {nope_key: "x", "gone::key": "y"})
    assert [f.key for f in new] == []
    assert stale == ["gone::key"]
    new, stale = compare_with_allowlist(findings, {nope_key: "x"})
    assert [f.key for f in new] == [get_key]
    assert stale == []


def test_labeled_exceptions_exist_in_the_source():
    for key in LABELED_HTTP_EXCEPTIONS:
        file, function = key.split("::")
        cls, method = function.split(".")
        source = (PLTR_SRC / file).read_text(encoding="utf-8")
        assert f"class {cls}" in source and f"def {method}(" in source, key
