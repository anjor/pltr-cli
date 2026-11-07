"""pltr's command contract: output, errors, confirmation and command metadata.

Every curated command and every generated ``pltr api`` command uses this
package and nothing else to talk to the user. Import from here only::

    from pltr.contract import (
        pltr_command, emit, Columns, collect_pages,
        ProfileOption, FormatOption, OutputOption, YesOption,
        confirm_destructive, info, success, warn, spinner,
    )

The rules (stdout is data only; JSON is the SDK's own serialization; errors
are structured with documented exit codes; destructive commands confirm
unless ``--yes``; nothing prompts when stdin is not a terminal) and how to
convert a command are in ``docs/development/command-contract.md``.
"""

from .command import (
    BETA_LABEL,
    CommandEntry,
    CommandMeta,
    PltrRootGroup,
    beta_help,
    get_command_meta,
    iter_commands,
    pltr_command,
)
from .errors import (
    Aborted,
    ConfirmationRequired,
    ErrorInfo,
    ExitCode,
    PltrError,
    classify_error,
    fail,
    render_error,
)
from .options import (
    AllPagesOption,
    ConfirmAliasOption,
    ForceAliasOption,
    FormatOption,
    MaxPagesOption,
    OutputOption,
    PageSizeOption,
    PageTokenOption,
    PreviewNoopOption,
    ProfileOption,
    YesOption,
    click_format_option,
    click_output_option,
    click_page_options,
    click_profile_option,
    click_yes_option,
    confirm_destructive,
    format_option,
    load_json_input,
    output_option,
    profile_option,
    stdin_is_interactive,
)
from .output import (
    ColumnError,
    Columns,
    check_binary_output,
    column_value,
    emit,
    emit_bytes,
    format_cell,
    table_rows,
    write_bytes_atomically,
)
from .resources import (
    PATH_HELP,
    ResourceRef,
    resource_argument,
    resource_option,
)
from .runtime import (
    FORMAT_ENVVAR,
    FORMATS,
    capture_warnings,
    info,
    is_json,
    output_format,
    spinner,
    success,
    warn,
)
from .serialize import Page, collect_pages, to_document, to_jsonable

__all__ = [
    # commands and metadata
    "pltr_command",
    "CommandMeta",
    "CommandEntry",
    "get_command_meta",
    "iter_commands",
    "beta_help",
    "BETA_LABEL",
    "PltrRootGroup",
    # options
    "ProfileOption",
    "FormatOption",
    "OutputOption",
    "YesOption",
    "ConfirmAliasOption",
    "ForceAliasOption",
    "PreviewNoopOption",
    "PageSizeOption",
    "PageTokenOption",
    "MaxPagesOption",
    "AllPagesOption",
    "profile_option",
    "format_option",
    "output_option",
    "click_profile_option",
    "click_format_option",
    "click_output_option",
    "click_yes_option",
    "click_page_options",
    "confirm_destructive",
    "stdin_is_interactive",
    "load_json_input",
    # output
    "emit",
    "emit_bytes",
    "check_binary_output",
    "write_bytes_atomically",
    "Columns",
    "ColumnError",
    "column_value",
    "format_cell",
    "table_rows",
    "Page",
    "collect_pages",
    "to_jsonable",
    "to_document",
    "FORMATS",
    "FORMAT_ENVVAR",
    # Compass paths in resource parameters (#193)
    "ResourceRef",
    "resource_argument",
    "resource_option",
    "PATH_HELP",
    # stderr
    "info",
    "success",
    "warn",
    "spinner",
    "capture_warnings",
    "is_json",
    "output_format",
    # errors
    "ExitCode",
    "PltrError",
    "ConfirmationRequired",
    "Aborted",
    "ErrorInfo",
    "classify_error",
    "render_error",
    "fail",
]
