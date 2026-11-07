"""Realistic Foundry connectivity API JSON bodies for stub_foundry_http tests.

Bodies use the API's own field names (camelCase) and shapes, so the SDK
decodes them into its real ``Connection``, ``FileImport`` and ``TableImport``
models. They contain no timestamps, so pltr's JSON output equals the body.
"""

from typing import Any, Dict, Iterable

CONNECTION_RID = "ri.magritte..source.6f1e2d3c-0000-4000-8000-000000000001"
FOLDER_RID = "ri.compass.main.folder.5a4b3c2d-0000-4000-8000-000000000002"
DATASET_RID = "ri.foundry.main.dataset.3c2b1a00-0000-4000-8000-000000000003"
FILE_IMPORT_RID = "ri.magritte..sync.0f0e0d0c-0000-4000-8000-000000000004"
TABLE_IMPORT_RID = "ri.magritte..sync.0a0b0c0d-0000-4000-8000-000000000005"
EGRESS_POLICY_RID = (
    "ri.resource-policy-manager.global.network-egress-policy."
    "1b2c3d4e-0000-4000-8000-000000000006"
)
BUILD_RID = "ri.foundry.main.build.7d6c5b4a-0000-4000-8000-000000000007"


def rest_configuration(host: str = "api.example.com") -> Dict[str, Any]:
    """A ``RestConnectionConfiguration``."""
    return {
        "type": "rest",
        "domains": [{"host": host, "port": 443, "scheme": "HTTPS"}],
    }


def jdbc_configuration(drivers: Iterable[str] = ()) -> Dict[str, Any]:
    """A ``JdbcConnectionConfiguration``."""
    return {
        "type": "jdbc",
        "url": "jdbc:postgresql://db.example.com:5432/orders",
        "driverClass": "org.postgresql.Driver",
        "uploadedJdbcDrivers": list(drivers),
        "jdbcProperties": {"ssl": "true"},
    }


def foundry_worker() -> Dict[str, Any]:
    """A ``FoundryWorker``."""
    return {"type": "foundryWorker", "networkEgressPolicyRids": [EGRESS_POLICY_RID]}


def connection(
    rid: str = CONNECTION_RID, name: str = "Orders API", **overrides: Any
) -> Dict[str, Any]:
    """A ``Connection``."""
    body: Dict[str, Any] = {
        "rid": rid,
        "parentFolderRid": FOLDER_RID,
        "displayName": name,
        "exportSettings": {
            "exportsEnabled": False,
            "exportEnabledWithoutMarkingsValidation": False,
        },
        "worker": foundry_worker(),
        "configuration": rest_configuration(),
    }
    body.update(overrides)
    return body


def file_import(
    rid: str = FILE_IMPORT_RID, name: str = "Daily drop", **overrides: Any
) -> Dict[str, Any]:
    """A ``FileImport``."""
    body: Dict[str, Any] = {
        "rid": rid,
        "connectionRid": CONNECTION_RID,
        "datasetRid": DATASET_RID,
        "branchName": "master",
        "displayName": name,
        "fileImportFilters": [{"type": "pathMatchesFilter", "regex": ".*\\.csv"}],
        "importMode": "APPEND",
        "subfolder": "exports/daily",
    }
    body.update(overrides)
    return body


def table_import(
    rid: str = TABLE_IMPORT_RID, name: str = "Orders", **overrides: Any
) -> Dict[str, Any]:
    """A ``TableImport``."""
    body: Dict[str, Any] = {
        "rid": rid,
        "connectionRid": CONNECTION_RID,
        "datasetRid": DATASET_RID,
        "branchName": "master",
        "displayName": name,
        "importMode": "SNAPSHOT",
        "allowSchemaChanges": False,
        "config": {"type": "jdbcImportConfig", "query": "SELECT * FROM orders"},
    }
    body.update(overrides)
    return body


def page(*items: Dict[str, Any], token: str = "") -> Dict[str, Any]:
    """A list response (``ListFileImportsResponse``, ``ListTableImportsResponse``)."""
    body: Dict[str, Any] = {"data": list(items)}
    if token:
        body["nextPageToken"] = token
    return body
