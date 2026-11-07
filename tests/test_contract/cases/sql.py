"""Contract-test cases for src/pltr/commands/sql.py (see __init__.py)."""

from tests import foundry_json_sql as sj

# execute polls getStatus while the query runs, then fetches the results.
_EXECUTE = [{"json": sj.running()}, {"json": sj.succeeded()}, sj.results()]

SUCCESS = {
    "sql execute": _EXECUTE,
    "sql submit": [{"json": sj.running()}],
    "sql status": [{"json": sj.running()}],
    "sql results": [sj.results()],
    "sql cancel": [{"status_code": 204}, {"json": sj.canceled()}],
    "sql wait": [{"json": sj.succeeded()}, sj.results()],
}

SUCCESS_EXEMPT = {
    "sql export": (
        "writes the rows to OUTPUT_FILE (like --output), so stdout stays empty by "
        "design; tests/test_commands/test_sql.py covers the success path"
    ),
}
