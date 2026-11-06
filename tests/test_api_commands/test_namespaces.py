"""One generated `pltr api` command per SDK namespace, against a real FoundryClient.

Each case asserts the outgoing HTTP request (method, path, query including
`preview=true` for beta endpoints, JSON body) and that `--format json` prints the
SDK's own serialization of the decoded response, which for these realistic
responses is the response JSON itself.
"""

import json

import pytest

from pltr.commands.api import _specs

USER_ID = "f05f8da4-b84c-4fca-9c77-8af0b13d11de"
AGENT_RID = "ri.aip-agents..agent.0f1e9a2c-1111-4c2d-9a8b-123456789abc"
ORGANIZATION_RID = "ri.multipass..organization.7e4a0d6c-9f3b-4f7e-a3c8-1c9d2b4e5f60"
CONNECTION_RID = "ri.magritte..source.3b8f0a7e-2a1d-4c5e-9b6f-0e1d2c3b4a59"
CHECK_RID = "ri.data-health.main.check.5c2d7e1f-8a9b-4c3d-b2e1-f0a9b8c7d6e5"
DATASET_RID = "ri.foundry.main.dataset.c26f11c8-cdb3-4f44-9f5d-9816ea1c82da"
FOLDER_RID = "ri.compass.main.folder.01f6d8e2-ae50-4b4b-9d2a-34c0e1b2ba93"
SPACE_RID = "ri.compass.main.folder.7d9e3c1a-5b2f-4e8d-a6c4-2f1e0d9c8b7a"
QUERY_RID = "ri.function-registry.main.function.9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
MEDIA_SET_RID = "ri.mio.main.media-set.6a5b4c3d-2e1f-4a0b-9c8d-7e6f5a4b3c2d"
MEDIA_ITEM_RID = "ri.mio.main.media-item.1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
MODEL_RID = "ri.models.main.model.4f3e2d1c-0b9a-4c8d-a7e6-5f4e3d2c1b0a"
ONTOLOGY_RID = "ri.ontology.main.ontology.00000000-0000-0000-0000-000000000000"
BUILD_RID = "ri.foundry.main.build.a4386b7e-d546-49be-8a36-eefc355f5c58"
JOB_RID = "ri.foundry.main.job.aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
VIEW_RID = "ri.foundry-streaming.main.view.2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e"
TPA_RID = (
    "ri.third-party-applications.main.application.8e7d6c5b-4a3f-4e2d-b1c0-9f8e7d6c5b4a"
)
WIDGET_SET_RID = "ri.widgetregistry..widget-set.3c4d5e6f-7a8b-4c9d-8e0f-1a2b3c4d5e6f"

CASES = [
    pytest.param(
        ["admin", "user", "get", USER_ID],
        ("GET", f"/api/v2/admin/users/{USER_ID}", {}, None),
        {
            "id": USER_ID,
            "username": "jdoe",
            "givenName": "Jane",
            "realm": "palantir-internal-realm",
            "status": "ACTIVE",
            "attributes": {"multipass:email:primary": ["jdoe@example.com"]},
        },
        id="admin",
    ),
    pytest.param(
        ["aip-agents", "agent", "get", AGENT_RID, "--version", "1.0"],
        (
            "GET",
            f"/api/v2/aipAgents/agents/{AGENT_RID}",
            {"version": "1.0", "preview": "true"},
            None,
        ),
        {
            "rid": AGENT_RID,
            "version": "1.0",
            "metadata": {"displayName": "Helper", "suggestedPrompts": []},
            "parameters": {},
        },
        id="aip-agents",
    ),
    pytest.param(
        [
            "audit",
            "organization",
            "log-file",
            "list",
            ORGANIZATION_RID,
            "--start-date",
            "2026-01-01",
            "--page-size",
            "2",
        ],
        (
            "GET",
            f"/api/v2/audit/organizations/{ORGANIZATION_RID}/logFiles",
            {"startDate": "2026-01-01", "pageSize": "2"},
            None,
        ),
        {"data": [{"id": "log-1"}, {"id": "log-2"}], "nextPageToken": "page-2"},
        id="audit",
    ),
    pytest.param(
        [
            "checkpoints",
            "record",
            "search",
            "--where",
            json.dumps(
                {
                    "filter": {
                        "type": "textSearch",
                        "field": "justificationResponse",
                        "query": "audit",
                        "matchType": "CONTAINS",
                    }
                }
            ),
            "--sort-direction",
            "DESC",
        ],
        (
            "POST",
            "/api/v2/checkpoints/records/search",
            {"preview": "true"},
            {
                "where": {
                    "filter": {
                        "type": "textSearch",
                        "field": "justificationResponse",
                        "query": "audit",
                        "matchType": "CONTAINS",
                    }
                },
                "sortDirection": "DESC",
            },
        ),
        {"data": []},
        id="checkpoints",
    ),
    pytest.param(
        [
            "connectivity",
            "connection",
            "update-export-settings",
            CONNECTION_RID,
            "--export-settings",
            '{"exportsEnabled": true, "exportEnabledWithoutMarkingsValidation": false}',
        ],
        (
            "POST",
            f"/api/v2/connectivity/connections/{CONNECTION_RID}/updateExportSettings",
            {},
            {
                "exportSettings": {
                    "exportsEnabled": True,
                    "exportEnabledWithoutMarkingsValidation": False,
                }
            },
        ),
        None,
        id="connectivity",
    ),
    pytest.param(
        ["data-health", "check", "delete", CHECK_RID, "--yes"],
        ("DELETE", f"/api/v2/dataHealth/checks/{CHECK_RID}", {"preview": "true"}, None),
        None,
        id="data-health",
    ),
    pytest.param(
        ["datasets", "dataset", "get", DATASET_RID],
        ("GET", f"/api/v2/datasets/{DATASET_RID}", {}, None),
        {"rid": DATASET_RID, "name": "flights", "parentFolderRid": FOLDER_RID},
        id="datasets",
    ),
    pytest.param(
        ["filesystem", "folder", "get", FOLDER_RID],
        ("GET", f"/api/v2/filesystem/folders/{FOLDER_RID}", {}, None),
        {
            "rid": FOLDER_RID,
            "displayName": "Flights",
            "path": "/Analytics/Flights",
            "type": "FOLDER",
            "createdBy": USER_ID,
            "updatedBy": USER_ID,
            "createdTime": "2026-01-01T10:00:00+00:00",
            "updatedTime": "2026-01-02T10:00:00+00:00",
            "trashStatus": "NOT_TRASHED",
            "parentFolderRid": SPACE_RID,
            "spaceRid": SPACE_RID,
        },
        id="filesystem",
    ),
    pytest.param(
        [
            "functions",
            "query",
            "get-by-rid",
            "--rid",
            QUERY_RID,
            "--include-prerelease",
        ],
        (
            "GET",
            "/api/v2/functions/queries/getByRid",
            {"rid": QUERY_RID, "includePrerelease": "true", "preview": "true"},
            None,
        ),
        {
            "apiName": "getFlightCount",
            "parameters": {},
            "output": {"type": "integer"},
            "rid": QUERY_RID,
            "version": "1.2.0",
        },
        id="functions",
    ),
    pytest.param(
        [
            "language-models",
            "open-ai-model",
            "embeddings",
            "text-embedding-3-small",
            "--input",
            "hello",
            "--input",
            "world",
        ],
        (
            "POST",
            "/api/v2/languageModels/openAi/text-embedding-3-small/embeddings",
            {"preview": "true"},
            {"input": ["hello", "world"]},
        ),
        {
            "data": [[0.25, -0.5], [0.125, 0.75]],
            "model": "text-embedding-3-small",
            "usage": {"promptTokens": 2},
        },
        id="language-models",
    ),
    pytest.param(
        [
            "media-sets",
            "media-set",
            "get-rid-by-path",
            MEDIA_SET_RID,
            "--media-item-path",
            "/images/a.png",
        ],
        (
            "GET",
            f"/api/v2/mediasets/{MEDIA_SET_RID}/items/getRidByPath",
            {"mediaItemPath": "/images/a.png", "preview": "true"},
            None,
        ),
        {"mediaItemRid": MEDIA_ITEM_RID},
        id="media-sets",
    ),
    pytest.param(
        ["models", "model", "get", MODEL_RID],
        ("GET", f"/api/v2/models/{MODEL_RID}", {"preview": "true"}, None),
        {"rid": MODEL_RID},
        id="models",
    ),
    pytest.param(
        ["ontologies", "ontology", "get", "flights-ontology"],
        ("GET", "/api/v2/ontologies/flights-ontology", {}, None),
        {
            "apiName": "flights-ontology",
            "displayName": "Flights",
            "description": "Flight operations",
            "rid": ONTOLOGY_RID,
        },
        id="ontologies",
    ),
    pytest.param(
        ["orchestration", "build", "get", BUILD_RID],
        ("GET", f"/api/v2/orchestration/builds/{BUILD_RID}", {}, None),
        {
            "rid": BUILD_RID,
            "branchName": "master",
            "createdTime": "2026-01-01T10:00:00+00:00",
            "createdBy": USER_ID,
            "fallbackBranches": [],
            "jobRids": [JOB_RID],
            "retryCount": 0,
            "retryBackoffDuration": {"value": 1, "unit": "MINUTES"},
            "abortOnFailure": False,
            "status": "RUNNING",
        },
        id="orchestration",
    ),
    pytest.param(
        ["sql-queries", "sql-query", "get-status", "query-123"],
        ("GET", "/api/v2/sqlQueries/query-123/getStatus", {}, None),
        {"queryId": "query-123", "type": "running"},
        id="sql-queries",
    ),
    pytest.param(
        ["streams", "dataset", "stream", "get", DATASET_RID, "master"],
        ("GET", f"/api/v2/streams/datasets/{DATASET_RID}/streams/master", {}, None),
        {
            "branchName": "master",
            "schema": {
                "fields": [
                    {
                        "name": "flight_id",
                        "schema": {"nullable": False, "dataType": {"type": "string"}},
                    }
                ]
            },
            "viewRid": VIEW_RID,
            "partitionsCount": 1,
            "streamType": "LOW_LATENCY",
            "compressed": False,
        },
        id="streams",
    ),
    pytest.param(
        ["third-party-applications", "third-party-application", "get", TPA_RID],
        (
            "GET",
            f"/api/v2/thirdPartyApplications/{TPA_RID}",
            {"preview": "true"},
            None,
        ),
        {"rid": TPA_RID},
        id="third-party-applications",
    ),
    pytest.param(
        ["widgets", "widget-set", "get", WIDGET_SET_RID],
        (
            "GET",
            f"/api/v2/widgets/widgetSets/{WIDGET_SET_RID}",
            {"preview": "true"},
            None,
        ),
        {"rid": WIDGET_SET_RID},
        id="widgets",
    ),
]


def test_cases_cover_every_namespace():
    covered = {case.values[0][0] for case in CASES}
    assert covered == set(_specs.NAMESPACES)


@pytest.mark.filterwarnings("error::UserWarning")
@pytest.mark.parametrize("args, expected_request, response", CASES)
def test_namespace_command(api_stub, pltr_api, args, expected_request, response):
    if response is None:
        api_stub.respond(204)
    else:
        api_stub.respond(200, json=response)

    result = pltr_api(*args, "--format", "json")

    assert result.exit_code == 0, result.output
    method, path, query, body = expected_request
    (request,) = api_stub.requests
    assert request.method == method
    assert request.url.path == path
    assert dict(request.url.params) == query
    if body is None:
        assert request.content in (b"", b"null")
    else:
        assert json.loads(request.content) == body
    assert json.loads(result.stdout) == response
    assert result.stderr == ""
