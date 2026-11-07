"""
Media set commands (Foundry media sets API).

Media sets hold media items (images, documents, audio, video, ...). Both are
addressed by RID: media sets look like ``ri.mio.main.media-set.<uuid>`` and
media items like ``ri.mio.main.media-item.<uuid>``.
"""

import itertools
from pathlib import Path
from typing import Any, Optional

import click
import typer
from typing_extensions import Annotated

from ..contract import (
    Columns,
    ExitCode,
    FormatOption,
    OutputOption,
    PltrError,
    PreviewNoopOption,
    ProfileOption,
    YesOption,
    check_binary_output,
    confirm_destructive,
    emit,
    emit_bytes,
    info,
    pltr_command,
    spinner,
    success,
    warn,
)
from ..services.mediasets import MediaSetsService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()

#: Table/CSV columns for a ``MediaReference`` (``reference`` and ``upload-temp``).
REFERENCE_COLUMNS: Columns = {
    "MIME Type": "mime_type",
    "Media Set RID": "reference.media_set_view_item.media_set_rid",
    "Media Set View RID": "reference.media_set_view_item.media_set_view_rid",
    "Media Item RID": "reference.media_set_view_item.media_item_rid",
    "Token": "reference.media_set_view_item.token",
}


def _item_info_columns(media_item_rid: str) -> Columns:
    """Columns for a ``GetMediaItemInfoResponse``, which doesn't repeat the
    item RID: the RID shown is the one the user passed."""
    return {
        "Media Item RID": lambda _: media_item_rid,
        "Path": "path",
        "MIME Type": "mime_type",
        "Size (bytes)": "size_bytes_long",
        "Originally Uploaded MIME Type": "originally_uploaded_file_mime_type",
        "View RID": "view_rid",
        "Logical Timestamp": "logical_timestamp",
        "Created By": "attribution.creator_id",
        "Created": "attribution.creation_timestamp",
    }


MediaSetRid = Annotated[
    str,
    typer.Argument(
        help="Media set RID (ri.mio.main.media-set.<uuid>).",
        autocompletion=complete_rid,
        show_default=False,
    ),
]
MediaItemRid = Annotated[
    str,
    typer.Argument(
        help=(
            "Media item RID (ri.mio.main.media-item.<uuid>); find one with "
            "'pltr media-sets get-by-path'."
        ),
        autocompletion=complete_rid,
        show_default=False,
    ),
]
TransactionId = Annotated[
    str,
    typer.Argument(
        help="Transaction ID (a UUID, from 'pltr media-sets create').",
        show_default=False,
    ),
]
BranchOption = Annotated[
    Optional[str],
    typer.Option(
        "--branch",
        help="Media set branch (default: the default branch, usually master).",
        show_default=False,
    ),
]
OverwriteOption = Annotated[
    bool, typer.Option("--overwrite", help="Replace OUTPUT_PATH if it exists.")
]


def _output_path_argument(what: str) -> Any:
    return typer.Argument(
        help=f"File to save the {what} to, or - for stdout.",
        dir_okay=False,
        allow_dash=True,
        show_default=False,
    )


def _deprecated_commit_yes(
    ctx: click.Context, param: click.Parameter, value: bool
) -> bool:
    if value and not ctx.resilient_parsing:
        warn(
            "--yes has no effect on 'media-sets commit' (committing no longer asks "
            "for confirmation) and will be removed in a future release."
        )
    return value


#: Hidden, deprecated no-op: `commit` used to ask for confirmation.
CommitYesNoopOption = Annotated[
    bool,
    typer.Option(
        "--yes",
        "-y",
        hidden=True,
        help="Deprecated; has no effect.",
        callback=_deprecated_commit_yes,
    ),
]


# ------------------------------------------------------------ binary output


def _binary_output(path: Path, *, overwrite: bool) -> str:
    """Check OUTPUT_PATH before downloading; return it for ``emit_bytes``.

    ``-`` means stdout. An existing file is replaced only with ``--overwrite``
    (otherwise a usage error, before any API call), and missing parent
    directories are created.
    """
    output = str(path)
    check_binary_output(output)
    if output != "-":
        if path.exists() and not overwrite:
            raise typer.BadParameter(
                f"{path} already exists; pass --overwrite to replace it",
                param_hint="OUTPUT_PATH",
            )
        path.parent.mkdir(parents=True, exist_ok=True)
    return output


# ----------------------------------------------------------------- commands


@app.command("get")
@pltr_command(sdk="media_sets.MediaSet.info")
def get_media_item(
    media_set_rid: MediaSetRid,
    media_item_rid: MediaItemRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get a media item's metadata: path, MIME type, size and who uploaded it."""
    with spinner(f"Fetching media item {media_item_rid}..."):
        item = MediaSetsService(profile=profile).get_media_item_info(
            media_set_rid, media_item_rid
        )
    cache_rid(media_set_rid)
    cache_rid(media_item_rid)
    emit(
        item,
        format=format,
        output=output,
        columns=_item_info_columns(media_item_rid),
        title="Media Item",
    )


@app.command("get-by-path")
@pltr_command(sdk="media_sets.MediaSet.get_rid_by_path", beta=True)
def get_media_by_path(
    media_set_rid: MediaSetRid,
    media_item_path: Annotated[
        str,
        typer.Argument(
            help="Path of the media item within the media set.", show_default=False
        ),
    ],
    profile: ProfileOption = None,
    branch: BranchOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Look up the RID of the media item at a path in a media set."""
    with spinner(f"Looking up media item at path {media_item_path}..."):
        result = MediaSetsService(profile=profile).get_media_item_rid_by_path(
            media_set_rid, media_item_path, branch_name=branch
        )
    cache_rid(media_set_rid)
    if result.media_item_rid:
        cache_rid(result.media_item_rid)
    else:
        warn(f"No media item at path '{media_item_path}'.")
    emit(
        result,
        format=format,
        output=output,
        columns={"Path": lambda _: media_item_path, "Media Item RID": "media_item_rid"},
        title="Media Item",
    )


@app.command("create")
@pltr_command(sdk="media_sets.MediaSet.create", beta=True)
def create_transaction(
    media_set_rid: MediaSetRid,
    profile: ProfileOption = None,
    branch: BranchOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Open a transaction for uploading to a transactional media set.

    Prints the transaction ID (in JSON, as a JSON string). Upload with
    'pltr media-sets upload', then commit the transaction to make the items
    available, or abort it to delete them.
    """
    with spinner("Creating transaction..."):
        transaction_id = MediaSetsService(profile=profile).create_transaction(
            media_set_rid, branch_name=branch
        )
    cache_rid(media_set_rid)
    success(f"Created transaction {transaction_id} on media set {media_set_rid}")
    info(
        f"Upload with: pltr media-sets upload {media_set_rid} FILE PATH "
        f"{transaction_id}; then commit or abort the transaction."
    )
    emit(
        transaction_id,
        format=format,
        output=output,
        columns={"Transaction ID": lambda value: value},
        title="Transaction",
    )


@app.command("commit")
@pltr_command(sdk="media_sets.MediaSet.commit", beta=True)
def commit_transaction(
    media_set_rid: MediaSetRid,
    transaction_id: TransactionId,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    preview: PreviewNoopOption = False,
    yes: CommitYesNoopOption = False,
):
    """Commit a transaction: the items uploaded in it become available."""
    with spinner(f"Committing transaction {transaction_id}..."):
        MediaSetsService(profile=profile).commit_transaction(
            media_set_rid, transaction_id
        )
    success(f"Committed transaction {transaction_id}; its uploads are now available")
    emit(None, format=format)


@app.command("abort")
@pltr_command(sdk="media_sets.MediaSet.abort", beta=True, destructive=True)
def abort_transaction(
    media_set_rid: MediaSetRid,
    transaction_id: TransactionId,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    preview: PreviewNoopOption = False,
):
    """Abort a transaction, deleting the items uploaded in it."""
    confirm_destructive(
        f"Abort transaction {transaction_id} on media set {media_set_rid}? The "
        "items uploaded in it will be deleted.",
        yes=yes,
    )
    with spinner(f"Aborting transaction {transaction_id}..."):
        MediaSetsService(profile=profile).abort_transaction(
            media_set_rid, transaction_id
        )
    success(f"Aborted transaction {transaction_id}; its uploads were deleted")
    emit(None, format=format)


@app.command("upload")
@pltr_command(sdk="media_sets.MediaSet.upload", beta=True)
def upload_media(
    media_set_rid: MediaSetRid,
    file_path: Annotated[
        Path,
        typer.Argument(
            help="Local file to upload.",
            exists=True,
            dir_okay=False,
            readable=True,
            show_default=False,
        ),
    ],
    media_item_path: Annotated[
        str,
        typer.Argument(
            help="Path of the new item within the media set, e.g. images/photo.jpg.",
            show_default=False,
        ),
    ],
    transaction_id: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "ID of an open transaction (from 'pltr media-sets create'); "
                "required for transactional media sets."
            ),
            show_default=False,
        ),
    ] = None,
    branch: BranchOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Upload a file as a media item.

    For a transactional media set, pass the ID of an open transaction and
    commit it afterwards ('pltr media-sets commit'); the item is available
    from then on.
    """
    body = file_path.read_bytes()
    with spinner(f"Uploading {file_path.name} ({len(body)} bytes)..."):
        response = MediaSetsService(profile=profile).upload_media(
            media_set_rid,
            body,
            media_item_path=media_item_path,
            transaction_id=transaction_id,
            branch_name=branch,
        )
    cache_rid(media_set_rid)
    cache_rid(response.media_item_rid)
    success(f"Uploaded {file_path.name} as {response.media_item_rid}")
    if transaction_id:
        info(
            "Commit the transaction to make it available: "
            f"pltr media-sets commit {media_set_rid} {transaction_id}"
        )
    emit(
        response,
        format=format,
        output=output,
        columns={
            "Media Item RID": "media_item_rid",
            "Media Set View RID": "media_set_view_rid",
            "Path": lambda _: media_item_path,
        },
        title="Media Item",
    )


@app.command("download")
@pltr_command(sdk=("media_sets.MediaSet.read", "media_sets.MediaSet.read_original"))
def download_media(
    media_set_rid: MediaSetRid,
    media_item_rid: MediaItemRid,
    output_path: Annotated[Path, _output_path_argument("media item's content")],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    original: Annotated[
        bool,
        typer.Option(
            "--original",
            help="Download the file as originally uploaded, not the processed version.",
        ),
    ] = False,
    overwrite: OverwriteOption = False,
):
    """Download a media item's content to a file, or to stdout with -.

    The content is streamed, and stdout never carries anything else. A
    failed download leaves no partial file behind.
    """
    target = _binary_output(output_path, overwrite=overwrite)
    version = "original" if original else "processed"
    service = MediaSetsService(profile=profile)
    with spinner(f"Downloading {version} media item {media_item_rid}..."):
        with service.download_media(
            media_set_rid, media_item_rid, original=original
        ) as response:
            emit_bytes(response.iter_bytes(), output=target)
    cache_rid(media_set_rid)
    cache_rid(media_item_rid)


@app.command("reference")
@pltr_command(sdk="media_sets.MediaSet.reference", beta=True)
def get_media_reference(
    media_set_rid: MediaSetRid,
    media_item_rid: MediaItemRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get a media item's media reference (the value of ontology media properties)."""
    with spinner(f"Getting reference for media item {media_item_rid}..."):
        reference = MediaSetsService(profile=profile).get_media_reference(
            media_set_rid, media_item_rid
        )
    cache_rid(media_set_rid)
    cache_rid(media_item_rid)
    emit(
        reference,
        format=format,
        output=output,
        columns=REFERENCE_COLUMNS,
        title="Media Reference",
    )


@app.command("thumbnail-calculate")
@pltr_command(sdk="media_sets.MediaSet.calculate", beta=True)
def thumbnail_calculate(
    media_set_rid: MediaSetRid,
    media_item_rid: MediaItemRid,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Start calculating an image's thumbnail; prints the calculation status.

    The status is pending, successful or failed; run the command again to
    check on it. Once it's successful, download the thumbnail with
    'pltr media-sets thumbnail-retrieve'.
    """
    with spinner(f"Starting thumbnail calculation for {media_item_rid}..."):
        status = MediaSetsService(profile=profile).calculate_thumbnail(
            media_set_rid, media_item_rid
        )
    cache_rid(media_set_rid)
    cache_rid(media_item_rid)
    if status.type == "successful":
        info(
            "Download it with: pltr media-sets thumbnail-retrieve "
            f"{media_set_rid} {media_item_rid} OUTPUT_PATH"
        )
    emit(
        status,
        format=format,
        output=output,
        columns={"Media Item RID": lambda _: media_item_rid, "Status": "type"},
        title="Thumbnail",
    )


@app.command("thumbnail-retrieve")
@pltr_command(sdk="media_sets.MediaSet.retrieve", beta=True)
def thumbnail_retrieve(
    media_set_rid: MediaSetRid,
    media_item_rid: MediaItemRid,
    output_path: Annotated[Path, _output_path_argument("thumbnail (webp)")],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    overwrite: OverwriteOption = False,
    preview: PreviewNoopOption = False,
):
    """Download an image's calculated thumbnail (200px wide webp), or to stdout with -.

    Calculate it first with 'pltr media-sets thumbnail-calculate'. stdout
    never carries anything but the image. A failed download leaves no
    partial file behind.
    """
    target = _binary_output(output_path, overwrite=overwrite)
    service = MediaSetsService(profile=profile)
    with spinner(f"Downloading thumbnail of {media_item_rid}..."):
        with service.retrieve_thumbnail(media_set_rid, media_item_rid) as response:
            chunks = response.iter_bytes()
            # An empty body means there's no thumbnail (yet): write no file.
            first = next((chunk for chunk in chunks if chunk), None)
            if first is None:
                raise PltrError(
                    "The thumbnail is empty; it may not be calculated yet.",
                    error_type="api_error",
                    exit_code=ExitCode.API,
                    hint=(
                        "Check with 'pltr media-sets thumbnail-calculate "
                        f"{media_set_rid} {media_item_rid}' and retry once it's "
                        "successful."
                    ),
                )
            emit_bytes(itertools.chain([first], chunks), output=target)
    cache_rid(media_set_rid)
    cache_rid(media_item_rid)


@app.command("upload-temp")
@pltr_command(sdk="media_sets.MediaSet.upload_media")
def upload_temp(
    file_path: Annotated[
        Path,
        typer.Argument(
            help="Local file to upload.",
            exists=True,
            dir_okay=False,
            readable=True,
            show_default=False,
        ),
    ],
    profile: ProfileOption = None,
    filename: Annotated[
        Optional[str],
        typer.Option(
            "--filename",
            help="Name for the uploaded media (default: the file's name).",
            show_default=False,
        ),
    ] = None,
    attribution: Annotated[
        Optional[str],
        typer.Option(
            "--attribution",
            help="Usage attribution for the upload.",
            show_default=False,
        ),
    ] = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Upload temporary media; prints its media reference.

    The media is deleted after an hour unless it's persisted, for example by
    using the reference in an ontology edit.
    """
    body = file_path.read_bytes()
    with spinner(f"Uploading {file_path.name} ({len(body)} bytes)..."):
        reference = MediaSetsService(profile=profile).upload_temp_media(
            body, filename=filename or file_path.name, attribution=attribution
        )
    success(f"Uploaded {file_path.name} as temporary media")
    info("Temporary media is deleted after an hour unless it's persisted.")
    emit(
        reference,
        format=format,
        output=output,
        columns=REFERENCE_COLUMNS,
        title="Media Reference",
    )


@app.command("clear")
@pltr_command(sdk="media_sets.MediaSet.clear", beta=True, destructive=True)
def clear_media_item(
    media_set_rid: MediaSetRid,
    media_item_path: Annotated[
        str,
        typer.Argument(
            help="Path of the media item to clear within the media set.",
            show_default=False,
        ),
    ],
    branch: BranchOption = None,
    transaction_id: Annotated[
        Optional[str],
        typer.Option(
            "--transaction-id",
            help=(
                "ID of an open transaction to clear the item in; required for "
                "transactional media sets (the deletion shows once it's committed)."
            ),
            show_default=False,
        ),
    ] = None,
    yes: YesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
):
    """Delete (soft-delete) the media item at a path in a media set.

    The item and all older items at that path become unretrievable. Asks for
    confirmation; --yes skips it.
    """
    confirm_destructive(
        f"Clear the media item at '{media_item_path}' in media set {media_set_rid}? "
        "It and all older items at that path become unretrievable.",
        yes=yes,
    )
    with spinner(f"Clearing media item at {media_item_path}..."):
        MediaSetsService(profile=profile).clear_media_item(
            media_set_rid,
            media_item_path,
            branch_name=branch,
            transaction_id=transaction_id,
        )
    success(f"Cleared the media item at '{media_item_path}'")
    emit(None, format=format)


@app.callback()
def main():
    """
    Media set operations using foundry-platform-sdk.

    Media sets and media items are addressed by RID:
    ri.mio.main.media-set.<uuid> and ri.mio.main.media-item.<uuid>.
    Transactions, uploads, references, thumbnails and clearing use beta
    Foundry endpoints (labeled [beta]).

    Examples:
        # Item metadata, and the RID of the item at a path
        pltr media-sets get <MEDIA_SET_RID> <MEDIA_ITEM_RID>
        pltr media-sets get-by-path <MEDIA_SET_RID> images/photo.jpg

        # Upload to a transactional media set
        TXN=$(pltr media-sets create <MEDIA_SET_RID> --format json | jq -r .)
        pltr media-sets upload <MEDIA_SET_RID> photo.jpg images/photo.jpg "$TXN"
        pltr media-sets commit <MEDIA_SET_RID> "$TXN"

        # Download (- writes to stdout)
        pltr media-sets download <MEDIA_SET_RID> <MEDIA_ITEM_RID> photo.jpg
    """
