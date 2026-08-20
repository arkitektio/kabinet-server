"""Turning a built app image into catalogue rows.

``adownload_logo`` used to live here (and, verbatim, in ``bridge/mutations/repo.py``).
It fetched a manifest's logo mid-write and handed the file to ``release.logo.save()`` --
but ``Release.logo`` is a ForeignKey to ``MediaStore``, not a FileField, and is None for
a release being created, so every manifest carrying a logo raised and was swallowed into
a bare ``DBError``. The upstream URL now goes to ``Release.original_logo``; ingesting the
image into the datalayer is a separate piece of work.

Everything here is synchronous on purpose. ``transaction.atomic`` has no async form, and
the ``a``-prefixed ORM calls these used to make would each have run outside it. The two
async resolvers that need this (``scan_repo`` and ``create_app_image``) wrap it in
``sync_to_async``. Nothing below does IO other than the database -- the manifest has
already been fetched by the caller -- so there is nothing to be gained by staying async.
"""

from django.db import transaction

from bridge import models

from .errors import DBError
from .models import AppImageInputModel, KabinetConfigFile


def upsert_app_image(
    app_image: AppImageInputModel,
    organization: models.Organization,
    repo: models.Repo | None = None,
) -> models.Flavour:
    """Create or update every row one built app image implies, and return its flavour.

    This is the unit of work behind both entry points into the catalogue: scanning a
    GitHub repo walks a ``kabinet.yml`` and calls this once per app image, and
    ``createAppImage`` calls it once for an image that was pushed directly. It used to
    exist only as the body of ``parse_config``'s loop, which is why ``createAppImage``
    shipped as a stub -- the work it needed was there but not reachable.

    ``repo`` is optional: an image registered through ``createAppImage`` has no source
    repository, which is what makes ``Flavour.repo`` nullable.
    """
    manifest = app_image.manifest

    app, _ = models.App.objects.get_or_create(
        identifier=manifest.identifier,
        organization=organization,
    )

    release, _ = models.Release.objects.update_or_create(
        version=manifest.version,
        app=app,
        defaults=dict(
            scopes=manifest.scopes,
            # `Release.logo` is a FK to MediaStore, not a FileField. This used to call
            # `release.logo.save(...)` on that FK -- which is None for a new release --
            # so every manifest carrying a logo raised `AttributeError`, was wrapped into
            # a bare `DBError` and failed the whole scan. Until the image is ingested
            # into the datalayer, the upstream URL is what we have, and `original_logo`
            # is the field that holds it.
            original_logo=manifest.logo,
        ),
    )

    image, _ = models.DockerImage.objects.update_or_create(
        image_string=app_image.image.image_string,
        organization=organization,
        defaults=dict(build_at=app_image.image.build_at),
    )

    flavour, _ = models.Flavour.objects.update_or_create(
        release=release,
        name=app_image.flavour_name or "vanilla",
        defaults=dict(
            deployment_id=app_image.app_image_id,
            flavour=app_image.app_image_id,
            selectors=[selector.model_dump() for selector in app_image.selectors],
            repo=repo,
            image=image,
            manifest=manifest.model_dump(),
            requirements=[requirement.model_dump() for requirement in app_image.inspection.requirements],
        ),
    )

    for implementation in app_image.inspection.implementations:
        definition = implementation.definition
        def_model, _ = models.Definition.objects.update_or_create(
            hash=definition.unique_hash,
            organization=organization,
            defaults=dict(
                description=definition.description,
                args=[port.model_dump() for port in definition.args],
                returns=[port.model_dump() for port in definition.returns],
                name=definition.name,
            ),
        )
        def_model.flavours.add(flavour)

    return flavour


@transaction.atomic
def parse_config(
    config: KabinetConfigFile,
    repo: models.GithubRepo,
    organization: models.Organization,
) -> list[models.Flavour]:
    """Create or update every flavour a repo's ``kabinet.yml`` describes.

    Atomic, which it was not. A repo describing five app images used to write them one
    autocommitted row at a time, so a failure on the third left the first two committed
    and the organization holding a half-scanned catalogue that no later scan would
    reconcile -- there was no ``atomic`` anywhere in the codebase and ``ATOMIC_REQUESTS``
    is off.

    Failures still surface as ``DBError``, but the message now names the repo and carries
    the underlying error. It used to be the bare string "Could not create models from
    deployments" for any failure across six models, which told a caller nothing -- and
    every call site caught ``KeyError``, an exception this has never raised.
    """
    try:
        return [upsert_app_image(app_image, organization, repo=repo) for app_image in config.app_images]
    except Exception as e:
        raise DBError(f"Could not create models from the app images of {repo}: {e}") from e
