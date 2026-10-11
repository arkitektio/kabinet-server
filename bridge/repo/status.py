"""What the last scan of a repository came to, kept on the repository.

A scan used to leave nothing behind but a log line: an OCI scan's per-tag problems were
logged and dropped, and a GitHub repo that could not be read again looked exactly like one
that was read. Every scan now ends here, so the catalogue can say which repos are healthy,
which could not be read at all, and which were read but carried something kabinet refused.
"""

from asgiref.sync import sync_to_async
from django.utils import timezone

from bridge import models


def record_scan(repo: models.Repo, *, error: str | None = None, problems: dict[str, str] | None = None) -> None:
    """Store the outcome of a scan of ``repo``: a failure as a whole (``error``), or what it refused.

    A failed scan keeps the problems the last one found: it did not look again, so they still stand.
    """
    repo.scan_attempted_at = timezone.now()
    repo.scan_error = error or ""
    fields = ["scan_attempted_at", "scan_error"]
    if error is None:
        repo.scan_problems = problems or {}
        fields.append("scan_problems")
        if isinstance(repo, models.GithubRepo):
            # `OciRepo.scanned_at` is written by the scan itself, together with what it saw.
            repo.scanned_at = repo.scan_attempted_at
            fields.append("scanned_at")
    repo.save(update_fields=fields)


async def arecord_scan(repo: models.Repo, *, error: str | None = None, problems: dict[str, str] | None = None) -> None:
    """:func:`record_scan`, from async code."""
    await sync_to_async(record_scan)(repo, error=error, problems=problems)
