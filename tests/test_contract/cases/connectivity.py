"""Contract-test cases for src/pltr/commands/connectivity.py (see __init__.py)."""

import json
from pathlib import Path

from tests import foundry_json_connectivity as cj
from tests.test_contract.cases import CONTRACT_RID, resource_rid

_DATA = Path(__file__).parent / "data"
#: update-secrets refuses an empty secrets file; upload-jdbc-drivers takes .jar files.
SECRETS_FILE = str(_DATA / "connectivity-secrets.json")
DRIVER_JAR = str(_DATA / "connectivity-driver.jar")

SUCCESS = {
    "connectivity connection get": [{"json": cj.connection(CONTRACT_RID)}],
    "connectivity connection create": [{"json": cj.connection()}],
    "connectivity connection get-config": [{"json": cj.rest_configuration()}],
    "connectivity connection update-secrets": [{"status_code": 204}],
    "connectivity connection update-export-settings": [{"status_code": 204}],
    "connectivity connection upload-jdbc-drivers": [
        {
            "json": cj.connection(
                configuration=cj.jdbc_configuration(["connectivity-driver.jar"])
            )
        }
    ],
    "connectivity import file": [{"json": cj.file_import()}],
    "connectivity import get-file": [{"json": cj.file_import()}],
    "connectivity import list-file": [
        {"json": cj.page(cj.file_import(), token="next")}
    ],
    "connectivity import execute-file": [{"json": cj.BUILD_RID}],
    "connectivity import table": [{"json": cj.table_import()}],
    "connectivity import get-table": [{"json": cj.table_import()}],
    "connectivity import list-table": [{"json": cj.page(cj.table_import())}],
    "connectivity import execute-table": [{"json": cj.BUILD_RID}],
}

ARGS = {
    # CONFIGURATION and WORKER are optional arguments (they can come from files)
    "connectivity connection create": [
        "Contract API",
        CONTRACT_RID,
        json.dumps(cj.rest_configuration()),
        json.dumps(cj.foundry_worker()),
    ],
    "connectivity connection update-secrets": [
        resource_rid("connection"),
        "--secrets-file",
        SECRETS_FILE,
    ],
    # SETTINGS is an optional argument (it can come from --settings-file)
    "connectivity connection update-export-settings": [
        resource_rid("connection"),
        '{"exportsEnabled": true, "exportEnabledWithoutMarkingsValidation": false}',
    ],
    "connectivity connection upload-jdbc-drivers": [
        resource_rid("connection"),
        DRIVER_JAR,
    ],
    # --config must be a table import config object
    "connectivity import table": [
        resource_rid("connection"),
        resource_rid("dataset"),
        "--name",
        "Contract import",
        "--mode",
        "SNAPSHOT",
        "--config",
        '{"type": "jdbcImportConfig", "query": "SELECT 1"}',
    ],
}
