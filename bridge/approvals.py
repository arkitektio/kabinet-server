"""Release approvals: what a user pre-authorized, and whether it still holds.

The authorization itself lives in lok (a ``Mandate``: the approver lets a deployer
app provision this release as them). Kabinet keeps the pointer and pins it to a
digest of the release, because a release can be re-published under the same
version (``upsert_app_image`` is an ``update_or_create`` on (app, version)) — an
approval must not silently carry over to different scopes, requirements or images.
"""

import hashlib
import json

from asgiref.sync import sync_to_async
from django.utils import timezone

from bridge import models

DIGEST_PREFIX = "sha256:"


class ApprovalError(Exception):
    """A deployment was refused by its approval."""


def _image_ref(image: models.DockerImage) -> str:
    return image.image_string


def image_is_pinned(image: models.DockerImage) -> bool:
    """Whether the image is addressed by content digest rather than a (movable) tag."""
    return "@sha256:" in image.image_string


def release_digest(release: models.Release) -> str:
    """A content digest of everything an approval vouches for.

    Identity, the OAuth scopes, the union of service requirements, and each
    flavour's image. An image addressed by tag only (no ``@sha256:``) is hashed by
    its tag, so a rebuild pushed under the same tag is *not* detected — see
    :func:`release_is_pinned`.
    """
    flavours = list(release.flavours.select_related("image").order_by("name"))
    requirements = sorted(
        {(r.get("key"), r.get("service"), bool(r.get("optional"))) for f in flavours for r in (f.requirements or [])},
        key=lambda r: (str(r[0]), str(r[1]), r[2]),
    )
    payload = {
        "identifier": release.app.identifier,
        "version": release.version,
        "scopes": sorted(set(release.scopes or [])),
        "requirements": requirements,
        "images": [[f.name, _image_ref(f.image)] for f in flavours],
    }
    return DIGEST_PREFIX + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def release_is_pinned(release: models.Release) -> bool:
    """Whether every flavour image is digest-addressed (so the digest covers image content)."""
    return all(image_is_pinned(f.image) for f in release.flavours.select_related("image"))


def release_requirements(release: models.Release) -> list[dict]:
    """The union of the release's flavour requirements, as lok manifest requirements."""
    seen: dict[tuple, dict] = {}
    for flavour in release.flavours.all():
        for r in flavour.requirements or []:
            seen.setdefault((r.get("key"), r.get("service")), r)
    return list(seen.values())


def is_stale(approval: models.ReleaseApproval) -> bool:
    return approval.digest != release_digest(approval.release)


def is_active(approval: models.ReleaseApproval) -> bool:
    return approval.revoked_at is None and not is_stale(approval)


def check_deployable(approval: models.ReleaseApproval, flavour: models.Flavour, backend: models.Backend) -> None:
    """Refuse a deployment the approval does not cover."""
    if approval.revoked_at is not None:
        raise ApprovalError("This approval has been revoked.")
    if flavour.release_id != approval.release_id:
        raise ApprovalError("The flavour does not belong to the approved release.")
    if approval.backends.exists() and not approval.backends.filter(pk=backend.pk).exists():
        raise ApprovalError("This backend is not allowed to deploy under this approval.")
    if is_stale(approval):
        raise ApprovalError("The release changed since it was approved (scopes, requirements or images); it needs to be approved again.")


acheck_deployable = sync_to_async(check_deployable)


def create_approval(
    *,
    release: models.Release,
    approver,
    organization,
    mandate_id: str,
    agent: str,
    backends: list[models.Backend] | None = None,
) -> models.ReleaseApproval:
    approval = models.ReleaseApproval.objects.create(
        release=release,
        approver=approver,
        organization=organization,
        mandate_id=mandate_id,
        agent=agent,
        digest=release_digest(release),
    )
    if backends:
        approval.backends.set(backends)
    return approval


def revoke(approval: models.ReleaseApproval) -> models.ReleaseApproval:
    if approval.revoked_at is None:
        approval.revoked_at = timezone.now()
        approval.save(update_fields=["revoked_at"])
    return approval
