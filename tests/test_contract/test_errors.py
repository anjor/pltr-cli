"""Tests for error classification, rendering and exit codes."""

import json
from typing import Any

import click
import foundry_sdk
import httpx
import pydantic
import pytest
import requests
from foundry_sdk import (
    ApiNotFoundError,
    BadRequestError,
    ConfidentialClientAuth,
    ConflictError,
    ConnectionError,
    ConnectTimeout,
    FoundryClient,
    InternalServerError,
    NotAuthenticated,
    NotFoundError,
    PermissionDeniedError,
    ProxyError,
    RateLimitError,
    ReadTimeout,
    RequestEntityTooLargeError,
    SDKInternalError,
    ServiceUnavailable,
    UnauthorizedError,
    UnprocessableEntityError,
)

from pltr.auth.base import (
    AuthError,
    InvalidCredentialsError,
    MissingCredentialsError,
    ProfileNotFoundError,
)
from pltr.contract import (
    Aborted,
    ConfirmationRequired,
    ErrorInfo,
    ExitCode,
    PltrError,
    classify_error,
    fail,
    render_error,
)
from tests import foundry_json as fj

GENERIC_BODY = {
    "errorCode": "NOT_FOUND",
    "errorName": "Thing:NotFound",
    "errorInstanceId": "i-1",
    "parameters": {"thingRid": "ri.a.b.c.d"},
}


def raised(exc: BaseException) -> BaseException:
    """`exc` as it looks after being raised (traceback, context set)."""
    try:
        raise exc
    except BaseException as caught:
        return caught


# -------------------------------------------------- typed errors via the SDK


def test_typed_not_found_error_from_a_real_endpoint(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("FolderNotFound", parameters={"folderRid": fj.FOLDER_RID})
    )
    with pytest.raises(NotFoundError) as excinfo:
        stub_foundry_http.client.filesystem.Folder.get(fj.FOLDER_RID)
    error = excinfo.value
    assert type(error).__name__ == "FolderNotFound"  # the typed subclass
    assert str(error) == "" and not hasattr(error, "error_code")

    info = classify_error(error)

    assert info.to_json() == {
        "type": "not_found",
        "message": "FolderNotFound: The given Folder could not be found. "
        f"(folderRid={fj.FOLDER_RID})",
        "exitCode": 5,
        "statusCode": 404,
        "errorCode": "NOT_FOUND",  # derived: typed errors drop it
        "errorName": "FolderNotFound",
        "errorInstanceId": fj.ERROR_INSTANCE_ID,
        "parameters": {"folderRid": fj.FOLDER_RID},
    }


def test_typed_permission_denied_error_from_a_real_endpoint(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("GetCurrentUserPermissionDenied", "PERMISSION_DENIED")
    )
    with pytest.raises(PermissionDeniedError) as excinfo:
        stub_foundry_http.client.admin.User.get_current()

    info = classify_error(excinfo.value)

    assert type(excinfo.value).__name__ == "GetCurrentUserPermissionDenied"
    assert (info.type, info.exit_code, info.status_code) == (
        "permission_denied",
        4,
        403,
    )
    assert info.error_code == "PERMISSION_DENIED"
    assert info.message.startswith("GetCurrentUserPermissionDenied")


def test_generic_rpc_error_keeps_the_body_error_code():
    info = classify_error(raised(NotFoundError(GENERIC_BODY)))
    assert info.to_json() == {
        "type": "not_found",
        "message": "Thing:NotFound (thingRid=ri.a.b.c.d)",
        "exitCode": 5,
        "statusCode": 404,
        "errorCode": "NOT_FOUND",
        "errorName": "Thing:NotFound",
        "errorInstanceId": "i-1",
        "parameters": {"thingRid": "ri.a.b.c.d"},
    }


# --------------------------------------------------------- exit-code mapping


def body(code: str = "X") -> dict:
    return {
        "errorCode": code,
        "errorName": "E",
        "errorInstanceId": "i",
        "parameters": {},
    }


@pytest.mark.parametrize(
    "exc, error_type, exit_code, status",
    [
        (BadRequestError(body()), "validation_error", 6, 400),
        (UnprocessableEntityError(body()), "validation_error", 6, 422),
        (UnauthorizedError(body()), "auth_error", 3, 401),
        (PermissionDeniedError(body()), "permission_denied", 4, 403),
        (NotFoundError(body()), "not_found", 5, 404),
        (ConflictError(body()), "conflict", 7, 409),
        (RequestEntityTooLargeError(body()), "request_too_large", 7, 413),
        (InternalServerError(body()), "server_error", 7, None),
        (RateLimitError("slow down", reason="r"), "rate_limited", 7, 429),
        (ServiceUnavailable("down", reason="r"), "server_error", 7, 503),
        (ApiNotFoundError("no such API"), "api_not_found", 5, 404),
        (ConnectionError("refused"), "network_error", 7, None),
        (ProxyError("proxy"), "network_error", 7, None),
        (ConnectTimeout("connect"), "timeout", 7, None),
        (ReadTimeout("read"), "timeout", 7, None),
        (NotAuthenticated("not signed in"), "auth_error", 3, None),
        (SDKInternalError("boom"), "unexpected_error", 1, None),
        (
            SDKInternalError("Unexpected error response with status code 502: <html>"),
            "server_error",
            7,
            502,
        ),
        (ProfileNotFoundError("no profile"), "auth_error", 3, None),
        (MissingCredentialsError("no token"), "auth_error", 3, None),
        (InvalidCredentialsError("bad"), "auth_error", 3, None),
        (AuthError("auth"), "auth_error", 3, None),
        (click.UsageError("bad usage"), "usage_error", 2, None),
        (click.BadParameter("bad value"), "usage_error", 2, None),
        (json.JSONDecodeError("Expecting value", "x", 0), "usage_error", 2, None),
        (
            requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0),
            "invalid_response",
            7,
            None,
        ),
        (ConfirmationRequired("pass --yes"), "confirmation_required", 2, None),
        (Aborted("no"), "aborted", 1, None),
        (KeyError("x"), "unexpected_error", 1, None),
    ],
)
def test_exit_codes(exc, error_type, exit_code, status):
    info = classify_error(raised(exc))
    assert (info.type, info.exit_code, info.status_code) == (
        error_type,
        exit_code,
        status,
    )


def test_any_auth_error_subclass_is_exit_3():
    class KeyringUnavailableError(MissingCredentialsError):
        pass

    assert classify_error(raised(KeyringUnavailableError("no keyring"))).exit_code == 3


def test_oauth_token_failure_is_an_auth_error(stub_foundry_http):
    """The SDK wraps a failed token request in SDKInternalError."""
    client = FoundryClient(
        auth=ConfidentialClientAuth(
            client_id="id", client_secret="s", scopes=["api:read-data"]
        ),
        hostname="test.palantirfoundry.com",
    )
    stub_foundry_http.respond_always(401, json={"error": "invalid_client"})
    with pytest.raises(SDKInternalError) as excinfo:
        client.filesystem.Folder.get(fj.FOLDER_RID)

    info = classify_error(excinfo.value)

    assert (info.type, info.exit_code, info.status_code) == ("auth_error", 3, 401)
    assert "OAuth2 token request failed" in info.message
    assert stub_foundry_http.requests[0].url.path.endswith("/oauth2/token")


@pytest.mark.parametrize(
    "status, error_type, exit_code, says",
    [
        (400, "auth_error", 3, "client secret and scopes"),
        (403, "auth_error", 3, "client secret and scopes"),
        # Not about the credentials: agents must not be told to fix them.
        (429, "rate_limited", 7, "retry after a short wait"),
        (500, "server_error", 7, "retry later"),
        (503, "server_error", 7, "retry later"),
        (404, "not_found", 5, "check the profile's host"),
    ],
)
def test_oauth_token_failure_by_status(
    stub_foundry_http, status, error_type, exit_code, says
):
    client = FoundryClient(
        auth=ConfidentialClientAuth(
            client_id="id", client_secret="s", scopes=["api:read-data"]
        ),
        hostname="test.palantirfoundry.com",
    )
    stub_foundry_http.respond_always(status, json={"error": "nope"})
    with pytest.raises(Exception) as excinfo:
        client.filesystem.Folder.get(fj.FOLDER_RID)

    info = classify_error(excinfo.value)

    assert (info.type, info.exit_code, info.status_code) == (
        error_type,
        exit_code,
        status,
    )
    assert info.message.startswith(f"OAuth2 token request failed (HTTP {status})")
    assert says in info.message
    if error_type != "auth_error":
        assert "client secret" not in info.message
        assert "pltr configure" not in (info.hint or "")


def test_bare_http_status_errors():
    request = httpx.Request("GET", "https://host/api/v2/thing")
    response = httpx.Response(404, request=request)
    info = classify_error(
        raised(httpx.HTTPStatusError("nope", request=request, response=response))
    )
    assert (info.type, info.exit_code, info.status_code) == ("not_found", 5, 404)


# -------------------------------------------------------- requests errors


def http_error(status: int, payload: Any = None, text: str = "") -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    response.reason = "Reason"
    response._content = (
        json.dumps(payload).encode() if payload is not None else text.encode()
    )
    return requests.HTTPError(f"{status} error", response=response)


def test_requests_http_error_with_foundry_body():
    info = classify_error(raised(http_error(404, GENERIC_BODY)))
    assert info.to_json() == {
        "type": "not_found",
        "message": "Thing:NotFound (thingRid=ri.a.b.c.d)",
        "exitCode": 5,
        "statusCode": 404,
        "errorCode": "NOT_FOUND",
        "errorName": "Thing:NotFound",
        "errorInstanceId": "i-1",
        "parameters": {"thingRid": "ri.a.b.c.d"},
    }


@pytest.mark.parametrize(
    "status, error_type, exit_code",
    [
        (400, "validation_error", 6),
        (401, "auth_error", 3),
        (403, "permission_denied", 4),
        (429, "rate_limited", 7),
        (500, "server_error", 7),
        (418, "api_error", 7),
    ],
)
def test_requests_http_error_without_body(status, error_type, exit_code):
    info = classify_error(raised(http_error(status, text="<html>")))
    assert (info.type, info.exit_code, info.status_code) == (
        error_type,
        exit_code,
        status,
    )
    assert info.message == f"HTTP {status} Reason"


def test_requests_network_errors():
    assert classify_error(raised(requests.ConnectionError("x"))).type == "network_error"
    assert classify_error(raised(requests.Timeout("x"))).type == "timeout"


# ------------------------------------------------------- pydantic validation


def test_invalid_rid_argument_is_a_usage_error(stub_foundry_http):
    with pytest.raises(pydantic.ValidationError) as excinfo:
        stub_foundry_http.client.filesystem.Folder.get("not-a-rid")
    info = classify_error(excinfo.value)
    assert (info.type, info.exit_code) == ("usage_error", 2)
    assert "'not-a-rid' is not a valid RID" in info.message
    assert stub_foundry_http.requests == []


def test_wrong_sdk_signature_is_a_pltr_bug(stub_foundry_http):
    with pytest.raises(pydantic.ValidationError) as excinfo:
        stub_foundry_http.client.filesystem.Space.list(organization_rid="ri.a.b.c.d")
    info = classify_error(excinfo.value)
    assert (info.type, info.exit_code) == ("unexpected_error", 1)
    assert "pltr bug" in info.message


def test_response_that_does_not_fit_the_model_is_an_invalid_response(
    stub_foundry_http,
):
    """Not a usage error: the user's input was fine, the response wasn't."""
    stub_foundry_http.respond(json={"rid": fj.FOLDER_RID})  # most fields missing
    with pytest.raises(pydantic.ValidationError) as excinfo:
        stub_foundry_http.client.filesystem.Folder.get(fj.FOLDER_RID)
    assert excinfo.value.title == "Folder"

    info = classify_error(excinfo.value)

    assert (info.type, info.exit_code, info.status_code) == (
        "invalid_response",
        7,
        None,
    )
    assert info.message.startswith(
        "The API response doesn't match the SDK's Folder model (displayName: Field "
        "required; path: Field required; type: Field required; and "
    )
    assert f"foundry-platform-sdk {foundry_sdk.__version__}" in info.message
    assert "upgrading pltr" in info.message
    assert "uv tool upgrade pltr-cli" in info.hint


def test_response_of_a_non_model_type_that_does_not_fit(stub_foundry_http):
    """Responses that aren't models are decoded with a TypeAdapter."""
    stub_foundry_http.respond(json=12)  # Transaction.build returns a build RID
    with pytest.raises(pydantic.ValidationError) as excinfo:
        stub_foundry_http.client.datasets.Dataset.Transaction.build(
            "ri.foundry.main.dataset.d", "ri.foundry.main.transaction.t", preview=True
        )

    info = classify_error(excinfo.value)

    assert (info.type, info.exit_code) == ("invalid_response", 7)
    assert info.message.startswith("The API response doesn't match the SDK's str")


def test_next_page_that_does_not_fit_the_model(stub_foundry_http):
    """Later pages are fetched without validate_call (iterating the iterator)."""
    stub_foundry_http.respond(json={"data": [fj.folder()], "nextPageToken": "p2"})
    stub_foundry_http.respond(json={"data": [{"rid": 1}]})
    iterator = stub_foundry_http.client.filesystem.Folder.children(fj.FOLDER_RID)
    with pytest.raises(pydantic.ValidationError) as excinfo:
        list(iterator)

    info = classify_error(excinfo.value)

    assert (info.type, info.exit_code) == ("invalid_response", 7)
    assert "ListChildrenOfFolderResponse" in info.message


def test_wrapped_response_decode_error_keeps_the_context(stub_foundry_http):
    stub_foundry_http.respond(json={"rid": fj.FOLDER_RID})
    try:
        try:
            stub_foundry_http.client.filesystem.Folder.get(fj.FOLDER_RID)
        except pydantic.ValidationError as decode_error:
            raise RuntimeError("Failed to get the folder") from decode_error
    except RuntimeError as wrapper:
        info = classify_error(wrapper)

    assert (info.type, info.exit_code) == ("invalid_response", 7)
    assert info.message.startswith("Failed to get the folder: The API response")


def test_pltr_validating_user_input_into_a_model_is_still_a_usage_error():
    """No SDK frames: pltr validated something itself (e.g. JSON input)."""
    from foundry_sdk.v2.core.models import DatasetSchema

    with pytest.raises(pydantic.ValidationError) as excinfo:
        DatasetSchema.model_validate({"fieldSchemaList": [{"name": "x"}]})

    info = classify_error(excinfo.value)

    assert (info.type, info.exit_code) == ("usage_error", 2)


# --------------------------------------------- responses that aren't JSON


def test_sdk_success_body_that_is_not_json_is_an_invalid_response(
    stub_foundry_http,
):
    """The SDK wraps the JSONDecodeError in SDKInternalError."""
    stub_foundry_http.respond(
        content=b"<html>Sign in</html>", headers={"Content-Type": "application/json"}
    )
    with pytest.raises(SDKInternalError) as excinfo:
        stub_foundry_http.client.filesystem.Folder.get(fj.FOLDER_RID)

    info = classify_error(excinfo.value)

    assert (info.type, info.exit_code) == ("invalid_response", 7)
    assert info.message.startswith(
        "The API returned a response that isn't valid JSON (Expecting value at "
        "line 1, column 1)."
    )


def test_direct_http_success_body_that_is_not_json_is_an_invalid_response(
    stub_foundry_http,
):
    """requests' JSONDecodeError must not reach the json.JSONDecodeError
    in its context, which would make it a usage error (invalid JSON input)."""
    stub_foundry_http.respond(content=b"<html>Sign in</html>")
    response = requests.get("https://test.palantirfoundry.com/api/thing")
    with pytest.raises(requests.exceptions.JSONDecodeError) as excinfo:
        response.json()
    assert isinstance(excinfo.value.__context__, json.JSONDecodeError)

    info = classify_error(excinfo.value)

    assert (info.type, info.exit_code) == ("invalid_response", 7)
    assert "isn't valid JSON" in info.message


def test_unexpected_sdk_failure_is_reported_as_a_bug():
    info = classify_error(raised(SDKInternalError("'NoneType' object is not iterable")))

    assert (info.type, info.exit_code) == ("unexpected_error", 1)
    assert info.message == (
        "foundry-platform-sdk failed unexpectedly: 'NoneType' object is not iterable"
    )
    assert info.hint is not None and "bug in foundry-platform-sdk or pltr" in info.hint


def test_sdk_internal_error_is_never_a_usage_error():
    """Even when it wraps an exception that alone would be a usage error."""
    try:
        try:
            raise ValueError("bad value")
        except ValueError as inner:
            raise SDKInternalError(str(inner)) from inner
    except SDKInternalError as outer:
        info = classify_error(outer)

    assert (info.type, info.exit_code) == ("unexpected_error", 1)


# --------------------------------------------------------- exception chains


def test_wrapped_sdk_error_is_found_through_cause():
    try:
        try:
            raise NotFoundError(GENERIC_BODY)
        except NotFoundError as sdk_error:
            raise RuntimeError("Failed to get thing ri.a.b.c.d") from sdk_error
    except RuntimeError as wrapper:
        info = classify_error(wrapper)
    assert (info.type, info.exit_code, info.error_name) == (
        "not_found",
        5,
        "Thing:NotFound",
    )
    assert info.message == (
        "Failed to get thing ri.a.b.c.d: Thing:NotFound (thingRid=ri.a.b.c.d)"
    )


def test_wrapped_sdk_error_is_found_through_implicit_context():
    """Legacy services re-raise inside `except` without `from e`."""
    try:
        try:
            raise PermissionDeniedError(body())
        except PermissionDeniedError as sdk_error:
            raise RuntimeError(f"Failed to do it: {sdk_error}")  # noqa: B904
    except RuntimeError as wrapper:
        info = classify_error(wrapper)
    assert (info.type, info.exit_code) == ("permission_denied", 4)
    assert info.message.startswith("Failed to do it: E")
    assert "\n" not in info.message


def test_unknown_errors():
    assert classify_error(raised(RuntimeError("it broke"))).message == "it broke"
    assert classify_error(raised(KeyError("x"))).message == "KeyError: 'x'"
    assert classify_error(raised(RuntimeError())).message == "RuntimeError"


def test_pltr_error_with_custom_type_and_hint():
    info = classify_error(
        raised(
            PltrError("file missing", error_type="usage_error", exit_code=2, hint="h")
        )
    )
    assert (info.type, info.exit_code, info.hint) == ("usage_error", 2, "h")


# ---------------------------------------------------------------- rendering


def test_to_json_omits_missing_and_empty_keys():
    info = ErrorInfo("usage_error", "bad", ExitCode.USAGE, parameters={})
    assert info.to_json() == {"type": "usage_error", "message": "bad", "exitCode": 2}


def test_render_json_is_one_compact_line(capsys):
    render_error(classify_error(raised(NotFoundError(GENERIC_BODY))), as_json=True)
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and " " not in err.split('"message"')[0]
    assert json.loads(err)["errorName"] == "Thing:NotFound"


def test_render_text_includes_error_name_details_and_hint(capsys):
    render_error(classify_error(raised(NotFoundError(GENERIC_BODY))), as_json=False)
    err = capsys.readouterr().err
    assert err.splitlines()[0] == "Error: Thing:NotFound (thingRid=ri.a.b.c.d)"
    assert "status: 404" in err and "errorCode: NOT_FOUND" in err
    assert "errorInstanceId: i-1" in err
    assert err.splitlines()[-1].startswith("Hint: Check the RID")


def test_fail_exits_with_the_code(capsys):
    with pytest.raises(click.exceptions.Exit) as excinfo:
        fail(raised(NotFoundError(GENERIC_BODY)))
    assert excinfo.value.exit_code == 5
    assert "Thing:NotFound" in capsys.readouterr().err


def test_fail_reraises_with_pltr_debug(monkeypatch, capsys):
    monkeypatch.setenv("PLTR_DEBUG", "1")
    error = raised(NotFoundError(GENERIC_BODY))
    with pytest.raises(NotFoundError):
        fail(error)
    assert "Thing:NotFound" in capsys.readouterr().err
