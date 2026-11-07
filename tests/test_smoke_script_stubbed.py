"""scripts/smoke.py run for real against a fake Foundry (no network).

Every check (except the `auth` group, whose point is real authentication)
runs the real pltr CLI in-process against ``stub_foundry_http``, answered by a
small stateful fake of the endpoints the checks call: uploads can be listed
and downloaded again, trashed resources report their trash status, and so
on. It shows that the check table matches real pltr output: the commands
parse, the validators accept pltr's JSON, and each check finds what later
checks need. It is no substitute for the live run; it can't tell whether
Foundry behaves like the fake.
"""

import csv
import io
import itertools
import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
import pytest
import typer
from click.testing import CliRunner

from scripts import smoke
from tests import foundry_json as fj
from tests import foundry_json_admin as fj_admin
from tests import foundry_json_aip_agents as fj_aip
from tests import foundry_json_audit as fj_audit
from tests import foundry_json_connectivity as fj_conn
from tests import foundry_json_data_health as fj_dh
from tests import foundry_json_dataset as fj_ds
from tests import foundry_json_filesystem as fj_fs
from tests import foundry_json_functions as fj_fn
from tests import foundry_json_language_models as fj_lm
from tests import foundry_json_mediasets as fj_ms
from tests import foundry_json_models as fj_models
from tests import foundry_json_ontology as fj_ont
from tests import foundry_json_orchestration as fj_orch
from tests import foundry_json_sql as fj_sql
from tests import foundry_json_streams as fj_streams
from tests import foundry_json_widgets as fj_widgets

READ_DATASET = fj_ds.DATASET_RID
SCRATCH = "ri.compass.main.folder.5c7a1e9b-0000-4000-8000-00000000c0de"
SPACE = "ri.compass.main.folder.5c7a1e9b-0000-4000-8000-0000000005ac"
PROJECT = "ri.compass.main.folder.5c7a1e9b-0000-4000-8000-0000000000b1"
USER = fj_admin.user()
READ_FILES = {
    "data/small.csv": b"id,amount\n1,2.5\n",
    "data/big.csv": b"id,amount\n" + b"".join(b"%d,1.0\n" % i for i in range(100)),
}
LINK_TYPE = {
    "apiName": "manager",
    "displayName": "Manager",
    "status": "ACTIVE",
    "objectTypeApiName": "Employee",
    "cardinality": "ONE",
    "linkTypeRid": "ri.ontology.main.relation.0381eda6-69bb-4cb7-8ba0-c6158e094a05",
}

Response = Tuple[int, Dict[str, Any]]


def js(body: Any, status: int = 200) -> Response:
    return status, {"json": body}


def raw(content: bytes) -> Response:
    return 200, {
        "content": content,
        "headers": {"Content-Type": "application/octet-stream"},
    }


def empty() -> Response:
    return 204, {}


def not_found(name: str) -> Response:
    return js(fj.error(name, "NOT_FOUND"), 404)


def body(request: httpx.Request) -> Any:
    """The request's JSON body (None for no body or file content)."""
    try:
        return json.loads(request.content) if request.content else None
    except ValueError:
        return None


class FakeFoundry:
    """The endpoints the smoke checks call, with just enough state."""

    def __init__(self) -> None:
        self.ids = itertools.count(1)
        self.unrouted: List[str] = []
        self.seen: List[Tuple[str, str, Any]] = []
        # resource RID -> (type, name, parent); trash status by RID
        self.resources: Dict[str, Tuple[str, str, str]] = {}
        self.trash: Dict[str, str] = {}
        # dataset RID -> {path: content}, {branch: transaction}, schema fields
        self.files: Dict[str, Dict[str, bytes]] = {READ_DATASET: dict(READ_FILES)}
        self.branches: Dict[str, Dict[str, Optional[str]]] = {
            READ_DATASET: {"master": fj_ds.TRANSACTION_RID}
        }
        self.schemas: Dict[str, List[Dict[str, Any]]] = {
            READ_DATASET: fj_ds.DEFAULT_FIELDS
        }
        self.transactions: Dict[str, Dict[str, Any]] = {
            fj_ds.TRANSACTION_RID: fj_ds.transaction(
                status="COMMITTED", closed_time=fj_ds.CLOSED_TIME
            )
        }
        self.routes: List[Tuple[str, "re.Pattern[str]", Callable[..., Response]]] = []
        self._register()

    # -------------------------------------------------------------- plumbing

    def __call__(self, request: httpx.Request) -> Response:
        path = request.url.path
        self.seen.append((request.method, path, body(request)))
        for method, pattern, handler in self.routes:
            match = pattern.fullmatch(path)
            if match and method == request.method:
                return handler(request, **match.groupdict())
        self.unrouted.append(f"{request.method} {path}")
        return not_found("SmokeStubUnrouted")

    def route(
        self, method: str, pattern: str
    ) -> Callable[[Callable[..., Response]], Callable[..., Response]]:
        expression = re.compile(
            pattern.replace("{rid}", r"(?P<rid>[^/]+)")
            .replace("{name}", r"(?P<name>[^/]+)")
            .replace("{sub}", r"(?P<sub>[^/]+)")
            .replace("{path}", r"(?P<path>.+?)")
        )

        def register(handler: Callable[..., Response]) -> Callable[..., Response]:
            self.routes.append((method, expression, handler))
            return handler

        return register

    def new_rid(self, kind: str) -> str:
        return f"ri.{kind}.5c7a1e9b-0000-4000-8000-{next(self.ids):012d}"

    def resource(self, rid: str) -> Dict[str, Any]:
        kind, name, parent = self.resources.get(
            rid, ("COMPASS_FOLDER", "Scratch", SPACE)
        )
        return dict(
            fj.resource(rid, name, kind),
            parentFolderRid=parent,
            projectRid=PROJECT,
            spaceRid=SPACE,
            trashStatus=self.trash.get(rid, "NOT_TRASHED"),
        )

    def file(self, dataset: str, path: str) -> Dict[str, Any]:
        content = self.files[dataset][path]
        return fj_ds.file(path, size_bytes=str(len(content)))

    def table(self, dataset: str) -> bytes:
        if dataset == READ_DATASET:
            return fj_ds.arrow_stream({"id": [1, 2], "amount": [2.5, 3.5]})
        rows: List[Dict[str, str]] = []
        for path in sorted(self.files[dataset]):
            text = self.files[dataset][path].decode()
            rows.extend(csv.DictReader(io.StringIO(text)))
        return fj_ds.arrow_stream(
            {
                "id": [int(r["id"]) for r in rows],
                "name": [r["name"] for r in rows],
                "value": [float(r["value"]) for r in rows],
            }
        )

    # -------------------------------------------------------------- routes

    def _register(self) -> None:  # noqa: C901 - one route per endpoint
        r = self.route
        api = "/api/v2"

        # admin
        r("GET", f"{api}/admin/users/getCurrent")(lambda q: js(USER))
        r("GET", f"{api}/admin/users")(lambda q: js(fj_fs.page([USER])))
        r("POST", f"{api}/admin/users/search")(lambda q: js(fj_fs.page([USER])))
        r("GET", f"{api}/admin/groups")(lambda q: js(fj_fs.page([fj_admin.group()])))
        r("GET", f"{api}/admin/markings")(
            lambda q: js(fj_fs.page([fj_admin.marking()]))
        )
        r("GET", f"{api}/admin/markings/{{rid}}")(
            lambda q, rid: js(fj_admin.marking(rid))
        )
        r("PUT", f"{api}/admin/markings/{{rid}}")(
            lambda q, rid: js(fj_admin.marking(rid, body(q)["name"]))
        )
        r("GET", f"{api}/admin/organizations/{{rid}}")(
            lambda q, rid: js(fj_admin.organization(rid))
        )
        r("PUT", f"{api}/admin/organizations/{{rid}}")(
            lambda q, rid: js(fj_admin.organization(rid, body(q)["name"]))
        )
        r("GET", f"{api}/admin/organizations/{{rid}}/listAvailableRoles")(
            lambda q, rid: js({"data": [fj_admin.organization_role()]})
        )
        r("GET", f"{api}/admin/roles/{{rid}}")(lambda q, rid: js(fj_admin.role(rid)))
        r("GET", f"{api}/audit/organizations/{{rid}}/logFiles")(
            lambda q, rid: js(fj_audit.log_files(fj_audit.LOG_FILE_ID, token="next"))
        )

        # filesystem
        r("GET", f"{api}/filesystem/folders/{{rid}}")(self._folder_get)
        r("POST", f"{api}/filesystem/folders")(self._folder_create)
        r("GET", f"{api}/filesystem/folders/{{rid}}/children")(
            lambda q, rid: js(
                fj_fs.page([fj_fs.project_resource(PROJECT, "Smoke", SPACE)])
                if rid == SPACE
                else fj_fs.page([fj.resource(PROJECT, "Smoke")])
            )
        )
        r("GET", f"{api}/filesystem/resources/{{rid}}")(
            lambda q, rid: js(self.resource(rid))
        )
        r("DELETE", f"{api}/filesystem/resources/{{rid}}")(self._trash)
        r("POST", f"{api}/filesystem/resources/{{rid}}/restore")(self._restore)
        r("GET", f"{api}/filesystem/resources/{{rid}}/roles")(
            lambda q, rid: js(fj_fs.page([fj_fs.user_role(principal_id=USER["id"])]))
        )
        r("GET", f"{api}/filesystem/resources/{{rid}}/getAccessRequirements")(
            lambda q, rid: js(fj_fs.access_requirements())
        )
        r("GET", f"{api}/filesystem/spaces")(
            lambda q: js(fj_fs.page([fj.space(SPACE)], "next"))
        )
        r("GET", f"{api}/filesystem/spaces/{{rid}}")(lambda q, rid: js(fj.space(rid)))
        r("PUT", f"{api}/filesystem/spaces/{{rid}}")(
            lambda q, rid: js(fj.space(rid, body(q)["displayName"]))
        )
        r("POST", f"{api}/filesystem/projects/create")(self._project_create)
        r("GET", f"{api}/filesystem/projects/{{rid}}")(
            lambda q, rid: js(
                fj_fs.project(rid, trashStatus=self.trash.get(rid, "NOT_TRASHED"))
            )
        )

        # datasets
        r("POST", f"{api}/datasets")(self._dataset_create)
        r("GET", f"{api}/datasets/{{rid}}")(
            lambda q, rid: js(
                fj_ds.dataset(rid, self.resources.get(rid, ("", "sales", ""))[1])
            )
        )
        r("GET", f"{api}/datasets/{{rid}}/branches")(
            lambda q, rid: js(
                fj_ds.page([fj_ds.branch(n, t) for n, t in self.branches[rid].items()])
            )
        )
        r("POST", f"{api}/datasets/{{rid}}/branches")(self._branch_create)
        r("GET", f"{api}/datasets/{{rid}}/branches/{{name}}")(
            lambda q, rid, name: js(fj_ds.branch(name, self.branches[rid][name]))
        )
        r("DELETE", f"{api}/datasets/{{rid}}/branches/{{name}}")(self._branch_delete)
        r("GET", f"{api}/datasets/{{rid}}/files")(self._files_list)
        r("GET", f"{api}/datasets/{{rid}}/files/{{path}}/content")(
            lambda q, rid, path: raw(self.files[rid][path])
        )
        r("POST", f"{api}/datasets/{{rid}}/files/{{path}}/upload")(self._upload)
        r("GET", f"{api}/datasets/{{rid}}/files/{{path}}")(self._file_get)
        r("DELETE", f"{api}/datasets/{{rid}}/files/{{path}}")(self._file_delete)
        r("GET", f"{api}/datasets/{{rid}}/transactions")(
            lambda q, rid: js(fj_ds.page(list(self.transactions.values())[:1]))
        )
        r("POST", f"{api}/datasets/{{rid}}/transactions")(self._transaction_create)
        r("GET", f"{api}/datasets/{{rid}}/transactions/{{sub}}")(
            lambda q, rid, sub: js(self.transactions[sub])
        )
        r("POST", f"{api}/datasets/{{rid}}/transactions/{{sub}}/commit")(
            lambda q, rid, sub: self._close(sub, "COMMITTED")
        )
        r("POST", f"{api}/datasets/{{rid}}/transactions/{{sub}}/abort")(
            lambda q, rid, sub: self._close(sub, "ABORTED")
        )
        r("GET", f"{api}/datasets/{{rid}}/getSchema")(self._schema_get)
        r("PUT", f"{api}/datasets/{{rid}}/putSchema")(self._schema_put)
        r("GET", f"{api}/datasets/{{rid}}/readTable")(
            lambda q, rid: raw(self.table(rid))
        )
        r("GET", f"{api}/datasets/{{rid}}/getSchedules")(
            lambda q, rid: js(fj_ds.page([fj_orch.SCHEDULE_RID]))
        )
        r("POST", f"{api}/datasets/{{rid}}/jobs")(
            lambda q, rid: js(fj_ds.page([fj_ds.job()]))
        )
        r(
            "POST",
            "/foundry-schema-inference/api/datasets/{rid}/branches/{name}/schema",
        )(lambda q, rid, name: js(fj_ds.inference_response()))
        r("POST", "/foundry-metadata/api/schemas/datasets/{rid}/branches/{name}")(
            lambda q, rid, name: js(fj_ds.metadata_response())
        )

        # SQL: a query is running when submitted and has succeeded when asked
        r("POST", f"{api}/sqlQueries/execute")(
            lambda q: js(fj_sql.running(f"smoke-query-{next(self.ids)}"))
        )
        r("GET", f"{api}/sqlQueries/{{rid}}/getStatus")(
            lambda q, rid: js(fj_sql.succeeded(rid))
        )
        r("GET", f"{api}/sqlQueries/{{rid}}/getResults")(
            lambda q, rid: (200, fj_sql.results({"n": [1, 2], "msg": ["a", "b"]}))
        )
        r("POST", f"{api}/sqlQueries/{{rid}}/cancel")(lambda q, rid: empty())

        # ontologies
        ontology = f"{api}/ontologies/{{name}}"
        objects = f"{ontology}/objects/{{sub}}"
        r("GET", f"{api}/ontologies")(lambda q: js(fj_ont.page([fj_ont.ontology()])))
        r("GET", ontology)(lambda q, name: js(fj_ont.ontology(api_name=name)))
        r("GET", f"{ontology}/objectTypes")(
            lambda q, name: js(fj_ont.page([fj_ont.object_type()]))
        )
        r("GET", f"{ontology}/objectTypes/{{sub}}")(
            lambda q, name, sub: js(fj_ont.object_type(sub, datasources=True))
        )
        r("GET", f"{ontology}/objectTypes/{{sub}}/outgoingLinkTypes")(
            lambda q, name, sub: js(fj_ont.page([LINK_TYPE]))
        )
        r("GET", objects)(
            lambda q, name, sub: js(
                fj_ont.page(
                    [fj_ont.employee("EMP001"), fj_ont.employee("EMP002")],
                    totalCount="2",
                )
            )
        )
        r("GET", f"{objects}/{{rid}}")(
            lambda q, name, sub, rid: js(fj_ont.employee(rid))
        )
        r("GET", f"{objects}/{{rid}}/links/{{path}}")(
            lambda q, name, sub, rid, path: js(fj_ont.page([fj_ont.employee("EMP002")]))
        )
        r("POST", f"{objects}/search")(self._search)
        r("POST", f"{objects}/aggregate")(
            lambda q, name, sub: js(
                {
                    "accuracy": "ACCURATE",
                    "data": [{"group": {}, "metrics": [{"name": "count", "value": 2}]}],
                }
            )
        )
        r("POST", f"{objects}/count")(lambda q, name, sub: js(fj_ont.count_response(2)))
        r("POST", f"{ontology}/actions/{{sub}}/apply")(
            lambda q, name, sub: js(fj_ont.validate_response("VALID"))
        )

        # orchestration
        mine = dict(createdBy=USER["id"])
        r("POST", f"{api}/orchestration/builds/search")(
            lambda q: js(fj_ds.page([fj_orch.build(**mine)]))
        )
        r("GET", f"{api}/orchestration/builds/{{rid}}")(
            lambda q, rid: js(fj_orch.build(rid, **mine))
        )
        r("POST", f"{api}/orchestration/builds/getBatch")(
            lambda q: js(
                {"data": {i["buildRid"]: fj_orch.build(i["buildRid"]) for i in body(q)}}
            )
        )
        r("GET", f"{api}/orchestration/builds/{{rid}}/jobs")(
            lambda q, rid: js(fj_ds.page([fj_orch.job()]))
        )
        r("GET", f"{api}/orchestration/jobs/{{rid}}")(
            lambda q, rid: js(fj_orch.job(rid))
        )
        r("POST", f"{api}/orchestration/jobs/getBatch")(
            lambda q: js(
                {"data": {i["jobRid"]: fj_orch.job(i["jobRid"]) for i in body(q)}}
            )
        )
        r("GET", f"{api}/orchestration/schedules/{{rid}}")(
            lambda q, rid: js(fj_orch.schedule(rid))
        )
        r("GET", f"{api}/orchestration/schedules/{{rid}}/runs")(
            lambda q, rid: js(fj_ds.page([fj_orch.schedule_run()]))
        )

        # streams
        r("POST", f"{api}/streams/datasets/create")(self._stream_create)
        r("GET", f"{api}/streams/datasets/{{rid}}/streams/{{name}}")(
            lambda q, rid, name: js(fj_streams.stream(name))
        )
        r(
            "POST",
            f"{api}/highScale/streams/datasets/{{rid}}/streams/{{name}}/publishRecord",
        )(lambda q, rid, name: empty())

        # the other areas
        r("GET", f"{api}/functions/queries/{{name}}")(lambda q, name: js(fj_fn.query()))
        r("POST", f"{api}/functions/queries/getByRid")(lambda q: js(fj_fn.query()))
        r("POST", f"{api}/functions/queries/{{name}}/execute")(
            lambda q, name: js({"value": 42})
        )
        r("GET", f"{api}/mediasets/{{rid}}")(
            lambda q, rid: js(
                {
                    "rid": rid,
                    "mediaSchema": "IMAGERY",
                    "defaultBranchName": "master",
                    "transactionPolicy": {"type": "noTransactions"},
                    "pathsRequired": True,
                }
            )
        )
        items = f"{api}/mediasets/{{rid}}/items"
        r("GET", f"{items}/getRidByPath")(
            lambda q, rid: js(
                fj_ms.rid_by_path()
                if q.url.params.get("mediaItemPath") == "images/a.png"
                else {}
            )
        )
        r("GET", f"{items}/{{sub}}")(lambda q, rid, sub: js(fj_ms.item_info()))
        r("GET", f"{items}/{{sub}}/reference")(
            lambda q, rid, sub: js(fj_ms.media_reference())
        )
        agents = f"{api}/aipAgents/agents"
        r("GET", f"{agents}/allSessions")(lambda q: js(fj_fs.page([fj_aip.session()])))
        r("GET", f"{agents}/{{rid}}")(lambda q, rid: js(fj_aip.agent(rid)))
        r("GET", f"{agents}/{{rid}}/agentVersions")(
            lambda q, rid: js(fj_fs.page([fj_aip.agent_version()]))
        )
        r("GET", f"{agents}/{{rid}}/sessions")(
            lambda q, rid: js(fj_fs.page([fj_aip.session()]))
        )
        r("GET", f"{api}/widgets/widgetSets/{{rid}}")(
            lambda q, rid: js(fj_widgets.widget_set(rid))
        )
        r("GET", f"{api}/widgets/widgetSets/{{rid}}/releases")(
            lambda q, rid: js(fj_fs.page([fj_widgets.release()]))
        )
        r("GET", f"{api}/thirdPartyApplications/{{rid}}")(
            lambda q, rid: js({"rid": rid})
        )
        connection = f"{api}/connectivity/connections/{{rid}}"
        r("GET", connection)(lambda q, rid: js(fj_conn.connection(rid)))
        r("GET", f"{connection}/fileImports")(
            lambda q, rid: js(fj_conn.page(fj_conn.file_import()))
        )
        r("GET", f"{connection}/tableImports")(
            lambda q, rid: js(fj_conn.page(fj_conn.table_import()))
        )
        check = f"{api}/dataHealth/checks/{{rid}}"
        r("GET", check)(lambda q, rid: js(fj_dh.check(rid)))
        r("GET", f"{check}/checkReports/getLatest")(
            lambda q, rid: js({"data": [fj_dh.check_report()]})
        )
        r("GET", f"{check}/checkReports/{{sub}}")(
            lambda q, rid, sub: js(fj_dh.check_report(sub))
        )
        r("GET", f"{api}/models/modelStudioTrainers")(lambda q: js({"data": []}))
        r("GET", f"{api}/models/{{rid}}")(lambda q, rid: js(fj_models.model(rid)))
        r("GET", f"{api}/models/{{rid}}/versions")(
            lambda q, rid: js(fj_fs.page([fj_models.model_version()]))
        )
        r("GET", f"{api}/models/{{rid}}/versions/{{sub}}")(
            lambda q, rid, sub: js(fj_models.model_version(sub))
        )
        r("POST", f"{api}/languageModels/anthropic/{{name}}/messages")(
            lambda q, name: js(fj_lm.anthropic_response("OK"))
        )
        r("POST", f"{api}/languageModels/openAi/{{name}}/embeddings")(
            lambda q, name: js(fj_lm.embeddings_response())
        )

    # -------------------------------------------------------------- stateful handlers

    def _folder_create(self, request: httpx.Request) -> Response:
        data = body(request)
        rid = self.new_rid("compass.main.folder")
        self.resources[rid] = (
            "COMPASS_FOLDER",
            data["displayName"],
            data["parentFolderRid"],
        )
        return self._folder_get(request, rid)

    def _folder_get(self, request: httpx.Request, rid: str) -> Response:
        if rid == smoke.MISSING_FOLDER_RID:
            return not_found("FolderNotFound")
        kind, name, parent = self.resources.get(
            rid, ("COMPASS_FOLDER", "Scratch", SPACE)
        )
        return js(
            fj.folder(
                rid,
                name,
                parentFolderRid=parent,
                projectRid=PROJECT,
                spaceRid=SPACE,
                trashStatus=self.trash.get(rid, "NOT_TRASHED"),
            )
        )

    def _project_create(self, request: httpx.Request) -> Response:
        data = body(request)
        rid = self.new_rid("compass.main.folder")
        self.resources[rid] = ("COMPASS_FOLDER", data["displayName"], data["spaceRid"])
        return js(fj_fs.project(rid, data["displayName"], spaceRid=data["spaceRid"]))

    def _trash(self, request: httpx.Request, rid: str) -> Response:
        self.trash[rid] = "DIRECTLY_TRASHED"
        return empty()

    def _restore(self, request: httpx.Request, rid: str) -> Response:
        self.trash[rid] = "NOT_TRASHED"
        return empty()

    def _dataset_create(self, request: httpx.Request) -> Response:
        data = body(request)
        rid = self.new_rid("foundry.main.dataset")
        self.resources[rid] = ("FOUNDRY_DATASET", data["name"], data["parentFolderRid"])
        self.files[rid] = {}
        self.branches[rid] = {"master": None}
        return js(fj_ds.dataset(rid, data["name"], data["parentFolderRid"]))

    def _stream_create(self, request: httpx.Request) -> Response:
        data = body(request)
        rid = self.new_rid("foundry.main.dataset")
        self.resources[rid] = ("FOUNDRY_DATASET", data["name"], data["parentFolderRid"])
        return js(fj_streams.dataset(rid, data["name"]))

    def _files_list(self, request: httpx.Request, rid: str) -> Response:
        prefix = request.url.params.get("pathPrefix", "")
        paths = sorted(p for p in self.files[rid] if p.startswith(prefix))
        return js(fj_ds.page([self.file(rid, p) for p in paths]))

    def _file_get(self, request: httpx.Request, rid: str, path: str) -> Response:
        if path not in self.files[rid]:
            return not_found("FileNotFound")
        return js(self.file(rid, path))

    def _upload(self, request: httpx.Request, rid: str, path: str) -> Response:
        self.files[rid][path] = request.content
        transaction = request.url.params.get("transactionRid") or self._transaction(
            rid, "UPDATE", "COMMITTED"
        )
        return js(dict(self.file(rid, path), transactionRid=transaction))

    def _file_delete(self, request: httpx.Request, rid: str, path: str) -> Response:
        del self.files[rid][path]
        return empty()

    def _transaction(self, dataset: str, kind: str, status: str) -> str:
        rid = self.new_rid("foundry.main.transaction")
        self.transactions[rid] = fj_ds.transaction(rid, kind, status)
        self.branches[dataset]["master"] = rid
        return rid

    def _transaction_create(self, request: httpx.Request, rid: str) -> Response:
        kind = body(request)["transactionType"]
        return js(self.transactions[self._transaction(rid, kind, "OPEN")])

    def _close(self, transaction: str, status: str) -> Response:
        self.transactions[transaction] = dict(
            self.transactions[transaction], status=status, closedTime=fj_ds.CLOSED_TIME
        )
        return js(self.transactions[transaction])

    def _branch_create(self, request: httpx.Request, rid: str) -> Response:
        data = body(request)
        self.branches[rid][data["name"]] = data.get("transactionRid")
        return js(fj_ds.branch(data["name"], data.get("transactionRid")))

    def _branch_delete(self, request: httpx.Request, rid: str, name: str) -> Response:
        del self.branches[rid][name]
        return empty()

    def _schema_get(self, request: httpx.Request, rid: str) -> Response:
        if rid not in self.schemas:
            return not_found("SchemaNotFound")
        return js(fj_ds.schema_response(self.schemas[rid]))

    def _schema_put(self, request: httpx.Request, rid: str) -> Response:
        self.schemas[rid] = body(request)["schema"]["fieldSchemaList"]
        return js(fj_ds.schema_response(self.schemas[rid]))

    def _search(self, request: httpx.Request, name: str, sub: str) -> Response:
        where = body(request).get("where")
        matches = [fj_ont.employee("EMP001"), fj_ont.employee("EMP002")]
        if where and where.get("type") == "eq":
            matches = [m for m in matches if m.get(where["field"]) == where["value"]]
        return js(fj_ont.search_response(matches))


class InProcessRunner:
    """smoke.Runner that runs pltr in-process with click's CliRunner."""

    def __init__(self) -> None:
        from pltr.cli import app

        self.root = typer.main.get_command(app)
        self.cli = CliRunner()

    def __call__(self, argv, env, timeout) -> smoke.RunResult:
        start = time.monotonic()
        result = self.cli.invoke(self.root, list(argv), env=dict(env))
        return smoke.RunResult(
            result.exit_code, result.stdout, result.stderr, time.monotonic() - start
        )


INPUTS = {
    "dataset.rid": READ_DATASET,
    "sql.table": READ_DATASET,
    "action.name": "promoteEmployee",
    "action.parameters": '{"employee": "EMP001"}',
    "functions.query": fj_fn.QUERY_API_NAME,
    "functions.parameters": "{}",
    "media_sets.rid": fj_ms.MEDIA_SET_RID,
    "media_sets.item_path": "images/a.png",
    "aip_agents.agent_rid": fj_aip.AGENT_RID,
    "widgets.widget_set_rid": fj_widgets.WIDGET_SET_RID,
    "third_party_apps.application_rid": (
        "ri.third-party-applications.main.application.5c7a1e9b-0000-4000-8000-000000000a99"
    ),
    "connectivity.connection_rid": fj_conn.CONNECTION_RID,
    "data_health.check_rid": fj_dh.CHECK_RID,
    "models.model_rid": fj_models.MODEL_RID,
    "streams.dataset_rid": fj_streams.DATASET_RID,
    "streams.branch": "master",
    "language_models.anthropic_model": fj_lm.MODEL_API_NAME,
    "language_models.embedding_model": fj_lm.EMBEDDING_MODEL,
    "admin.replace_space_rid": SPACE,
    "admin.replace_organization_rid": fj_admin.ORG_RID,
    "admin.replace_marking_id": fj_admin.MARKING_ID,
    "writes.space_rid": SPACE,
}


@pytest.fixture
def fake_foundry(stub_foundry_http, isolated_home, mock_keyring, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    fake = FakeFoundry()
    stub_foundry_http.next_response = fake
    return fake


def test_every_check_passes_against_the_fake_foundry(
    fake_foundry, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)  # no ./smoke.toml
    groups = sorted({check.group for check in smoke.CHECKS} - {"auth"})
    args = ["--allow-writes", "--scratch-folder", SCRATCH, "--include-admin"]
    args += ["--profile", "smoke", "--only", *groups]
    for key, value in INPUTS.items():
        args += ["--set", f"{key}={value}"]
    out, err = io.StringIO(), io.StringIO()

    code = smoke.main(args, runner=InProcessRunner(), stdout=out, stderr=err)

    report = out.getvalue()
    assert not fake_foundry.unrouted, fake_foundry.unrouted
    not_passed = [
        line for line in report.splitlines() if re.match(r"^(FAIL|SKIP)\s", line)
    ]
    assert not not_passed, report
    assert code == 0, report
    expected = len(smoke.CHECKS) - sum(1 for c in smoke.CHECKS if c.group == "auth")
    assert report.startswith(f"pltr smoke test: {expected} passed, 0 failed, 0 skipped")
    assert "Left behind" not in report
    assert "  ontology.object_type = Employee" in report  # found by the checks

    # What was found by earlier checks drove later requests.
    searches = [
        b for m, p, b in fake_foundry.seen if p.endswith("/objects/Employee/search")
    ]
    assert {"type": "eq", "field": "employeeId", "value": "EMP001"} in [
        s.get("where") for s in searches if s
    ]
    # The write pass cleaned up: everything it created is in the trash.
    created = [rid for rid in fake_foundry.resources if rid != SCRATCH]
    folders = [
        rid for rid in created if fake_foundry.resources[rid][0] == "COMPASS_FOLDER"
    ]
    assert all(fake_foundry.trash.get(rid) == "DIRECTLY_TRASHED" for rid in folders)
