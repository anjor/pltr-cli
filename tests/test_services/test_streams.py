"""Tests for StreamsService against a real FoundryClient (only HTTP is faked).

Dataset.create, Dataset.Stream.create and Dataset.Stream.reset are beta: their
requests must carry preview=true. Stream.get, publish_record and
publish_records are GA: passing preview= would make the SDK emit a
UserWarning, which the module-level filter turns into a failure.
"""

import json

import pydantic
import pytest
from foundry_sdk.v2.streams.errors import StreamNotFound
from foundry_sdk.v2.streams.models import Dataset, Stream

from pltr.services.streams import StreamsService
from tests import foundry_json_streams as st

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

STREAMS = f"/api/v2/streams/datasets/{st.DATASET_RID}/streams"
HIGH_SCALE = f"/api/v2/highScale/streams/datasets/{st.DATASET_RID}/streams"


def test_create_dataset_is_beta_and_sends_the_schema(stub_foundry_http):
    stub_foundry_http.respond(json=st.dataset())

    dataset = StreamsService().create_dataset(
        name="sensor-data",
        parent_folder_rid=st.FOLDER_RID,
        schema=st.SCHEMA,
        branch_name="develop",
        compressed=True,
        partitions_count=5,
        stream_type="HIGH_THROUGHPUT",
    )

    assert isinstance(dataset, Dataset)
    assert (dataset.rid, dataset.parent_folder_rid) == (st.DATASET_RID, st.FOLDER_RID)
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        "/api/v2/streams/datasets/create",
    )
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "name": "sensor-data",
        "parentFolderRid": st.FOLDER_RID,
        "schema": st.SCHEMA,
        "branchName": "develop",
        "partitionsCount": 5,
        "streamType": "HIGH_THROUGHPUT",
        "compressed": True,
    }


def test_create_dataset_leaves_out_unset_settings(stub_foundry_http):
    stub_foundry_http.respond(json=st.dataset())

    StreamsService().create_dataset(
        name="sensor-data", parent_folder_rid=st.FOLDER_RID, schema=st.SCHEMA
    )

    assert json.loads(stub_foundry_http.requests[0].content) == {
        "name": "sensor-data",
        "parentFolderRid": st.FOLDER_RID,
        "schema": st.SCHEMA,
    }


def test_create_dataset_rejects_a_schema_without_fields(stub_foundry_http):
    """The format the old help documented never matched the SDK's StreamSchema."""
    with pytest.raises(pydantic.ValidationError):
        StreamsService().create_dataset(
            name="x",
            parent_folder_rid=st.FOLDER_RID,
            schema={"fieldSchemaList": [{"name": "value", "type": "STRING"}]},
        )
    assert stub_foundry_http.requests == []


def test_create_stream_is_beta(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream("feature"))

    stream = StreamsService().create_stream(
        st.DATASET_RID, branch_name="feature", schema=st.SCHEMA, partitions_count=3
    )

    assert isinstance(stream, Stream)
    assert stream.branch_name == "feature"
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", STREAMS)
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "branchName": "feature",
        "schema": st.SCHEMA,
        "partitionsCount": 3,
    }


def test_get_stream_is_ga(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream())

    stream = StreamsService().get_stream(st.DATASET_RID, "master")

    assert (stream.view_rid, stream.partitions_count) == (st.VIEW_RID, 1)
    assert [field.name for field in stream.schema_.fields] == ["id", "value"]
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", f"{STREAMS}/master")
    assert dict(request.url.params) == {}


def test_get_stream_not_found(stub_foundry_http):
    stub_foundry_http.respond(404, json=st.stream_not_found("nope"))

    with pytest.raises(StreamNotFound) as caught:
        StreamsService().get_stream(st.DATASET_RID, "nope")

    assert caught.value.parameters["streamBranchName"] == "nope"


def test_publish_record_is_ga(stub_foundry_http):
    stub_foundry_http.respond(204)

    result = StreamsService().publish_record(
        st.DATASET_RID, "master", {"id": 1, "value": "a"}, view_rid=st.VIEW_RID
    )

    assert result is None
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{HIGH_SCALE}/master/publishRecord",
    )
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {
        "record": {"id": 1, "value": "a"},
        "viewRid": st.VIEW_RID,
    }


def test_publish_records_is_ga(stub_foundry_http):
    stub_foundry_http.respond(204)

    StreamsService().publish_records(st.DATASET_RID, "master", [{"id": 1}, {"id": 2}])

    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"{HIGH_SCALE}/master/publishRecords",
    )
    assert dict(request.url.params) == {}
    assert json.loads(request.content) == {"records": [{"id": 1}, {"id": 2}]}


def test_reset_stream_is_beta_and_keeps_unset_settings(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream())

    stream = StreamsService().reset_stream(st.DATASET_RID, "master")

    assert stream.view_rid == st.VIEW_RID
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{STREAMS}/master/reset")
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {}


def test_reset_stream_with_new_settings(stub_foundry_http):
    stub_foundry_http.respond(json=st.stream(partitionsCount=4))

    StreamsService().reset_stream(
        st.DATASET_RID,
        "master",
        schema=st.SCHEMA,
        compressed=False,
        partitions_count=4,
        stream_type="LOW_LATENCY",
    )

    assert json.loads(stub_foundry_http.requests[0].content) == {
        "schema": st.SCHEMA,
        "partitionsCount": 4,
        "streamType": "LOW_LATENCY",
        "compressed": False,
    }
