"""Contract-test cases for src/pltr/commands/dataset.py (see __init__.py)."""

import json

from tests import foundry_json_dataset as dj
from tests.test_contract.cases import CONTRACT_RID

SUCCESS = {
    "dataset get": [{"json": dj.dataset(CONTRACT_RID)}],
    "dataset create": [{"json": dj.dataset()}],
    "dataset preview": [
        {"content": dj.arrow_stream({"id": [1, 2], "region": ["EMEA", "APAC"]})}
    ],
    "dataset schema get": [{"json": dj.schema_response()}],
    "dataset schema set": [{"json": dj.schema_response()}],
    # labeled direct-HTTP: schema inference, then foundry-metadata
    "dataset schema apply": [
        {"json": dj.inference_response()},
        {"json": dj.metadata_response()},
    ],
    "dataset branches list": [{"json": dj.page([dj.branch()], "next")}],
    # reads the parent branch (master), then creates the branch at its transaction
    "dataset branches create": [
        {"json": dj.branch()},
        {"json": dj.branch("contract-test")},
    ],
    "dataset branches get": [{"json": dj.branch()}],
    "dataset branches delete": [{"status_code": 204}],
    "dataset branches transactions": [{"json": dj.page([dj.transaction()])}],
    "dataset files list": [{"json": dj.page([dj.file()])}],
    "dataset files upload": [{"json": dj.file("contract-file_path.json")}],
    # file metadata, then the streamed content
    "dataset files get": [{"json": dj.file()}, {"content": b"id,region\n1,EMEA\n"}],
    "dataset files delete": [{"status_code": 204}],
    "dataset files info": [{"json": dj.file()}],
    "dataset transactions start": [{"json": dj.transaction()}],
    "dataset transactions commit": [
        {"json": dj.transaction(status="COMMITTED", closed_time=dj.CLOSED_TIME)}
    ],
    "dataset transactions abort": [
        {"json": dj.transaction(status="ABORTED", closed_time=dj.CLOSED_TIME)}
    ],
    "dataset transactions status": [{"json": dj.transaction()}],
    "dataset transactions list": [{"json": dj.page([dj.transaction()])}],
    "dataset transactions build": [{"json": dj.BUILD_RID}],
    "dataset views create": [{"json": dj.view()}],
    "dataset views get": [{"json": dj.view()}],
    "dataset views add-datasets": [{"json": dj.view()}],
    "dataset views remove-datasets": [{"json": dj.view()}],
    "dataset views replace-datasets": [{"json": dj.view()}],
    "dataset views add-primary-key": [
        {
            "json": dj.view(
                primary_key={"columns": ["id"], "resolution": {"type": "unique"}}
            )
        }
    ],
    "dataset schedules list": [{"json": dj.page([dj.SCHEDULE_RID])}],
    "dataset jobs list": [{"json": dj.page([dj.job()])}],
}

ARGS = {
    # needs exactly one schema source
    "dataset schema set": [
        CONTRACT_RID,
        "--json",
        json.dumps({"fieldSchemaList": [dj.field("id", "LONG", nullable=False)]}),
    ],
}
