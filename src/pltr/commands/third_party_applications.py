"""
Third-party application commands (Foundry Third Party Applications API).

Applications are created in Developer Console and addressed by RID. Their
websites and website versions are available as generated commands
(``pltr api third-party-applications third-party-application website ...``).
"""

import typer
from typing_extensions import Annotated

from ..contract import (
    Columns,
    FormatOption,
    OutputOption,
    PreviewNoopOption,
    ProfileOption,
    emit,
    pltr_command,
    spinner,
)
from ..services.third_party_applications import ThirdPartyApplicationsService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()

#: Table/CSV columns for a ``ThirdPartyApplication`` model (it has only a RID).
APPLICATION_COLUMNS: Columns = {"RID": "rid"}


@app.command("get")
@pltr_command(sdk="third_party_applications.ThirdPartyApplication.get", beta=True)
def get_application(
    application_rid: Annotated[
        str,
        typer.Argument(
            help=(
                "Third-party application RID "
                "(ri.third-party-applications.main.application.<id>; shown in "
                "Developer Console)."
            ),
            autocompletion=complete_rid,
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get a third-party application.

    The API returns only the application's RID, so this confirms that the
    application exists and that you can see it.
    """
    with spinner(f"Fetching third-party application {application_rid}..."):
        application = ThirdPartyApplicationsService(profile=profile).get_application(
            application_rid
        )
    cache_rid(application_rid)
    emit(
        application,
        format=format,
        output=output,
        columns=APPLICATION_COLUMNS,
        title="Third-Party Application",
    )
