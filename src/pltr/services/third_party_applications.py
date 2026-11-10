"""
Third-party applications service wrapper for the Foundry SDK
(``client.third_party_applications``).

``ThirdPartyApplication.get`` is beta and is always called with
``preview=True``. The website endpoints (``ThirdPartyApplication.Website``
and its ``Version``s, used by ``pltr site``) are GA and never get
``preview``. Methods return SDK models unchanged and let SDK exceptions
propagate so the error layer can classify them.
"""

from typing import Any, List, Optional

from .base import BaseService


def foundry_error_name(exc: BaseException) -> Optional[str]:
    """The Foundry ``errorName`` of an SDK error (typed or not)."""
    from foundry_sdk import _errors as sdk

    return exc.name if isinstance(exc, sdk.PalantirRPCException) else None


class ThirdPartyApplicationsService(BaseService):
    """Service wrapper for Foundry third-party application operations."""

    def _get_service(self) -> Any:
        """Get the Foundry third-party applications service."""
        return self.client.third_party_applications

    def get_application(self, application_rid: str) -> Any:
        """Get a third-party application (``ThirdPartyApplication.get``, beta).

        Returns:
            A ``ThirdPartyApplication`` model. The API returns only its
            ``rid``, so this mainly confirms the application exists and that
            you can see it.
        """
        return self.service.ThirdPartyApplication.get(application_rid, preview=True)

    def website_version_exists(self, application_rid: str, version: str) -> bool:
        """Whether the application's website has this version (``Version.get``, GA).

        Only ``VersionNotFound`` means it doesn't; any other error (the
        application or its website not found, no permission) propagates.
        """
        try:
            self.service.ThirdPartyApplication.Website.Version.get(
                application_rid, version
            )
        except Exception as exc:
            if foundry_error_name(exc) == "VersionNotFound":
                return False
            raise
        return True

    def upload_website_version(
        self, application_rid: str, body: bytes, version: str
    ) -> Any:
        """Upload a zip as a new website version (``Version.upload``, GA).

        Returns:
            A ``Version`` model.
        """
        return self.service.ThirdPartyApplication.Website.Version.upload(
            application_rid, body, version=version
        )

    def list_website_versions(
        self,
        application_rid: str,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """One page of the website's versions (``Version.list``, GA): an SDK
        ``ResourceIterator`` (never iterate it: that fetches every page)."""
        return self.service.ThirdPartyApplication.Website.Version.list(
            application_rid, page_size=page_size, page_token=page_token
        )

    def deploy_website(
        self,
        application_rid: str,
        version: str,
        *,
        timeout: float,
        resume: Optional[str] = None,
    ) -> Any:
        """Deploy an uploaded version (``Website.deploy``, GA); return the ``Website``.

        Foundry scans an upload for vulnerabilities, and deploying it before
        the scan is done fails with ``ScanningInProgress``: the deploy is
        retried with backoff for up to ``timeout`` seconds. Deploying the
        version that is already live changes nothing, so a retry is safe.

        Raises:
            WaitTimedOut: (exit 9) still scanning after ``timeout`` seconds;
                the version stays uploaded, and the error suggests
                ``resume``, the command that deploys it.
        """
        from ..contract import WaitTimedOut, info
        from .waiting import wait_until

        noted: List[bool] = []

        def attempt() -> Any:
            try:
                return self.service.ThirdPartyApplication.Website.deploy(
                    application_rid, version=version
                )
            except Exception as exc:
                if foundry_error_name(exc) != "ScanningInProgress":
                    raise
                if not noted:
                    info(
                        f"Foundry is scanning version {version} for "
                        "vulnerabilities; deploying it once the scan is done..."
                    )
                    noted.append(True)
                return None

        def timed_out(latest: Any) -> Exception:
            return WaitTimedOut(
                f"Version {version} was uploaded, but Foundry was still scanning "
                f"it for vulnerabilities after {timeout:g} seconds, so it isn't "
                "deployed.",
                hint=(
                    "Deploy it once the scan is done; the Website hosting page of "
                    "Developer Console shows the scan."
                ),
                suggested_command=resume,
                parameters={
                    "thirdPartyApplicationRid": application_rid,
                    "version": version,
                },
            )

        return wait_until(
            attempt,
            lambda website: website is not None,
            timeout=timeout,
            on_timeout=timed_out,
        )
