"""Contract-test cases for src/pltr/commands/audit.py (see __init__.py)."""

from tests import foundry_json_audit as aj

SUCCESS = {
    "audit list": [{"json": aj.log_files("2024-01-01-0001.json.gz", token="next")}],
}

SUCCESS_EXEMPT = {
    # The error checks still run; tests/test_commands/test_audit.py covers success.
    "audit get": (
        "streams the log file's raw bytes to stdout or --output (emit_bytes), "
        "not a JSON document"
    ),
}
