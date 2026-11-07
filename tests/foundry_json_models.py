"""Realistic Foundry models API JSON bodies for stub_foundry_http tests.

Bodies use the API's field names and value formats (times are ISO-8601), so
the SDK decodes them into real ``Model`` and ``ModelVersion`` models.
"""

from typing import Any, Dict

from tests.foundry_json_orchestration import sdk_json

__all__ = ["model", "model_version", "sdk_json"]

MODEL_RID = "ri.models.main.model.3c4d5e6f-1111-4000-8000-000000000001"
VERSION_RID = "ri.models.main.model-version.3c4d5e6f-2222-4000-8000-000000000001"
VERSION_RID_2 = "ri.models.main.model-version.3c4d5e6f-2222-4000-8000-000000000002"
FOLDER_RID = "ri.compass.main.folder.3c4d5e6f-3333-4000-8000-000000000001"
REPOSITORY_RID = "ri.stemma.main.repository.3c4d5e6f-4444-4000-8000-000000000001"
EXPERIMENT_RID = "ri.models.main.experiment.3c4d5e6f-5555-4000-8000-000000000001"


def model(rid: str = MODEL_RID) -> Dict:
    """A ``Model`` (the API returns only its RID)."""
    return {"rid": rid}


def model_version(rid: str = VERSION_RID, **overrides: Any) -> Dict:
    """A ``ModelVersion`` with a tabular input and a parameter output."""
    body = {
        "rid": rid,
        "modelApi": {
            "inputs": [
                {
                    "type": "tabular",
                    "name": "transactions",
                    "columns": [
                        {"name": "amount", "dataType": {"type": "double"}},
                        {"name": "merchant", "dataType": {"type": "string"}},
                    ],
                    "format": "PANDAS",
                }
            ],
            "outputs": [
                {"type": "parameter", "name": "score", "dataType": {"type": "double"}}
            ],
        },
        "condaRequirements": ["scikit-learn=1.3.0", "pandas=2.1.0"],
        "backingRepositories": [REPOSITORY_RID],
        "createdTime": "2024-01-05T00:00:00Z",
        "source": {
            "type": "codeRepository",
            "repositoryRid": REPOSITORY_RID,
            "branch": "master",
        },
        "linkedExperiment": EXPERIMENT_RID,
    }
    body.update(overrides)
    return body
